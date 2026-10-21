import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from lib.models import Inventory, Project, Repository, PolicyError
from scripts.audit_repositories import DiscoveredRepository
from scripts.sync_fleet import (checked_merge, dependabot_config, dependency_caller,
                                ensure_pr, reconciled_inventory, release_caller, security_caller)

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


if __name__ == '__main__':
    unittest.main()
