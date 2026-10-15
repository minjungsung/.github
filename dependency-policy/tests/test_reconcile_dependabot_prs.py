import io
import json
from contextlib import redirect_stdout
import unittest
import subprocess

from lib.models import PolicyError
from scripts.reconcile_dependabot_prs import ReconciliationClient, classify_pr, main, verified_body_update_type

SHA = 'a' * 40


def passing():
    return {'number': 1, 'url': 'https://github.com/example/project/pull/1',
            'author': 'dependabot[bot]', 'head_sha': SHA, 'state': 'open',
            'update_type': 'patch', 'mergeable': True, 'behind': False,
            'gate': {'head_sha': SHA, 'status': 'completed', 'conclusion': 'success', 'app': 'github-actions'},
            'required_checks_pass': True, 'external_blocker': None}


class ReconcileTests(unittest.TestCase):
    def test_canonical_dependabot_version_evidence_is_conservative(self):
        for version, expected in [('1.0.1', 'patch'), ('1.1.0', 'minor'), ('2.0.0', 'major'), ('1.0.0-beta', None)]:
            detail = {'user': {'login': 'dependabot[bot]'}, 'body': f'Bumps package from 1.0.0 to {version}.\n'}
            self.assertEqual(verified_body_update_type(detail), expected)
        for body in ('Arbitrary versions 1.0.0 and 1.0.1', 'Bumps package from 1.0.0 to 1.0.1.\nBumps other from 1.0.0 to 2.0.0.\n'):
            self.assertIsNone(verified_body_update_type({'user': {'login': 'dependabot[bot]'}, 'body': body}))
        self.assertIsNone(verified_body_update_type({'user': {'login': 'other'}, 'body': 'Bumps package from 1.0.0 to 1.0.1.\n'}))

    def test_passing_patch_minor_are_eligible(self):
        for update in ('patch', 'minor'):
            pr = passing(); pr['update_type'] = update
            self.assertEqual(classify_pr(pr).state, 'merge-eligible')

    def test_stale_conflicted_failures_and_pending_have_explained_actions(self):
        for field, value, expected in [('behind', True, 'request-rebase'),
                                       ('mergeable', False, 'request-rebase'),
                                       ('required_checks_pass', False, 'investigate-checks')]:
            pr = passing(); pr[field] = value
            self.assertEqual(classify_pr(pr).state, expected)
        for conclusion in ('failure', 'cancelled', 'timed_out'):
            pr = passing(); pr['gate']['conclusion'] = conclusion
            self.assertEqual(classify_pr(pr).state, 'remediate')
        pr = passing(); pr['gate']['head_sha'] = 'b' * 40
        self.assertEqual(classify_pr(pr).state, 'await-current-checks')

    def test_major_unknown_and_external_blocker(self):
        for update, expected in [('major', 'manual-major'), (None, 'manual-unknown')]:
            pr = passing(); pr['update_type'] = update
            self.assertEqual(classify_pr(pr).state, expected)
        pr = passing(); pr['external_blocker'] = 'required review approval'
        self.assertEqual(classify_pr(pr).reason, 'required review approval')

    def test_close_requires_reviewed_concrete_evidence(self):
        for kind in ('duplicate', 'superseded', 'upstream-incompatible', 'withdrawn'):
            pr = passing(); pr['closure_evidence'] = {'kind': kind, 'reason': 'Documented replacement', 'url': 'https://github.com/example/project/pull/2', 'reviewed': True}
            self.assertEqual(classify_pr(pr).state, 'close-with-reason')
            pr['closure_evidence']['reviewed'] = False
            self.assertNotEqual(classify_pr(pr).state, 'close-with-reason')

    def test_wrong_author_or_malformed_head_rejected(self):
        for field, value in [('author', 'other'), ('head_sha', 'main')]:
            pr = passing(); pr[field] = value
            with self.assertRaises(PolicyError): classify_pr(pr)

    def test_check_is_read_only_and_unresolved_exit_nonzero(self):
        class Fake:
            def collect(self, owner): return [passing()]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--owner', 'example', '--check'], client=Fake()), 0)
        self.assertEqual(json.loads(output.getvalue())[0]['state'], 'merge-eligible')
        class Failed:
            def collect(self, owner):
                pr = passing(); pr['behind'] = True; return [pr]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--owner', 'example', '--check'], client=Failed()), 1)

    def test_json_collection_handles_failing_checks_and_keeps_unverified_metadata_manual(self):
        calls = []
        def runner(command):
            calls.append(command)
            code = 0
            if command[1:3] == ['pr', 'view']:
                value = {'headRefOid': SHA, 'author': {'login': 'app/dependabot'}, 'mergeStateStatus': 'CLEAN'}
            elif command[1:3] == ['pr', 'checks']:
                value = [{'bucket': 'fail', 'name': 'CI'}]; code = 1
            else:
                endpoint = command[-1]
                if endpoint.startswith('users/'):
                    value = [{'full_name': 'example/project', 'archived': False}]
                elif '/pulls?' in endpoint:
                    value = [{'number': 1, 'user': {'login': 'dependabot[bot]'}}]
                elif endpoint.endswith('/pulls/1'):
                    value = {'number': 1, 'user': {'login': 'dependabot[bot]'}, 'state': 'open',
                             'head': {'sha': SHA}, 'mergeable': True,
                             'html_url': 'https://github.com/example/project/pull/1',
                             'body': 'Bumps package from 1.0.0 to 1.0.1.\n'}
                else:
                    value = {'total_count': 0, 'check_runs': []}
            return subprocess.CompletedProcess(command, code, json.dumps(value), '')
        records = ReconciliationClient(runner).collect('example')
        self.assertEqual(records[0]['update_type'], 'patch')
        self.assertFalse(records[0]['required_checks_pass'])
        self.assertEqual(classify_pr(records[0]).state, 'await-current-checks')
        self.assertTrue(all(command[1] in {'api', 'pr'} for command in calls))
        self.assertFalse(any(command[1:3] in [['pr', 'comment'], ['pr', 'close'], ['pr', 'merge']] for command in calls))

    def test_rebase_boundary_invokes_handler_only_for_rebase_decision(self):
        class Fake:
            def collect(self, owner):
                pr = passing(); pr['behind'] = True; return [pr]
        calls = []
        with redirect_stdout(io.StringIO()):
            main(['--owner', 'example', '--request-rebase'], client=Fake(), mutation_handler=lambda mode, decision: calls.append((mode, decision.state)))
        self.assertEqual(calls, [('request-rebase', 'request-rebase')])

    def test_mutations_without_reviewed_handler_refused(self):
        for flag in ('--request-rebase', '--apply-remediation'):
            with self.assertRaises(PolicyError): main(['--owner', 'example', flag], client=object())


if __name__ == '__main__': unittest.main()
