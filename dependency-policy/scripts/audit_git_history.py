"""Audit all accessible owned repositories without executing repository code."""
import argparse
import concurrent.futures
import json
import os
import subprocess
import tempfile
from pathlib import Path


def run(command, **kwargs):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def scan_repository(repo, root, config):
    name = repo['name']
    result = {'repository': name, 'private': repo['private'], 'archived': repo['archived']}
    mirror = root / 'mirrors' / name
    mirror.parent.mkdir(exist_ok=True)
    if repo.get('size') == 0:
        return dict(result, status='empty', findings=[])
    cloned = run(['gh', 'repo', 'clone', repo['full_name'], str(mirror), '--', '--mirror'])
    if cloned.returncode:
        return dict(result, status='clone-unavailable', findings=[])
    pulled = run(['git', '-C', str(mirror), '-c', 'core.hooksPath=/dev/null', 'fetch', 'origin',
                  '+refs/pull/*/head:refs/audit-pulls/*'])
    result['pull-refs-fetched'] = pulled.returncode == 0
    result['commit-count'] = int(run(['git', '-C', str(mirror), 'rev-list', '--all', '--count'], text=True).stdout)
    report = root / (name + '.raw.json')
    scan = run(['gitleaks', 'git', str(mirror), '--log-opts=--all --full-history',
                '--config', str(config), '--gitleaks-ignore-path', str(root / 'no-ignores'),
                '--ignore-gitleaks-allow', '--redact=100', '--max-archive-depth=2',
                '--report-format=json', '--report-path', str(report), '--no-banner', '--timeout=1200'])
    if scan.returncode not in (0, 1) or not report.exists():
        return dict(result, status='scan-incomplete', findings=[])
    raw = json.loads(report.read_text())
    # Keep provenance only: no secrets, matched lines, commit authors or messages.
    result['findings'] = [{k: finding.get(k) for k in ('RuleID', 'File', 'StartLine', 'Commit')}
                          for finding in raw]
    report.unlink()
    result['finding-count'] = len(raw)
    result['status'] = 'scanned' if pulled.returncode == 0 else 'pull-history-incomplete'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    query = run(['gh', 'api', 'user/repos?affiliation=owner&per_page=100', '--paginate', '--slurp'], text=True)
    if query.returncode:
        raise SystemExit('Repository discovery unavailable')
    repositories = [repo for page in json.loads(query.stdout) for repo in page]
    results = []
    with tempfile.TemporaryDirectory(prefix='history-audit-') as temporary:
        root = Path(temporary)
        (root / 'no-ignores').mkdir()
        config = root / 'scanner.toml'
        config.write_text('[extend]\nuseDefault = true\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(scan_repository, repo, root, config): repo['name'] for repo in repositories}
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                except Exception:
                    result = {'repository': futures[future], 'status': 'scan-error', 'findings': []}
                results.append(result)
                print(result['repository'], result['status'], 'findings', len(result['findings']), flush=True)
                (args.output / 'history-audit.json').write_text(json.dumps({'repositories': results}, indent=2) + '\n')
    incomplete = [r for r in results if r['status'] not in ('scanned', 'empty')]
    findings = sum(len(r['findings']) for r in results)
    (args.output / 'summary.md').write_text(
        '# Git history secret audit\n\n'
        f'Accessible repositories: {len(results)}. Incomplete scans: {len(incomplete)}. '
        f'Detections requiring triage: {findings}.\n\n'
        'All advertised branches, tags, and fetched pull request heads were scanned. '
        'Deleted server objects, forks, release assets, LFS objects, issues, comments, '
        'Actions logs/artifacts, and external deployments are outside this scan. '
        'An empty detection set does not establish absence of vulnerabilities. '
        'Detections are not dismissed and exposed credentials must be revoked at their issuer.\n')
    if incomplete:
        raise SystemExit('History coverage is incomplete; evidence preserved')


if __name__ == '__main__':
    main()
