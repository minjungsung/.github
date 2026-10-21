import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import yaml

from lib.models import Inventory, Project, Repository, PolicyError
from scripts.audit_repositories import DiscoveredRepository
from scripts.sync_fleet import (checked_merge, dependabot_config, dependency_caller,
                                ensure_pr, reconciled_inventory, release_caller, security_caller,
                                configure_protection, synchronize)

SHA = 'a' * 40


class FleetSyncTests(unittest.TestCase):
    def test_rename_preserves_reviewed_commands_and_retired_entries_are_removed(self):
        project = Project('app', 'npm', '.', '24', 'package.json', test_command='npm test', timeout_minutes=15)
        old = Repository('old-name', 'main', (project,), auto_merge_enabled=False)
        retired = Repository('gone', 'main', (project,))
        discovered = DiscoveredRepository('new-name', 'main', False, (project,))
        inventory, issues = reconciled_inventory(Inventory(1, (old, retired)), [discovered], {'new-name': 'old-name'})
        self.assertEqual([r.name for r in inventory.repositories], ['new-name'])
        self.assertEqual(inventory.repositories[0].projects[0].test_command, 'npm test')
        self.assertFalse(inventory.repositories[0].auto_merge_enabled)
        self.assertEqual(issues, [])

    def test_empty_ambiguous_and_unsupported_projects_never_gain_auto_merge(self):
        project = Project('workflow', 'github-actions', '.', timeout_minutes=5)
        items = [DiscoveredRepository('empty', None, False),
                 DiscoveredRepository('ambiguous', 'main', False, (project,), ambiguities=('incomplete',)),
                 DiscoveredRepository('unsupported', 'main', False, (project,), unsupported_ecosystems=('bun',), auto_merge_enabled=False),
                 DiscoveredRepository('repo-template', 'main', False, (project,))]
        inventory, issues = reconciled_inventory(Inventory(1, ()), items, {})
        self.assertEqual([r.name for r in inventory.repositories], ['ambiguous', 'unsupported'])
        self.assertTrue(all(not r.auto_merge_enabled for r in inventory.repositories))
        self.assertEqual(len(issues), 2)

    def test_dependabot_preserves_custom_groups_and_multi_directory_entries(self):
        source = {'version': 2, 'updates': [{'package-ecosystem': 'npm', 'directories': ['/', '/web'],
                   'schedule': {'interval': 'daily'}, 'groups': {'production': {'patterns': ['*']}}}]}
        repo = Repository('app', 'main', (Project('root', 'npm', '.'), Project('web', 'npm', 'web')))
        first = dependabot_config(yaml.safe_dump(source), repo)
        result = yaml.safe_load(first)
        self.assertEqual(result['updates'][0], source['updates'][0])
        self.assertEqual(len(result['updates']), 2)
        self.assertEqual(first, dependabot_config(first, repo))
        with self.assertRaises(PolicyError):
            dependabot_config('version: 1', repo)

    def test_checked_merge_waits_for_security_application_and_external_checks(self):
        class Fake:
            def __init__(self, security='success', external='success'):
                self.security = security
                self.external = external
                self.mutations = []
            def api(self, endpoint, method='GET', payload=None):
                if method == 'PUT':
                    self.mutations.append(payload)
                    return {'merged': True}
                return {'head': {'sha': SHA}, 'mergeable': True}
            def _json(self, command):
                if 'check-runs?' in command[-1]:
                    return [{'check_runs': [{'name': name, 'app': {'id': 15368}, 'head_sha': SHA,
                        'status': 'completed', 'conclusion': conclusion} for name, conclusion in
                        [('dependency-gate', 'success'), ('scan / secret-scanning', self.security), ('application', 'success')]]}]
                return [[{'context': 'deployment', 'state': self.external}]]
        for security, external, merged in [('success', 'success', True), ('failure', 'success', False), ('success', 'pending', False)]:
            fake = Fake(security, external)
            result = {'status': 'pr-open', 'number': 1, 'head-sha': SHA}
            checked_merge(fake, 'example/app', result)
            self.assertEqual(bool(fake.mutations), merged)
            if merged:
                self.assertEqual(fake.mutations[0]['sha'], SHA)

    def test_generated_workflows_validate_pushes_and_use_immutable_policy(self):
        repo = Repository('app', 'main', (Project('workflow', 'github-actions', '.', timeout_minutes=5),))
        generated = [dependency_caller(repo, 'example', SHA), security_caller('example', SHA), release_caller('example', SHA)]
        self.assertIn('pr-author: dependabot[bot]', generated[0])
        self.assertNotIn('policy-push', generated[0])
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, text in enumerate(generated):
                path = Path(directory) / f'workflow-{index}.yml'
                path.write_text(text)
                paths.append(str(path))
                yaml.safe_load(text)
            result = subprocess.run(['actionlint', *paths], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_existing_pr_with_unrelated_files_is_never_rewritten(self):
        class Fake:
            def api(self, endpoint):
                if '/git/ref/' in endpoint:
                    return {'object': {'sha': SHA}}
                if '/files?' in endpoint:
                    return [{'filename': 'application.py'}]
                return [{'base': {'ref': 'main'}, 'head': {'sha': 'b' * 40}, 'number': 1}]
            def file(self, *args):
                return None
        with self.assertRaisesRegex(PolicyError, 'unrelated'):
            ensure_pr(Fake(), 'example/app', 'main', {'.github/workflows/central-security.yml': 'workflow'}, True)

    def test_protection_without_checks_preserves_existing_reviews_and_flags(self):
        class Fake:
            def __init__(self): self.mutations = []
            def api(self, endpoint, method='GET', payload=None):
                if method == 'GET':
                    raise AssertionError('Protection must not wait for successful checks')
                self.mutations.append((method, payload))
                return {}
        protection = {'required_status_checks': None, 'enforce_admins': {'enabled': True},
                      'restrictions': None, 'required_linear_history': {'enabled': True},
                      'required_pull_request_reviews': {'required_approving_review_count': 2,
                          'require_code_owner_reviews': True, 'url': 'unused'}}
        fake = Fake()
        with patch('scripts.sync_fleet.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(protection), '')):
            self.assertEqual(configure_protection(fake, 'example/app', 'main'), 'protected')
        method, payload = fake.mutations[0]
        self.assertEqual(method, 'PUT')
        self.assertTrue(payload['enforce_admins'])
        self.assertTrue(payload['required_linear_history'])
        self.assertEqual(payload['required_pull_request_reviews']['required_approving_review_count'], 2)
        self.assertNotIn('url', payload['required_pull_request_reviews'])

    def test_unprotected_branch_requires_both_checks_without_execution_evidence(self):
        client = Mock()
        response = subprocess.CompletedProcess([], 1, '', 'Branch not protected (HTTP 404)')
        with patch('scripts.sync_fleet.subprocess.run', return_value=response):
            self.assertEqual(configure_protection(client, 'example/app', 'main'), 'protected')
        client.api.assert_called_once_with('repos/example/app/branches/main/protection', 'PUT', {
            'required_status_checks': {'strict': False, 'checks': [
                {'context': 'dependency-gate', 'app_id': 15368},
                {'context': 'scan / secret-scanning', 'app_id': 15368}]},
            'enforce_admins': False, 'required_pull_request_reviews': None, 'restrictions': None})

    def test_protection_corrects_app_bindings_preserves_unrelated_checks_and_is_idempotent(self):
        for app_id in (None, -1, 42, 15368):
            with self.subTest(app_id=app_id):
                protection = {'required_status_checks': {'strict': True, 'checks': [
                    {'context': 'application', 'app_id': 42},
                    {'context': 'dependency-gate', 'app_id': app_id}],
                    'contexts': ['application', 'dependency-gate', 'legacy-deployment']}}
                client = Mock()
                def response(*args, **kwargs):
                    return subprocess.CompletedProcess([], 0, json.dumps(protection), '')
                def update(endpoint, method, payload):
                    self.assertEqual(method, 'PATCH')
                    self.assertTrue(endpoint.endswith('/protection/required_status_checks'))
                    protection['required_status_checks'] = payload
                client.api.side_effect = update
                with patch('scripts.sync_fleet.subprocess.run', side_effect=response):
                    configure_protection(client, 'example/app', 'main')
                    configure_protection(client, 'example/app', 'main')
                self.assertEqual(client.api.call_count, 1)
                self.assertEqual(protection['required_status_checks'], {'strict': True, 'checks': [
                    {'context': 'application', 'app_id': 42},
                    {'context': 'dependency-gate', 'app_id': 15368},
                    {'context': 'legacy-deployment', 'app_id': -1},
                    {'context': 'scan / secret-scanning', 'app_id': 15368}]})

    def test_fleet_protects_policy_and_application_before_configuration_failures(self):
        project = Project('workflow', 'github-actions', '.', timeout_minutes=5)
        repositories = tuple(Repository(name, 'main', (project,)) for name in ('.github', 'app'))
        inventory = Inventory(1, repositories)
        discovered = [DiscoveredRepository(repo.name, 'main', False, (project,)) for repo in repositories]
        client = Mock()
        client.file.return_value = None
        client.api.side_effect = PolicyError('Configuration unavailable')
        with patch('scripts.sync_fleet.discover_repositories', return_value=discovered), \
             patch('scripts.sync_fleet.configure_protection', return_value='protected') as protect:
            report = synchronize('example', inventory, SHA, client, apply=True)
        self.assertEqual(protect.call_args_list, [
            call(client, 'example/.github', 'main'), call(client, 'example/app', 'main')])
        self.assertEqual(report['repositories'][0]['protection'], 'protected')
        self.assertEqual(report['errors'], [{'repository': 'app', 'error': 'Configuration unavailable'}])
        self.assertFalse(report['synchronization-complete'])


if __name__ == '__main__':
    unittest.main()
