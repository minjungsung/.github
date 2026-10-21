"""Discover owned repositories and reconcile central automation through checked PRs."""
import argparse
import base64
from dataclasses import replace
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

import yaml

from lib.github_client import GitHubClient
from lib.models import Inventory, PolicyError, load_inventory
from scripts.audit_repositories import discover_repositories, inventory_dict, _merge_repository
from scripts.render_callers import render_caller

BRANCH = 'automation/central-policy'
TITLE = 'ci: synchronize central security and dependency automation'
SOURCE_REPOSITORY = 'repo-template'


class FleetClient(GitHubClient):
    def api(self, endpoint, method='GET', payload=None):
        if payload is None:
            return self._json(['gh', 'api', endpoint])
        result = subprocess.run(['gh', 'api', '--method', method, endpoint, '--input', '-'],
                                input=json.dumps(payload), capture_output=True, text=True)
        if result.returncode:
            raise PolicyError(f'GitHub API request failed: {method} {endpoint}')
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def file(self, repository, path, ref):
        result = subprocess.run(['gh', 'api', f'repos/{repository}/contents/{path}?ref={quote(ref, safe="")}'],
                                capture_output=True, text=True)
        if result.returncode:
            if 'HTTP 404' in result.stderr:
                return None
            raise PolicyError(f'Cannot read {path} from {repository}')
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get('encoding') != 'base64':
            raise PolicyError('Expected a regular text file')
        return base64.b64decode(value['content']).decode()


def reconciled_inventory(inventory, discovered, aliases):
    reviewed = {r.name: r for r in inventory.repositories}
    repositories = []
    issues = []
    for item in discovered:
        if item.archived or item.name == SOURCE_REPOSITORY:
            continue
        if not item.default_branch:
            issues.append({'repository': item.name, 'status': 'discovery-blocked',
                           'reasons': list(item.ambiguities)})
            continue
        if item.name == '.github' and item.name in reviewed:
            repositories.append(reviewed[item.name])
            continue
        if item.ambiguities:
            issues.append({'repository': item.name, 'status': 'manual-application',
                           'reasons': list(item.ambiguities)})
            supported = tuple(p for p in item.projects if p.ecosystem != 'gradle' or p.gradle_wrapper)
            if not supported:
                from lib.models import Project
                supported = (Project('github-actions', 'github-actions', '.', timeout_minutes=5),)
            item = replace(item, projects=supported, auto_merge_enabled=False)
        old_name = aliases.get(item.name, item.name)
        old = reviewed.get(old_name)
        if old:
            repo, problems = _merge_repository(replace(old, name=item.name), item)
            # Discovery drift requires manual dependency acceptance, but security
            # scanners and the checked configuration PR can still be installed.
            if problems:
                issues.append({'repository': item.name, 'status': 'inventory-drift', 'reasons': list(problems)})
                repo = replace(repo, auto_merge_enabled=False)
        else:
            repo = replace(item_to_repository(item), auto_merge_enabled=item.auto_merge_enabled and not item.ambiguities)
            projects = []
            for project in repo.projects:
                if project.ecosystem == 'npm':
                    project = replace(project, runtime_version='24')
                projects.append(project)
            repo = replace(repo, projects=tuple(projects))
        repositories.append(repo)
    return Inventory(1, tuple(sorted(repositories, key=lambda r: r.name))), issues


def item_to_repository(item):
    from lib.models import Repository
    return Repository(item.name, item.default_branch, item.projects,
                      item.deployment_workflows, item.auto_merge_enabled)


def security_caller(owner, policy_sha):
    return f'''name: Security Scanning
on:
  push:
  pull_request:
  schedule:
    - cron: '0 2 * * 0'
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: security-scanning-${{{{ github.ref }}}}
  cancel-in-progress: true
jobs:
  scan:
    uses: {owner}/.github/.github/workflows/secret-scanning.yml@{policy_sha}
    with:
      policy-ref: {policy_sha}
'''


def release_caller(owner, policy_sha):
    return f'''name: Release
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      version:
        description: 'Semantic version to release (for example v1.0.0)'
        required: true
        type: string
permissions:
  contents: read
jobs:
  release:
    permissions:
      contents: write
      checks: read
    uses: {owner}/.github/.github/workflows/release.yml@{policy_sha}
    with:
      version: ${{{{ github.event.inputs.version || github.ref_name }}}}
'''


