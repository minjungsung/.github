import unittest
from scripts.maintain_dependencies import maintain, plan_pr, trusted_checks
from lib.models import Inventory, Repository

SHA = 'a' * 40

def pr(**overrides):
    return dict({'user': {'login': 'dependabot[bot]'}, 'head': {'sha': SHA},
                 'state': 'open', 'draft': False, 'mergeable_state': 'clean',
                 'auto_merge': None}, **overrides)

def check(name, **overrides):
    return dict({'name': name, 'id': 1, 'head_sha': SHA, 'app': {'id': 15368},
                 'status': 'completed', 'conclusion': 'success'}, **overrides)

class MaintenanceTests(unittest.TestCase):
    def test_gate_alone_or_ordinary_noop_cannot_authorize_merge(self):
        self.assertFalse(trusted_checks([check('dependency-gate')], SHA))
        self.assertFalse(trusted_checks([check('dependency-gate'), check('validate-dependencies / ordinary-pr')], SHA))

    def test_current_application_checks_require_trusted_identity(self):
        checks = [check('dependency-gate'), check('validate-dependencies / validate-projects (root, npm)')]
        self.assertTrue(trusted_checks(checks, SHA))
        self.assertFalse(trusted_checks(checks, 'b'*40))
        checks[1]['app']['id'] = 1
        self.assertFalse(trusted_checks(checks, SHA))

    def test_latest_failure_supersedes_old_success(self):
        checks = [check('dependency-gate'), check('validate-dependencies / validate-projects (root, npm)'),
                  check('dependency-gate', id=2, conclusion='failure')]
        self.assertFalse(trusted_checks(checks, SHA))

    def test_manual_and_foreign_authors_never_mutate(self):
        self.assertEqual(plan_pr(pr(mergeable_state='behind'), [], False)[0], 'manual-repository')
        self.assertEqual(plan_pr(pr(user={'login':'someone'}), [], True)[0], 'ignore')

    def test_failed_validation_cannot_be_merged_by_controller(self):
        self.assertEqual(plan_pr(pr(), [], True)[0], 'validation-blocked')
        self.assertEqual(plan_pr(pr(mergeable_state='behind'), [], True)[0], 'refresh')

    def test_inaccessible_security_keeps_healthy_sibling_and_incomplete_coverage(self):
        from lib.models import PolicyError
        class Fake:
            def list_repositories(self, owner):
                return [{'name':n,'nameWithOwner':f'{owner}/{n}'} for n in ['one','two']]
            def alert_pages(self, repository):
                if repository.endswith('/one'): raise PolicyError('denied')
                return []
            def pages(self, endpoint): return []
        inventory=Inventory(1,tuple(Repository(n,'main',()) for n in ['one','two']))
        result=maintain('example',inventory,Fake())
        self.assertFalse(result['coverage-complete'])
        self.assertEqual(len(result['repositories']),2)
        self.assertEqual(result['repositories'][0]['alert-status'],'unavailable')
        self.assertEqual(result['mutations'],[])


class AlertPaginationTests(unittest.TestCase):
    def test_cursor_pages_follow_links_without_numeric_page(self):
        import json, subprocess
        from scripts.maintain_dependencies import MaintenanceClient
        commands=[]
        def runner(command):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps([[{'number':1}], [{'number':2}]]), '')
        result=MaintenanceClient(runner).alert_pages('example/project')
        self.assertEqual([a['number'] for a in result],[1,2])
        self.assertIn('--paginate',commands[0])
        self.assertNotIn('&page=',commands[0][-1])

class TrustedMergeTests(unittest.TestCase):
    def inputs(self):
        detail=pr(mergeable=True, body='Bumps package from 1.0.0 to 2.0.0.\n')
        checks=[check('dependency-gate'),check('validate-dependencies / validate-projects (root, npm)'),check('ci')]
        protection={'checks':[{'context':'dependency-gate','app_id':15368}]}
        return detail, checks, [], protection, 1

    def test_workflow_permission_failure_does_not_replace_application_checks(self):
        from scripts.maintain_dependencies import merge_eligibility
        args=list(self.inputs());args[1].append(check('dependabot-auto-merge',conclusion='failure'))
        self.assertTrue(merge_eligibility(*args)[0])
        args[1][2]['conclusion']='failure'
        self.assertFalse(merge_eligibility(*args)[0])

    def test_optional_quota_is_allowed_but_required_quota_is_blocked(self):
        from scripts.maintain_dependencies import merge_eligibility
        args=list(self.inputs());args[2]=[{'context':'Vercel','state':'failure','description':'Deployment rate limited — retry in 24 hours.'}]
        self.assertTrue(merge_eligibility(*args)[0])
        args[3]['checks'].append({'context':'Vercel','app_id':None})
        self.assertFalse(merge_eligibility(*args)[0])

    def test_incomplete_matrix_unknown_metadata_and_absent_protection_block(self):
        from scripts.maintain_dependencies import merge_eligibility
        for mutation in ['matrix','metadata','protection','stale']:
            args=list(self.inputs())
            if mutation=='matrix':args[4]=2
            if mutation=='metadata':args[0]['body']='Updates dependencies'
            if mutation=='protection':args[3]={'checks':[]}
            if mutation=='stale':args[0]['mergeable_state']='behind'
            self.assertFalse(merge_eligibility(*args)[0])

if __name__ == '__main__': unittest.main()
