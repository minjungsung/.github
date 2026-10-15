"""Generate reviewed caller changes; publish only with both explicit flags."""

import argparse
import difflib
import json
import hashlib
from pathlib import Path
import re
import tempfile
import subprocess
from typing import Sequence

from lib.github_client import CommandRunner, _default_runner
from lib.models import PolicyError, load_inventory
from scripts.render_callers import INVENTORY_PATH, render_caller

OWNER = 'minjungsung'
BRANCH = 'chore/dependency-merge-safeguard'
TITLE = 'ci: gate Dependabot merges on validation'
CALLER = '.github/workflows/dependency-gate.yml'
LEGACY = '.github/workflows/dependabot-auto-merge.yml'
# Exact reviewed standalone template: custom files require a separate review.
LEGACY_CONTENT = """name: Dependabot Auto-Merge

on:
  pull_request:

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - name: Auto-approve Dependabot PR
        run: gh pr review --approve "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Auto-merge patch/minor updates
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
"""


def _byte_runner(command):
    return subprocess.run(command, capture_output=True, check=False)


def main(argv: Sequence[str] | None = None, *, runner: CommandRunner = _default_runner,
         inventory_path: Path = INVENTORY_PATH, byte_runner=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--policy-sha', required=True)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--reviewed-legacy-sha256', help='reviewed SHA-256 authorizing only exact legacy workflow removal')
    parser.add_argument('--push', action='store_true')
    parser.add_argument('--create-pr', action='store_true')
    args = parser.parse_args(argv)
    if args.reviewed_legacy_sha256 is not None and re.fullmatch('[0-9a-f]{64}', args.reviewed_legacy_sha256) is None:
        raise PolicyError('reviewed legacy SHA-256 must be 64 lowercase hexadecimal characters')
    if args.push != args.create_pr:
        raise PolicyError('publication requires both --push and --create-pr')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', args.repository) or args.repository in {'.', '..'}:
        raise PolicyError('repository must be a safe inventory name')
    repository = load_inventory(inventory_path).repository(args.repository)
    generated = render_caller(repository, args.policy_sha)
    def reviewed_legacy(content):
        digest = hashlib.sha256(content).hexdigest()
        return digest == args.reviewed_legacy_sha256 if args.reviewed_legacy_sha256 else content == LEGACY_CONTENT.encode()
    full_name = f'{OWNER}/{repository.name}'
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    root = workspace / repository.name

    def run(command):
        result = runner(command)
        if result.returncode:
            raise PolicyError(f'command failed with exit code {result.returncode}: {command[0]}')
        return result.stdout

    def git(*arguments):
        return run(['git', '-C', str(root), *arguments])

    def blob_bytes(base):
        command = ['git', '-C', str(root), 'show', f'{base}:{LEGACY}']
        response = (byte_runner or (_byte_runner if runner is _default_runner else runner))(command)
        if response.returncode or not isinstance(response.stdout, bytes):
            raise PolicyError('immutable legacy blob requires a byte-preserving command runner')
        return response.stdout

    def result(status, pr_url=None):
        print(json.dumps({'repository': full_name, 'policy_sha': args.policy_sha,
                          'status': status, 'pr_url': pr_url}, sort_keys=True))
        return 0

    if root.is_symlink():
        raise PolicyError('workspace repository must not be a symlink')
    if not root.exists():
        run(['gh', 'repo', 'clone', full_name, str(root)])
    if root.is_symlink() or not (root / '.git').exists():
        raise PolicyError('workspace repository must be an explicit Git clone')
    # Verify clone identity, including reused workspaces.
    remote = git('remote', 'get-url', 'origin').strip()
    expected_urls = {f'https://github.com/{full_name}.git', f'https://github.com/{full_name}',
                     f'git@github.com:{full_name}.git', f'ssh://git@github.com/{full_name}.git'}
    if remote not in expected_urls:
        raise PolicyError('clone origin differs from inventoried repository')
    if args.push:
        push_urls = git('remote', 'get-url', '--push', '--all', 'origin').splitlines()
        if len(push_urls) != 1 or push_urls[0] not in expected_urls:
            raise PolicyError('effective push URLs differ from the single reviewed destination')
    if git('status', '--porcelain', '--untracked-files=all').strip():
        raise PolicyError('dirty clone: use a fresh workspace or review existing changes')
    live = json.loads(run(['gh', 'repo', 'view', full_name, '--json', 'defaultBranchRef']))
    if live.get('defaultBranchRef', {}).get('name') != repository.default_branch:
        raise PolicyError('live default branch differs from inventory')
    workflows = root / '.github/workflows'
    if workflows.is_symlink() or (root / '.github').is_symlink():
        raise PolicyError('workflow directory must not be a symlink')
    changes = {}
    if workflows.exists():
        for path in sorted(workflows.iterdir()):
            if path.suffix not in {'.yml', '.yaml'}:
                continue
            if path.is_symlink() or not path.is_file():
                raise PolicyError('workflow files must be regular files')
            text = path.read_text()
            relative = path.relative_to(root).as_posix()
            if relative == LEGACY and reviewed_legacy(path.read_bytes()):
                changes[relative] = (text, None)
            elif relative == LEGACY:
                raise PolicyError('legacy workflow differs from exact reviewed removal bytes; review required')
            elif relative != CALLER and ('gh pr merge' in text.lower() or
                    re.search(r'auto[-_ ]?merge|merge[-_ ]?pull[-_ ]?requests?|enablepullrequestautomerge',
                              text.lower())):
                raise PolicyError('independent auto-merge workflow requires review before rollout')
    current = git('branch', '--show-current').strip()
    prs = json.loads(run(['gh', 'pr', 'list', '--repo', full_name, '--head', f'{OWNER}:{BRANCH}',
                          '--state', 'open', '--json', 'url,baseRefName,headRefName,headRefOid']))
    if not isinstance(prs, list) or len(prs) > 1:
        raise PolicyError('expected at most one rollout PR')
    if prs:
        pr = prs[0]
        if current not in {repository.default_branch, BRANCH} or pr.get('baseRefName') != repository.default_branch or pr.get('headRefName') != BRANCH:
            raise PolicyError('existing rollout PR requires review')
        git('fetch', 'origin', repository.default_branch, BRANCH)
        head = f'origin/{BRANCH}'
        if git('rev-parse', head).strip() != pr.get('headRefOid'):
            raise PolicyError('existing PR head changed; rerun after review')
        files = set(git('diff', '--name-only', f'origin/{repository.default_branch}...{head}').splitlines())
        if not files or not files <= {CALLER, LEGACY} or git('show', f'{head}:{CALLER}') != generated or git('ls-tree', '--name-only', head, '--', LEGACY).strip():
            raise PolicyError('existing rollout PR differs from requested policy; review before rerun')
        if LEGACY in files:
            base = git('merge-base', f'origin/{repository.default_branch}', head).strip()
            if re.fullmatch(r'[0-9a-f]{40}', base) is None or not reviewed_legacy(blob_bytes(base)):
                raise PolicyError('deleted legacy workflow differs from reviewed merge-base bytes')
        return result('existing-pr', pr['url'])
    if args.reviewed_legacy_sha256 and not (root / LEGACY).is_file():
        raise PolicyError('reviewed legacy hash supplied but workflow is absent')
    if current != repository.default_branch:
        raise PolicyError('clone must be on the reviewed default branch')
    git('fetch', 'origin', repository.default_branch)
    if git('rev-parse', 'HEAD').strip() != git('rev-parse', f'origin/{repository.default_branch}').strip():
        raise PolicyError('default clone is stale or has local commits')
    if args.push and (git('ls-remote', '--heads', 'origin', BRANCH).strip() or git('branch', '--list', BRANCH).strip()):
        raise PolicyError('rollout branch already exists without an open PR; review before retry')
    target = root / CALLER
    before = target.read_text() if target.exists() else ''
    if before != generated:
        changes[CALLER] = (before, generated)
    if not changes:
        return result('unchanged')
    for path, (old, new) in sorted(changes.items()):
        print(''.join(difflib.unified_diff(old.splitlines(True), (new or '').splitlines(True),
                                         fromfile=path, tofile=path if new is not None else '/dev/null')), end='')
    if args.push:
        git('switch', '-c', BRANCH)
    for path, (_, text) in changes.items():
        destination = root / path
        if text is None:
            destination.unlink()
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
    print(git('status', '--short'), end='')
    if not args.push:
        return result('dry-run')
    paths = sorted(changes)
    git('add', '--', *paths)
    if set(git('diff', '--name-only', '--cached').splitlines()) != set(paths):
        raise PolicyError('staged changes differ from exact reviewed rollout files')
    git('commit', '-m', TITLE)
    git('push', '-u', 'origin', BRANCH)
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / 'pr-body.md'
        body.write_text(f'Gate Dependabot merges on strict dependency validation.\n\nPolicy commit: `{args.policy_sha}`.\n\nGenerated from reviewed repository inventory. Major updates remain manual.\n')
        url = run(['gh', 'pr', 'create', '--repo', full_name, '--base', repository.default_branch,
                   '--head', BRANCH, '--title', TITLE, '--body-file', str(body)]).strip()
    if not url.startswith(f'https://github.com/{full_name}/pull/'):
        raise PolicyError('PR creation returned an unexpected URL; inspect the published branch')
    return result('published', url)


if __name__ == '__main__':
    raise SystemExit(main())