def dependency_caller(repository, owner, policy_sha):
    generated = render_caller(repository, policy_sha)
    generated = re.sub(r'uses: [^\s]+/\.github/\.github/workflows/dependency-validation.yml@',
                       f'uses: {owner}/.github/.github/workflows/dependency-validation.yml@', generated)
    # Validate applications on configuration PRs and default-branch pushes too.
    generated = generated.replace("${{ github.event.pull_request.user.login || 'policy-push' }}",
                                  "dependabot[bot]")
    return generated


def dependabot_config(existing, repository):
    value = yaml.safe_load(existing) if existing else {'version': 2, 'updates': []}
    if not isinstance(value, dict) or value.get('version') != 2 or not isinstance(value.get('updates'), list):
        raise PolicyError('Dependabot configuration requires a version 2 updates list')
    updates = value['updates']
    pairs = {(u['package-ecosystem'], u.get('directory')) for u in updates if isinstance(u, dict)}
    wanted = {('github-actions', '/')}
    for project in repository.projects:
        ecosystem = {'npm': 'npm', 'python-requirements': 'pip', 'python-pyproject': 'pip', 'gradle': 'gradle'}.get(project.ecosystem)
        if ecosystem:
            wanted.add((ecosystem, '/' if project.path == '.' else '/' + project.path))
    for ecosystem, directory in sorted(wanted - pairs):
        # Existing multi-directory entries already manage matching directories.
        if any(u.get('package-ecosystem') == ecosystem and directory in u.get('directories', []) for u in updates):
            continue
        updates.append({'package-ecosystem': ecosystem, 'directory': directory,
                        'schedule': {'interval': 'weekly'}, 'open-pull-requests-limit': 10})
    return yaml.safe_dump(value, sort_keys=False)


def ensure_pr(client, full, base_branch, files, apply):
    base = client.api(f'repos/{full}/git/ref/heads/{quote(base_branch, safe="")}')['object']['sha']
    changed = {path: text for path, text in files.items() if client.file(full, path, base) != text}
    if not changed:
        return {'status': 'current', 'base-sha': base}
    pulls = client.api(f'repos/{full}/pulls?state=open&head={quote(full.split("/")[0]+":"+BRANCH,safe="")}&per_page=100')
    if len(pulls) > 1:
        raise PolicyError('Multiple central policy pull requests found')
    parent = base
    if pulls:
        pull = pulls[0]
        if pull['base']['ref'] != base_branch:
            raise PolicyError('Existing policy PR has an unexpected base')
        parent = pull['head']['sha']
        existing_files = client.api(f'repos/{full}/pulls/{pull["number"]}/files?per_page=100')
        if len(existing_files) >= 100 or not {f['filename'] for f in existing_files} <= set(files):
            raise PolicyError('Existing policy PR contains unrelated changes')
        if all(client.file(full, path, parent) == text for path, text in changed.items()):
            return {'status': 'pr-open', 'url': pull['html_url'], 'number': pull['number'], 'head-sha': parent}
    if not apply:
        return {'status': 'preview', 'files': sorted(changed)}
    # Use the existing head as parent; updates remain fast-forward and preserve
    # any default-branch movement for GitHub's protected merge path to reconcile.
    parent_tree = client.api(f'repos/{full}/git/commits/{parent}')['tree']['sha']
    tree = client.api(f'repos/{full}/git/trees', 'POST', {'base_tree': parent_tree,
        'tree': [{'path': p, 'mode': '100644', 'type': 'blob', 'content': t} for p, t in changed.items()]})
    commit = client.api(f'repos/{full}/git/commits', 'POST',
                        {'message': TITLE, 'tree': tree['sha'], 'parents': [parent]})
    if pulls:
        client.api(f'repos/{full}/git/refs/heads/{BRANCH}', 'PATCH', {'sha': commit['sha'], 'force': False})
        pull = pulls[0]
    else:
        ref = subprocess.run(['gh', 'api', f'repos/{full}/git/ref/heads/{BRANCH}'], capture_output=True, text=True)
        if ref.returncode == 0:
            # A merged prior rollout can leave its branch behind. Delete only
            # when GitHub confirms a merged PR for this exact branch head.
            previous = client.api(f'repos/{full}/pulls?state=closed&head={quote(full.split("/")[0]+":"+BRANCH,safe="")}&per_page=100')
            branch_sha = json.loads(ref.stdout)['object']['sha']
            if not any(p.get('merged_at') and p['head']['sha'] == branch_sha for p in previous):
                raise PolicyError('Orphaned policy branch requires review')
            client.api(f'repos/{full}/git/refs/heads/{BRANCH}', 'DELETE', {})
        client.api(f'repos/{full}/git/refs', 'POST', {'ref': f'refs/heads/{BRANCH}', 'sha': commit['sha']})
        pull = client.api(f'repos/{full}/pulls', 'POST', {'title': TITLE, 'head': BRANCH, 'base': base_branch,
            'body': 'Install or update centrally maintained dependency validation, secret scanning, and release automation.\n\nDefault-branch application validation and required checks remain enforced. Existing deployment workflows and customized release workflows are preserved.'})
    return {'status': 'pr-open', 'url': pull['html_url'], 'number': pull['number'], 'head-sha': commit['sha']}


