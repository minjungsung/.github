from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from lib.models import PolicyError
from scripts.render_callers import render_caller
from lib.models import load_inventory
from scripts.render_callers import INVENTORY_PATH
from scripts.rollout import BRANCH, CALLER, LEGACY, LEGACY_CONTENT, main

SHA = 'a' * 40


class FakeRunner:
    def __init__(self, dirty=False, branch='main', legacy=LEGACY_CONTENT, prs=None, push_urls=None, base_legacy=LEGACY_CONTENT):
        self.commands = []
        self.dirty = dirty
        self.branch = branch
        self.legacy = legacy
        self.prs = prs or []
        self.body = None
        self.push_urls = push_urls
        self.base_legacy = base_legacy

    def __call__(self, command):
        command = list(command)
        self.commands.append(command)
        output = ''
        if command[:3] == ['gh', 'repo', 'clone']:
            root = Path(command[4])
            (root / '.git').mkdir(parents=True)
            (root / LEGACY).parent.mkdir(parents=True)
            if self.legacy is not None:
                (root / LEGACY).write_text(self.legacy)
            (root / '.github/workflows/deploy.yml').write_text('name: Deploy\n')
        elif command[:3] == ['gh', 'repo', 'view']:
            output = json.dumps({'defaultBranchRef': {'name': 'main'}})
        elif command[:3] == ['gh', 'pr', 'list']:
            output = json.dumps(self.prs)
        elif command[:3] == ['gh', 'pr', 'create']:
            self.body = Path(command[command.index('--body-file') + 1]).read_text()
            output = 'https://github.com/minjungsung/Algorithm/pull/1\n'
        elif command[0] == 'git':
            args = command[3:]
            if args == ['remote', 'get-url', '--push', '--all', 'origin']:
                output = self.push_urls if self.push_urls is not None else 'https://github.com/minjungsung/' + Path(command[2]).name + '.git\n'
            elif args == ['remote', 'get-url', 'origin']:
                output = 'https://github.com/minjungsung/' + Path(command[2]).name + '.git\n'
            elif args[:1] == ['status']:
                output = ' M package.json\n' if self.dirty else ''
            elif args == ['branch', '--show-current']:
                output = self.branch + '\n'
            elif args[:1] == ['show']:
                output = self.base_legacy if args[1].endswith(':' + LEGACY) else render_caller(load_inventory(INVENTORY_PATH).repository('Algorithm'), SHA)
            elif args[:1] == ['merge-base']:
                output = SHA + '\n'
            elif args[:1] == ['rev-parse']:
                output = SHA + '\n'
            elif args[:2] == ['diff', '--name-only']:
                output = CALLER + '\n' + LEGACY + '\n'
            elif args[:1] == ['ls-remote']:
                output = ''
        return subprocess.CompletedProcess(command, 0, output, '')


