import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import subprocess
import unittest

from lib.models import PolicyError, Project, Repository
from scripts.configure_protection import CHECK_CONTEXT, ProtectionClient, find_check_context, main, plan_required_check
from scripts.render_callers import render_caller

SHA = 'a' * 40
PIN = 'b' * 40
REPO = Repository('sample', 'main', (Project('actions', 'github-actions', '.', timeout_minutes=5),))
CURRENT = {
    'url': 'example',
    'required_status_checks': {'strict': True, 'contexts': ['CI'], 'checks': [{'context': 'CI', 'app_id': 17}]},
    'required_pull_request_reviews': {'required_approving_review_count': 2, 'dismiss_stale_reviews': True},
    'enforce_admins': {'enabled': True},
}


class FakeAPI:
    def __init__(self):
        self.pages = [[{'name': CHECK_CONTEXT, 'head_sha': SHA, 'status': 'completed', 'conclusion': 'success'}]]
        self.current = copy.deepcopy(CURRENT)
        self.caller = render_caller(REPO, PIN)
        self.branch = 'main'
        self.mutations = []
        self.backup = None
        self.read_pages = []

    def check_runs_page(self, repository, sha, page):
        self.read_pages.append((repository, sha, page))
        return {'total_count': sum(map(len, self.pages)), 'check_runs': self.pages[page - 1]}

    def default_branch(self, repository):
        return self.branch

    def protection(self, repository, branch):
        return copy.deepcopy(self.current)

    def caller_text(self, repository, branch):
        return self.caller

    def update_required_checks(self, repository, branch, payload):
        assert self.backup.is_file()
        assert json.loads(self.backup.read_text()) == self.current
        self.mutations.append(copy.deepcopy(payload))
        self.current['required_status_checks'].update(payload)


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = self.root / 'inventory.json'
        self.inventory.write_text(json.dumps({'schema-version': 1, 'repositories': [{'name': 'sample', 'default-branch': 'main', 'projects': [{'name': 'actions', 'ecosystem': 'github-actions', 'path': '.'}]}]}))
        self.api.backup = self.root / 'backups' / 'example-sample.json'

    def run_cli(self, *extra):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(['--owner', 'example', '--repository', 'sample', '--sha', SHA, *extra], client=self.api, inventory_path=self.inventory, backup_directory=self.api.backup.parent)
        return result, json.loads(output.getvalue())

    def test_json_api_boundary_and_payload(self):
        commands = []
        payloads = []

        def runner(command):
            commands.append(command)
            if '--input' in command:
                payloads.append(json.loads(Path(command[command.index('--input') + 1]).read_text()))
            return subprocess.CompletedProcess(command, 0, '{}', '')

        client = ProtectionClient(runner)
        client.check_runs_page('example/sample', SHA, 2)
        client.protection('example/sample', 'release/main')
        payload = {'strict': True, 'contexts': ['CI', CHECK_CONTEXT], 'checks': [{'context': 'CI', 'app_id': 17}]}
        client.update_required_checks('example/sample', 'release/main', payload)
        self.assertIn('filter=all&per_page=100&page=2', commands[0][-1])
        self.assertIn('release%2Fmain/protection', commands[1][-1])
        self.assertIn('PATCH', commands[2])
        self.assertIn('repos/example/sample/branches/release%2Fmain/protection/required_status_checks', commands[2])
        self.assertEqual(payloads, [payload])

    def test_backup_failure_prevents_mutation(self):
        self.api.backup.parent.mkdir()
        self.api.backup.write_text('previous backup')
        with self.assertRaises(FileExistsError):
            self.run_cli('--apply', '--policy-sha', PIN)
        self.assertEqual(self.api.mutations, [])
        self.assertEqual(self.api.backup.read_text(), 'previous backup')

    def test_exact_successful_context(self):
        self.api.pages[0].insert(0, {'name': 'dependency-gate', 'head_sha': SHA, 'conclusion': 'success'})
        self.assertEqual(find_check_context(self.api, 'example/sample', SHA), CHECK_CONTEXT)
        self.assertEqual(self.api.read_pages[0][1], SHA)

    def test_reject_missing_duplicate_unsuccessful_wrong_sha_and_pending(self):
        good = self.api.pages[0][0]
        for runs in [[], [good, good], [dict(good, conclusion='failure')], [dict(good, head_sha='c' * 40)], [dict(good, status='in_progress')]]:
            with self.subTest(runs=runs), self.assertRaises(PolicyError):
                self.api.pages = [runs]
                find_check_context(self.api, 'example/sample', SHA)

    def test_paginate_and_reject_cross_page_duplicate(self):
        good = self.api.pages[0][0]
        self.api.pages = [[{'name': 'CI'}] * 100, [good]]
        self.assertEqual(find_check_context(self.api, 'example/sample', SHA), CHECK_CONTEXT)
        self.assertEqual(len(self.api.read_pages), 2)
        self.api.pages[0][0] = good
        with self.assertRaises(PolicyError):
            find_check_context(self.api, 'example/sample', SHA)

    def test_plan_preserves_original_and_review_settings(self):
        current = copy.deepcopy(CURRENT)
        after = plan_required_check(current, CHECK_CONTEXT)
        self.assertEqual(current, CURRENT)
        self.assertEqual(after['required_pull_request_reviews'], current['required_pull_request_reviews'])
        self.assertEqual(after['required_status_checks']['checks'][0], {'context': 'CI', 'app_id': 17})
        self.assertIn(CHECK_CONTEXT, after['required_status_checks']['contexts'])

    def test_legacy_contexts_are_preserved_in_modern_checks_payload(self):
        current = copy.deepcopy(CURRENT)
        current['required_status_checks']['contexts'].append('Legacy CI')
        after = plan_required_check(current, CHECK_CONTEXT)
        self.assertIn({'context': 'Legacy CI', 'app_id': -1}, after['required_status_checks']['checks'])
        self.assertEqual(after['required_status_checks']['checks'][0]['app_id'], 17)

    def test_dry_run_prints_diff_without_backup_or_mutation(self):
        result, diff = self.run_cli()
        self.assertEqual(result, 0)
        self.assertEqual(diff['before'], CURRENT)
        self.assertEqual(diff['after'], plan_required_check(CURRENT, CHECK_CONTEXT))
        self.assertEqual(self.api.mutations, [])
        self.assertFalse(self.api.backup.exists())

    def test_apply_backup_preservation_and_second_apply_idempotent(self):
        self.run_cli('--apply', '--policy-sha', PIN)
        original_backup = self.api.backup.read_bytes()
        self.assertEqual(len(self.api.mutations), 1)
        self.assertEqual(set(self.api.mutations[0]), {'strict', 'contexts', 'checks'})
        self.assertEqual(self.api.current['required_pull_request_reviews'], CURRENT['required_pull_request_reviews'])
        self.run_cli('--apply', '--policy-sha', PIN)
        self.assertEqual(len(self.api.mutations), 1)
        self.assertEqual(self.api.backup.read_bytes(), original_backup)

    def test_apply_requires_pin_and_exact_default_branch_caller(self):
        for pin, caller, branch in [(None, self.api.caller, 'main'), ('main', self.api.caller, 'main'), (PIN, '', 'main'), (PIN, self.api.caller.replace(PIN, SHA), 'main'), (PIN, self.api.caller, 'other')]:
            with self.subTest(pin=pin, branch=branch), self.assertRaises(PolicyError):
                self.api.caller, self.api.branch = caller, branch
                self.run_cli('--apply', *(['--policy-sha', pin] if pin else []))
            self.assertFalse(self.api.backup.exists())
            self.assertEqual(self.api.mutations, [])

    def test_reject_invalid_commit_before_api(self):
        with self.assertRaises(PolicyError):
            find_check_context(self.api, 'example/sample', 'main')
        self.assertEqual(self.api.read_pages, [])

    def test_existing_context_only_in_checks_is_idempotent(self):
        current = copy.deepcopy(CURRENT)
        current['required_status_checks']['checks'].append({'context': CHECK_CONTEXT, 'app_id': 44})
        self.assertEqual(plan_required_check(current, CHECK_CONTEXT), current)


if __name__ == '__main__':
    unittest.main()
