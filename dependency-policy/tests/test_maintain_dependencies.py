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
            def pages(self, endpoint):
                if '/one/dependabot/' in endpoint: raise PolicyError('denied')
                return []
        inventory=Inventory(1,tuple(Repository(n,'main',()) for n in ['one','two']))
        result=maintain('example',inventory,Fake())
        self.assertFalse(result['coverage-complete'])
        self.assertEqual(len(result['repositories']),2)
        self.assertEqual(result['repositories'][0]['alert-status'],'unavailable')
        self.assertEqual(result['mutations'],[])

if __name__ == '__main__': unittest.main()