def checked_merge(client, full, result, required=('dependency-gate', 'scan / secret-scanning')):
    if result.get('status') != 'pr-open':
        return
    number = result['number']
    detail = client.api(f'repos/{full}/pulls/{number}')
    head = detail['head']['sha']
    if head != result['head-sha'] or detail.get('mergeable') is not True:
        return
    pages = client._json(['gh', 'api', '--paginate', '--slurp', f'repos/{full}/commits/{head}/check-runs?filter=latest&per_page=100'])
    checks = [c for page in pages for c in page['check_runs']]
    if not all(any(c['name'] == name and c.get('app', {}).get('id') == 15368 and c['conclusion'] == 'success' for c in checks) for name in required):
        return
    if any(c.get('head_sha') != head or c['status'] != 'completed' or c['conclusion'] not in ('success', 'skipped', 'neutral') for c in checks):
        return
    statuses = client._json(['gh', 'api', '--paginate', '--slurp', f'repos/{full}/commits/{head}/statuses?per_page=100'])
    latest = {}
    for page in statuses:
        for status in page:
            latest.setdefault(status['context'], status)
    if any(s['state'] != 'success' for s in latest.values()):
        return
    fresh = client.api(f'repos/{full}/pulls/{number}')
    if fresh['head']['sha'] != head:
        raise PolicyError('Configuration PR changed before merge')
    response = client.api(f'repos/{full}/pulls/{number}/merge', 'PUT', {'sha': head, 'merge_method': 'squash'})
    if response.get('merged'):
        result['status'] = 'merged'


def configure_repository(client, full, metadata):
    client.api(f'repos/{full}', 'PATCH', {'allow_auto_merge': True,
        **({'security_and_analysis': {k: {'status': 'enabled'} for k in
            ('secret_scanning', 'secret_scanning_push_protection')}} if not metadata.get('private') else {})})
    client.api(f'repos/{full}/vulnerability-alerts', 'PUT', {})
    client.api(f'repos/{full}/automated-security-fixes', 'PUT', {})
    permissions = client.api(f'repos/{full}/actions/permissions/workflow')
    client.api(f'repos/{full}/actions/permissions/workflow', 'PUT',
               {'default_workflow_permissions': permissions['default_workflow_permissions'],
                'can_approve_pull_request_reviews': True})


def configure_protection(client, full, branch):
    sha = client.api(f'repos/{full}/git/ref/heads/{quote(branch, safe="")}')['object']['sha']
    checks = client.api(f'repos/{full}/commits/{sha}/check-runs?filter=latest&per_page=100')
    if checks.get('total_count', 0) > len(checks['check_runs']):
        raise PolicyError('Default branch checks response is incomplete')
    contexts = ['dependency-gate', 'scan / secret-scanning']
    if not all(any(c['name'] == name and c.get('app', {}).get('id') == 15368 and c['head_sha'] == sha and c['conclusion'] == 'success' for c in checks['check_runs']) for name in contexts):
        return 'await-default-validation'
    endpoint = f'repos/{full}/branches/{quote(branch, safe="")}/protection'
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True)
    if result.returncode:
        if 'HTTP 404' not in result.stderr:
            raise PolicyError('Branch protection is unavailable')
        client.api(endpoint, 'PUT', {'required_status_checks': {'strict': False,
            'checks': [{'context': name, 'app_id': 15368} for name in contexts]},
            'enforce_admins': False, 'required_pull_request_reviews': None, 'restrictions': None})
    else:
        protection = json.loads(result.stdout)
        existing = protection.get('required_status_checks') or {'strict': False, 'checks': []}
        required = list(existing.get('checks', []))
        present = {c['context'] for c in required}
        required.extend({'context': name, 'app_id': 15368} for name in contexts if name not in present)
        if required != existing.get('checks', []):
            client.api(endpoint + '/required_status_checks', 'PATCH', {'strict': existing['strict'], 'checks': required})
    return 'protected'