class RolloutTest(unittest.TestCase):
    def run_rollout(self, runner, workspace, *flags):
        with redirect_stdout(io.StringIO()) as out:
            main(['--repository', 'Algorithm', '--policy-sha', SHA,
                  '--workspace', str(workspace), *flags], runner=runner)
        return out.getvalue()

    def test_dry_run_only_generates_reviewed_workflows_and_prints_diff(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner()
            output = self.run_rollout(runner, Path(temp))
            root = Path(temp) / 'Algorithm'
            self.assertTrue((root / CALLER).is_file())
            self.assertFalse((root / LEGACY).exists())
            self.assertEqual((root / '.github/workflows/deploy.yml').read_text(), 'name: Deploy\n')
            self.assertIn('+name: Dependency Gate', output)
            self.assertFalse(any(c[0] == 'git' and c[3] in {'switch', 'add', 'commit', 'push'} for c in runner.commands))
            self.assertFalse(any(c[:3] == ['gh', 'pr', 'create'] for c in runner.commands))

    def test_dirty_clone_and_wrong_branch_are_refused(self):
        for runner in (FakeRunner(dirty=True), FakeRunner(branch='feature')):
            with TemporaryDirectory() as temp, self.assertRaises(PolicyError):
                self.run_rollout(runner, Path(temp))
            self.assertFalse(any(c[:3] == ['gh', 'pr', 'create'] for c in runner.commands))

    def test_publication_requires_both_flags_before_clone(self):
        for flag in ('--push', '--create-pr'):
            runner = FakeRunner()
            with TemporaryDirectory() as temp, self.assertRaises(PolicyError):
                self.run_rollout(runner, Path(temp), flag)
            self.assertEqual(runner.commands, [])

    def test_publication_stages_only_specific_files_and_creates_one_pr(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner()
            output = self.run_rollout(runner, Path(temp), '--push', '--create-pr')
            git_args = [c[3:] for c in runner.commands if c[0] == 'git']
            self.assertIn(['switch', '-c', BRANCH], git_args)
            self.assertIn(['add', '--', *sorted([CALLER, LEGACY])], git_args)
            self.assertIn(['push', '-u', 'origin', BRANCH], git_args)
            creates = [c for c in runner.commands if c[:3] == ['gh', 'pr', 'create']]
            self.assertEqual(len(creates), 1)
            self.assertIn('ci: gate Dependabot merges on validation', creates[0])
            self.assertIn('\n\n', runner.body)
            self.assertIn('"pr_url":', output)

    def test_unknown_legacy_or_independent_auto_merge_is_blocked(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner(legacy=LEGACY_CONTENT + '# custom\n')
            with self.assertRaisesRegex(PolicyError, 'review'):
                self.run_rollout(runner, Path(temp), '--push', '--create-pr')
            self.assertTrue((Path(temp) / 'Algorithm' / LEGACY).exists())

    def test_existing_matching_pr_is_returned_without_duplicate_publication(self):
        pr = {'url': 'https://github.com/minjungsung/Algorithm/pull/1',
              'baseRefName': 'main', 'headRefName': BRANCH, 'headRefOid': SHA}
        with TemporaryDirectory() as temp:
            runner = FakeRunner(prs=[pr])
            output = self.run_rollout(runner, Path(temp), '--push', '--create-pr')
            self.assertIn('existing-pr', output)
            self.assertFalse(any(c[:3] == ['gh', 'pr', 'create'] for c in runner.commands))
            self.assertFalse(any(c[0] == 'git' and c[3] in {'switch', 'commit', 'push'} for c in runner.commands))

    def test_existing_pr_does_not_bypass_unknown_workflow_review(self):
        pr = {'url': 'https://github.com/minjungsung/Algorithm/pull/1',
              'baseRefName': 'main', 'headRefName': BRANCH, 'headRefOid': SHA}
        with TemporaryDirectory() as temp:
            runner = FakeRunner(legacy=LEGACY_CONTENT + '# custom\n', prs=[pr])
            with self.assertRaisesRegex(PolicyError, 'review'):
                self.run_rollout(runner, Path(temp), '--push', '--create-pr')

    def test_dry_run_rerun_refuses_dirty_generated_worktree(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner()
            self.run_rollout(runner, Path(temp))
            runner.dirty = True
            with self.assertRaisesRegex(PolicyError, 'dirty clone'):
                self.run_rollout(runner, Path(temp))

    def test_unknown_independent_workflow_blocks_publication(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner()
            self.run_rollout(runner, Path(temp))
            root = Path(temp) / 'Algorithm'
            (root / '.github/workflows/custom.yml').write_text('run: gh pr merge --auto\n')
            with self.assertRaisesRegex(PolicyError, 'review'):
                self.run_rollout(runner, Path(temp), '--push', '--create-pr')

    def test_dangling_root_symlink_rejected_before_clone(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'Algorithm'
            root.symlink_to(Path(temp) / 'missing')
            runner = FakeRunner()
            with self.assertRaisesRegex(PolicyError, 'symlink'):
                self.run_rollout(runner, Path(temp))
            self.assertEqual(runner.commands, [])

    def test_publication_rejects_alternate_or_multiple_push_urls(self):
        expected = 'https://github.com/minjungsung/Algorithm.git\n'
        for urls in ('https://github.com/example/other.git\n', expected + expected, ''):
            with TemporaryDirectory() as temp:
                runner = FakeRunner(push_urls=urls)
                with self.assertRaisesRegex(PolicyError, 'push'):
                    self.run_rollout(runner, Path(temp), '--push', '--create-pr')
                self.assertFalse(any(c[0] == 'git' and c[3] in {'switch', 'add', 'commit', 'push'} for c in runner.commands))

    def test_existing_pr_custom_deleted_legacy_is_rejected(self):
        pr = {'url': 'https://github.com/minjungsung/Algorithm/pull/1',
              'baseRefName': 'main', 'headRefName': BRANCH, 'headRefOid': SHA}
        with TemporaryDirectory() as temp:
            runner = FakeRunner(prs=[pr], legacy=None, base_legacy=LEGACY_CONTENT + '# custom\n')
            with self.assertRaisesRegex(PolicyError, 'deleted legacy'):
                self.run_rollout(runner, Path(temp), '--push', '--create-pr')

    def test_unreviewed_merge_actions_and_scripts_are_blocked(self):
        for content in ('uses: pascalgn/automerge-action@v1\n',
                        'run: node scripts/auto-merge.js\n',
                        'uses: peter-evans/enable-pull-request-automerge@v3\n'):
            with TemporaryDirectory() as temp:
                runner = FakeRunner()
                self.run_rollout(runner, Path(temp))
                (Path(temp) / 'Algorithm/.github/workflows/custom.yml').write_text(content)
                with self.assertRaisesRegex(PolicyError, 'review'):
                    self.run_rollout(runner, Path(temp), '--push', '--create-pr')

    def test_reviewed_hash_authorizes_only_exact_legacy_bytes(self):
        content = LEGACY_CONTENT + '# reviewed custom workflow\n'
        digest = hashlib.sha256(content.encode()).hexdigest()
        for supplied, succeeds in ((digest, True), ('0' * 64, False)):
            with TemporaryDirectory() as temp:
                runner = FakeRunner(legacy=content)
                if succeeds:
                    self.run_rollout(runner, Path(temp), '--reviewed-legacy-sha256', supplied)
                    self.assertFalse((Path(temp) / 'Algorithm' / LEGACY).exists())
                else:
                    with self.assertRaises(PolicyError):
                        self.run_rollout(runner, Path(temp), '--reviewed-legacy-sha256', supplied)

    def test_existing_pr_authorized_legacy_deletion_matches_reviewed_hash(self):
        content = LEGACY_CONTENT + '# reviewed custom workflow\n'
        digest = hashlib.sha256(content.encode()).hexdigest()
        pr = {'url': 'https://github.com/minjungsung/Algorithm/pull/1',
              'baseRefName': 'main', 'headRefName': BRANCH, 'headRefOid': SHA}
        with TemporaryDirectory() as temp:
            runner = FakeRunner(prs=[pr], legacy=None, base_legacy=content)
            output = self.run_rollout(runner, Path(temp), '--push', '--create-pr', '--reviewed-legacy-sha256', digest)
            self.assertIn('existing-pr', output)

    def test_sha_validation_happens_before_commands(self):
        runner = FakeRunner()
        with TemporaryDirectory() as temp, self.assertRaises(ValueError):
            main(['--repository', 'Algorithm', '--policy-sha', 'main', '--workspace', temp], runner=runner)
        self.assertEqual(runner.commands, [])

    def test_disabled_auto_merge_omits_job(self):
        with TemporaryDirectory() as temp:
            runner = FakeRunner()
            with redirect_stdout(io.StringIO()):
                main(['--repository', 'Undead-Survivor', '--policy-sha', SHA, '--workspace', temp], runner=runner)
            self.assertNotIn('dependabot-auto-merge:', (Path(temp) / 'Undead-Survivor' / CALLER).read_text())


if __name__ == '__main__':
    unittest.main()
