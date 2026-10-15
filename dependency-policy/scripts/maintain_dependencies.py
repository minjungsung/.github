"""Scheduled fleet maintenance: exact-head checks, bounded rebases and alert evidence."""
import argparse
import json
import re
from pathlib import Path

from lib.models import PolicyError, load_inventory
from scripts.reconcile_dependabot_prs import ReconciliationClient


class MaintenanceClient(ReconciliationClient):
    def mutate(self, endpoint, method, payload):
        # Use typed CLI fields without shell evaluation or untrusted commands.
        command = ['gh', 'api', '--method', method, endpoint]
        for key, value in payload.items():
            command.extend(['-F' if isinstance(value, bool) else '-f',
                            f'{key}={str(value).lower() if isinstance(value, bool) else value}'])
        return self._json(command)


def trusted_checks(checks, head):
    """Require application validation and the stable gate from GitHub Actions."""
    latest = {}
    for check in checks:
        if check.get('head_sha') != head or check.get('app', {}).get('id') != 15368:
            continue
        name = check.get('name', '')
        if name not in latest or check.get('id', 0) > latest[name].get('id', 0):
            latest[name] = check
    gate = latest.get('dependency-gate')
    projects = [c for name, c in latest.items()
                if name.startswith('validate-dependencies / validate-projects (')]
    return bool(gate and projects and all(c.get('status') == 'completed' and
                c.get('conclusion') == 'success' for c in [gate, *projects]))


def plan_pr(detail, checks, repository_enabled):
    head = detail.get('head', {}).get('sha')
    if detail.get('user', {}).get('login') != 'dependabot[bot]':
        return 'ignore', 'Only authenticated Dependabot authors are supported'
    if not isinstance(head, str) or not re.fullmatch('[0-9a-f]{40}', head):
        raise PolicyError('invalid immutable PR head')
    if not repository_enabled:
        return 'manual-repository', 'Application validation is not yet accepted'
    if detail.get('draft') or detail.get('state') != 'open':
        return 'wait', 'PR is draft or no longer open'
    if detail.get('mergeable_state') == 'behind':
        return 'refresh', 'Update once against the current base; require fresh checks'
    if not trusted_checks(checks, head):
        return 'validation-blocked', 'Exact head lacks successful strict application validation'
    # Approval/metadata routing stays in the audited repository workflow.
    if not detail.get('auto_merge'):
        return 'await-auto-merge', 'Verified repository workflow must enable auto-merge'
    return 'await-github-merge', 'GitHub must enforce required checks and reviews'


def maintain(owner, inventory, client, apply=False):
    report = {'schema-version': 1, 'repositories': [], 'coverage-complete': True,
              'mutations': [], 'automatic-resolution-guaranteed': False}
    reviewed = {r.name: r for r in inventory.repositories}
    for repo in client.list_repositories(owner):
        if repo.get('isArchived'): continue
        name = repo['name']; full = repo['nameWithOwner']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or full != f'{owner}/{name}':
            raise PolicyError('unexpected repository identity')
        entry = {'repository': name, 'alerts': [], 'pull-requests': []}
        report['repositories'].append(entry)
        policy = reviewed.get(name)
        if policy is None:
            entry['policy-status'] = 'unclassified'
            report['coverage-complete'] = False
        else:
            entry['policy-status'] = 'automatic' if policy.auto_merge_enabled else 'manual'
            if not policy.auto_merge_enabled: report['coverage-complete'] = False
        try:
            alerts = client.pages(f'repos/{full}/dependabot/alerts?state=open')
            if not all(isinstance(a.get('number'), int) and isinstance(a.get('dependency'), dict) and isinstance(a.get('security_vulnerability'), dict) for a in alerts):
                raise PolicyError('invalid vulnerability alert response')
            entry['alerts'] = [{'number': a['number'], 'severity': a.get('security_advisory', {}).get('severity'),
                               'package': a.get('dependency', {}).get('package', {}).get('name'),
                               'patched-version': a.get('security_vulnerability', {}).get('first_patched_version'),
                               'url': a.get('html_url'), 'status': 'open-remediation-required'} for a in alerts]
            if alerts: report['coverage-complete'] = False
        except (PolicyError, KeyError, TypeError, AttributeError):
            entry['alert-status'] = 'unavailable'
            report['coverage-complete'] = False
        try:
            pulls = client.pages(f'repos/{full}/pulls?state=open')
        except PolicyError:
            entry['pr-status'] = 'unavailable'; report['coverage-complete'] = False
            continue
        for pr in pulls:
            if pr.get('user', {}).get('login') != 'dependabot[bot]': continue
            if type(pr.get('number')) is not int or pr['number'] < 1:
                entry['pr-status'] = 'invalid-response'; report['coverage-complete'] = False
                continue
            row = {'number': pr['number'], 'url': pr.get('html_url')}
            entry['pull-requests'].append(row)
            try:
                detail = client._json(['gh', 'api', f'repos/{full}/pulls/{pr["number"]}'])
                head = detail['head']['sha']
                checks = client._json(['gh', 'api', f'repos/{full}/commits/{head}/check-runs?filter=latest&per_page=100'])
                if checks.get('total_count', 0) > len(checks.get('check_runs', [])):
                    raise PolicyError('check response incomplete')
                action, reason = plan_pr(detail, checks.get('check_runs', []), bool(policy and policy.auto_merge_enabled))
                row.update({'head-sha': head, 'status': action, 'reason': reason})
                if action not in {'ignore', 'await-github-merge'}: report['coverage-complete'] = False
                if apply and action == 'refresh':
                    fresh = client._json(['gh', 'api', f'repos/{full}/pulls/{pr["number"]}'])
                    if fresh['head']['sha'] != head: raise PolicyError('head changed before mutation')
                    result = client.mutate(f'repos/{full}/pulls/{pr["number"]}/update-branch', 'PUT', {'expected_head_sha': head})
                    row['refresh-status'] = result.get('message', 'requested')
                    report['mutations'].append({'repository': name, 'number': pr['number'], 'action': 'refresh', 'expected-head-sha': head})
            except (PolicyError, KeyError, TypeError, ValueError):
                row['status'] = 'incomplete-discovery'; report['coverage-complete'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--inventory', type=Path, default=Path(__file__).resolve().parents[1] / 'repositories.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', args.owner): raise PolicyError('invalid owner')
    report = maintain(args.owner, load_inventory(args.inventory), MaintenanceClient(), args.apply)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Fleet evidence recorded; coverage complete:', report['coverage-complete'])
    return 0 if report['coverage-complete'] else 1


if __name__ == '__main__': raise SystemExit(main())
