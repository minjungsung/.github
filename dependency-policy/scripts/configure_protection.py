"""Plan branch protection changes; mutate only after explicit canary validation."""

import argparse
import base64
import binascii
import copy
import json
from pathlib import Path
import re
from typing import Any, Sequence
from urllib.parse import quote

from lib.github_client import GitHubClient
from lib.models import PolicyError, load_inventory
from scripts.render_callers import render_caller
from scripts.audit_repositories import DEFAULT_OWNER


POLICY_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = POLICY_ROOT / 'repositories.json'
BACKUP_DIRECTORY = POLICY_ROOT / 'reports' / 'protection-backups'
CHECK_CONTEXT = 'Dependency Gate / dependency-gate'
SHA_PATTERN = re.compile(r'[0-9a-f]{40}')
NAME_PATTERN = re.compile(r'[A-Za-z0-9_.-]+')


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError('GitHub response must be a JSON object')
    return value


class ProtectionClient(GitHubClient):
    """Protection API operations through the existing JSON command boundary."""

    def check_runs_page(self, repository: str, sha: str, page: int) -> dict:
        return _object(self._json(['gh', 'api', f'repos/{repository}/commits/{sha}/check-runs?filter=all&per_page=100&page={page}']))

    def default_branch(self, repository: str) -> str:
        branch = _object(self._json(['gh', 'api', f'repos/{repository}'])).get('default_branch')
        if not isinstance(branch, str) or not branch:
            raise PolicyError('repository has no default branch')
        return branch

    def protection(self, repository: str, branch: str) -> dict:
        return _object(self._json(['gh', 'api', f'repos/{repository}/branches/{quote(branch, safe="")}/protection']))

    def caller_text(self, repository: str, branch: str) -> str:
        value = _object(self._json(['gh', 'api', f'repos/{repository}/contents/.github/workflows/dependency-gate.yml?ref={quote(branch, safe="")}']))
        if value.get('type') != 'file' or value.get('encoding') != 'base64' or not isinstance(value.get('content'), str):
            raise PolicyError('default branch caller must be a base64-encoded file')
        try:
            return base64.b64decode(''.join(value['content'].split()), validate=True).decode()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise PolicyError('default branch caller has invalid content') from error

    def update_required_checks(self, repository: str, branch: str, payload: dict) -> dict:
        # A JSON input file preserves arrays and booleans without form coercion.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'required-checks.json'
            path.write_text(json.dumps(payload))
            return _object(self._json(['gh', 'api', '--method', 'PATCH', f'repos/{repository}/branches/{quote(branch, safe="")}/protection/required_status_checks', '--input', str(path)]))


def find_check_context(client: ProtectionClient, repository: str, sha: str) -> str:
    if SHA_PATTERN.fullmatch(sha) is None:
        raise PolicyError('commit SHA must be exactly 40 lowercase hexadecimal characters')
    matches = []
    page = 1
    seen = 0
    while True:
        response = _object(client.check_runs_page(repository, sha, page))
        runs = response.get('check_runs')
        total = response.get('total_count')
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs) or type(total) is not int or total < 0:
            raise PolicyError('invalid check-runs response')
        matches.extend(run for run in runs if run.get('name') == CHECK_CONTEXT)
        seen += len(runs)
        if seen >= total:
            break
        if not runs:
            raise PolicyError('incomplete check-runs pagination')
        page += 1
    if len(matches) != 1:
        raise PolicyError('expected exactly one Dependency Gate / dependency-gate check')
    match = matches[0]
    if match.get('head_sha') != sha or match.get('status') != 'completed' or match.get('conclusion') != 'success':
        raise PolicyError('canary check must be completed successfully on the exact commit SHA')
    return CHECK_CONTEXT


def plan_required_check(current: dict, context: str) -> dict:
    after = copy.deepcopy(_object(current))
    required = after.get('required_status_checks')
    if required is None:
        required = {'strict': False, 'contexts': [], 'checks': []}
        after['required_status_checks'] = required
    _object(required)
    contexts = required.get('contexts', [])
    checks = required.get('checks', [])
    if not isinstance(required.get('strict'), bool) or not isinstance(contexts, list) or not all(isinstance(item, str) for item in contexts) or not isinstance(checks, list) or not all(isinstance(item, dict) and isinstance(item.get('context'), str) for item in checks):
        raise PolicyError('invalid required status checks')
    if context not in contexts and not any(item['context'] == context for item in checks):
        required['contexts'] = [*contexts, context]
        bound_contexts = {item['context'] for item in checks}
        required['checks'] = [
            *checks,
            *({'context': name, 'app_id': -1} for name in [*contexts, context] if name not in bound_contexts),
        ]
    return after


def main(argv: Sequence[str] | None = None, *, client: ProtectionClient | None = None,
         inventory_path: Path = INVENTORY_PATH, backup_directory: Path = BACKUP_DIRECTORY) -> int:
    parser = argparse.ArgumentParser(description='Plan or explicitly apply Dependency Gate branch enforcement')
    parser.add_argument('--repository', required=True, help='repository name in inventory')
    parser.add_argument('--owner', default=DEFAULT_OWNER, help='GitHub repository owner')
    parser.add_argument('--sha', required=True, help='exact successful canary commit SHA')
    parser.add_argument('--policy-sha', help='immutable policy commit SHA; required for apply')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if not NAME_PATTERN.fullmatch(args.owner) or not NAME_PATTERN.fullmatch(args.repository) or args.owner in {'.', '..'} or args.repository in {'.', '..'}:
        raise PolicyError('owner and repository must be safe GitHub names')
    repository = load_inventory(inventory_path).repository(args.repository)
    if args.apply and (args.policy_sha is None or SHA_PATTERN.fullmatch(args.policy_sha) is None):
        raise PolicyError('apply requires an immutable 40-character policy SHA')
    api = client or ProtectionClient()
    full_name = f'{args.owner}/{repository.name}'
    context = find_check_context(api, full_name, args.sha)
    branch = api.default_branch(full_name)
    if branch != repository.default_branch:
        raise PolicyError('live default branch differs from reviewed inventory')
    if args.apply and api.caller_text(full_name, branch) != render_caller(repository, args.policy_sha):
        raise PolicyError('default branch caller does not match the rendered immutable policy pin')
    before = api.protection(full_name, branch)
    after = plan_required_check(before, context)
    print(json.dumps({'before': before, 'after': after}, indent=2, sort_keys=True))
    if not args.apply or before == after:
        return 0
    backup_directory.mkdir(parents=True, exist_ok=True)
    backup = backup_directory / f'{args.owner}-{repository.name}.json'
    # Refuse to overwrite an earlier recovery snapshot, including after API failure.
    with backup.open('x') as stream:
        stream.write(json.dumps(before, indent=2, sort_keys=True) + '\n')
    required = after['required_status_checks']
    payload = {key: required[key] for key in ('strict', 'contexts', 'checks') if key in required}
    api.update_required_checks(full_name, branch, payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