def synchronize(owner, inventory, policy_sha, client, apply=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', owner) or not re.fullmatch('[0-9a-f]{40}', policy_sha):
        raise PolicyError('Invalid policy owner or immutable commit')
    discovered = discover_repositories(client, owner)
    live_names = {d.name for d in discovered}
    aliases = {}
    for repo in inventory.repositories:
        if repo.name in live_names:
            continue
        response = subprocess.run(['gh', 'api', f'repos/{owner}/{repo.name}'], capture_output=True, text=True)
        if response.returncode == 0:
            renamed = json.loads(response.stdout)
            if renamed.get('owner', {}).get('login') == owner and renamed['name'] in live_names:
                aliases[renamed['name']] = repo.name
    proposed, issues = reconciled_inventory(inventory, discovered, aliases)
    report = {'schema-version': 1, 'policy-sha': policy_sha, 'repositories': issues, 'errors': []}
    for repo in proposed.repositories:
        if repo.name == '.github':
            continue
        full = f'{owner}/{repo.name}'
        try:
            metadata = client.api(f'repos/{full}')
            if repo.name not in {r.name for r in inventory.repositories} and repo.name not in aliases:
                enriched = []
                for project in repo.projects:
                    if project.ecosystem == 'npm':
                        manifest_path = project.manifest if project.path == '.' else f'{project.path}/{project.manifest}'
                        manifest = json.loads(client.file(full, manifest_path, repo.default_branch))
                        scripts = manifest.get('scripts', {})
                        project = replace(project, test_command='npm test' if 'test' in scripts else None,
                            build_command='npm run package' if 'package' in scripts and 'build' not in scripts else None)
                    enriched.append(project)
                repo = replace(repo, projects=tuple(enriched))
                proposed = replace(proposed, repositories=tuple(repo if r.name == repo.name else r for r in proposed.repositories))
            dependabot_path = '.github/dependabot.yml'
            existing_config = client.file(full, dependabot_path, repo.default_branch)
            alternate_config = client.file(full, '.github/dependabot.yaml', repo.default_branch)
            if existing_config is None and alternate_config is not None:
                dependabot_path, existing_config = '.github/dependabot.yaml', alternate_config
            files = {'.github/workflows/dependency-gate.yml': dependency_caller(repo, owner, policy_sha),
                     '.github/workflows/central-security.yml': security_caller(owner, policy_sha),
                     dependabot_path: dependabot_config(existing_config, repo)}
            release_path = '.github/workflows/release.yml'
            current_release = client.file(full, release_path, repo.default_branch)
            if current_release is None or f'{owner}/.github/.github/workflows/release.yml@' in current_release:
                files[release_path] = release_caller(owner, policy_sha)
            if apply:
                configure_repository(client, full, metadata)
            outcome = ensure_pr(client, full, repo.default_branch, files, apply)
            if apply:
                checked_merge(client, full, outcome)
                outcome['protection'] = configure_protection(client, full, repo.default_branch)
            report['repositories'].append({'repository': repo.name, 'auto-merge-enabled': repo.auto_merge_enabled, **outcome})
        except (PolicyError, KeyError, TypeError, ValueError) as error:
            report['errors'].append({'repository': repo.name, 'error': str(error)})
    full = f'{owner}/.github'
    files = {'dependency-policy/repositories.json': json.dumps(inventory_dict(proposed), indent=2) + '\n'}
    try:
        report['inventory'] = ensure_pr(client, full, 'main', files, apply)
        if apply:
            checked_merge(client, full, report['inventory'], required=('dependency-gate', 'Policy CI', 'scan / secret-scanning'))
    except PolicyError as error:
        report['errors'].append({'repository': '.github', 'error': str(error)})
    report['synchronization-complete'] = not report['errors'] and all(r['status'] == 'current' and r.get('protection') == 'protected' for r in report['repositories'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--policy-sha', required=True)
    parser.add_argument('--inventory', type=Path, default=Path(__file__).resolve().parents[1] / 'repositories.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    report = synchronize(args.owner, load_inventory(args.inventory), args.policy_sha, FleetClient(), args.apply)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Repositories:', len(report['repositories']), 'API errors:', len(report['errors']))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
