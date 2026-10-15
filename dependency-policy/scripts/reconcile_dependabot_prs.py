"""Read-only exact-head Dependabot reconciliation; remediation requires review."""
import argparse
from dataclasses import asdict, dataclass
import json
import hashlib
import re

from lib.github_client import GitHubClient
from lib.models import PolicyError
from scripts.configure_protection import CHECK_CONTEXT


@dataclass(frozen=True)
class ReconciliationDecision:
    number: int
    url: str
    head_sha: str
    state: str
    reason: str
    evidence: dict | None = None


def classify_pr(pr: dict) -> ReconciliationDecision:
    if pr.get('author') not in {'dependabot[bot]', 'app/dependabot'}:
        raise PolicyError('only verified Dependabot PR authors are supported')
    if not isinstance(pr.get('head_sha'), str) or not re.fullmatch('[0-9a-f]{40}', pr['head_sha']):
        raise PolicyError('PR requires an immutable head SHA')
    def decision(state, reason):
        return ReconciliationDecision(pr['number'], pr['url'], pr['head_sha'], state, reason, pr.get('metadata_evidence'))
    update = pr.get('update_type')
    if update == 'major': return decision('manual-major', 'Major updates require manual review')
    if update not in {'patch', 'minor'}: return decision('manual-unknown', 'Verified patch/minor metadata is unavailable')
    evidence = pr.get('closure_evidence', {})
    if isinstance(evidence, dict) and evidence.get('reviewed') is True and evidence.get('kind') in {'duplicate', 'superseded', 'upstream-incompatible', 'withdrawn'} and evidence.get('reason') and re.match(r'https://', evidence.get('url', '')):
        return decision('close-with-reason', evidence['kind'] + ': ' + evidence['reason'] + ' — ' + evidence['url'])
    if pr.get('behind') is True or pr.get('mergeable') is False:
        return decision('request-rebase', 'Head is behind or conflicted; wait for a new head SHA after rebase')
    gate = pr.get('gate')
    if not isinstance(gate, dict) or gate.get('head_sha') != pr['head_sha'] or gate.get('status') != 'completed' or gate.get('app') != 'github-actions':
        return decision('await-current-checks', 'Current head lacks a completed trusted dependency gate')
    if gate.get('conclusion') != 'success':
        return decision('remediate', 'Current strict dependency gate failed; reproduce install/test/build failure')
    if pr.get('required_checks_pass') is not True:
        return decision('investigate-checks', 'Other required checks are pending, failed, or unavailable')
    if pr.get('mergeable') is not True:
        return decision('await-mergeability', 'GitHub mergeability is not yet known')
    return decision('merge-eligible', pr.get('external_blocker') or 'Required gate and checks succeeded on the exact head; gated auto-merge may proceed')


def verified_body_update_type(detail):
    """Accept canonical Dependabot version pairs only, never arbitrary semver text."""
    if detail.get('user', {}).get('login') != 'dependabot[bot]':
        return None
    body = detail.get('body')
    if not isinstance(body, str): return None
    pairs = re.findall(r'^Bumps (?:\[[^\]\n]+\]\(https://[^)\n]+\)|[A-Za-z0-9@_./-]+) from ([0-9]+\.[0-9]+\.[0-9]+) to ([0-9]+\.[0-9]+\.[0-9]+)\.(?:\s|$)', body, re.MULTILINE)
    # Grouped prose and prereleases require reviewed metadata instead.
    if len(pairs) != 1: return None
    before, after = (tuple(map(int, version.split('.'))) for version in pairs[0])
    if after <= before: return None
    if after[0] != before[0]: return 'major'
    if after[1] != before[1]: return 'minor'
    return 'patch'


class ReconciliationClient(GitHubClient):
    def pages(self, endpoint):
        rows = []
        for page in range(1, 1001):
            value = self._json(['gh', 'api', f'{endpoint}{"&" if "?" in endpoint else "?"}per_page=100&page={page}'])
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise PolicyError('paginated GitHub response must contain objects')
            rows.extend(value)
            if len(value) < 100: return rows
        raise PolicyError('GitHub pagination did not terminate')

    def collect(self, owner):
        records = []
        for repo in self.pages(f'users/{owner}/repos?type=owner'):
            if repo.get('archived') is True: continue
            name = repo.get('full_name')
            if not isinstance(name, str) or name.split('/')[0] != owner:
                raise PolicyError('unexpected repository owner')
            for entry in self.pages(f'repos/{name}/pulls?state=open'):
                if entry.get('user', {}).get('login') != 'dependabot[bot]': continue
                detail = self._json(['gh', 'api', f'repos/{name}/pulls/{entry["number"]}'])
                if not isinstance(detail, dict) or detail.get('user', {}).get('login') != 'dependabot[bot]' or detail.get('state') != 'open':
                    raise PolicyError('PR changed during reconciliation; rerun')
                head = detail.get('head', {}).get('sha')
                if not isinstance(head, str) or not re.fullmatch('[0-9a-f]{40}', head):
                    raise PolicyError('invalid PR head SHA')
                gate_runs = []
                seen = 0
                for page in range(1, 1001):
                    checks = self._json(['gh', 'api', f'repos/{name}/commits/{head}/check-runs?filter=latest&per_page=100&page={page}'])
                    if not isinstance(checks, dict) or not isinstance(checks.get('check_runs'), list) or type(checks.get('total_count')) is not int:
                        raise PolicyError('invalid check-runs response')
                    runs = checks['check_runs']; seen += len(runs)
                    gate_runs.extend(run for run in runs if run.get('name') == CHECK_CONTEXT)
                    if seen >= checks['total_count']: break
                    if not runs: raise PolicyError('incomplete check pagination')
                else: raise PolicyError('check pagination did not terminate')
                gate = None
                if len(gate_runs) == 1:
                    run = gate_runs[0]; app = run.get('app', {})
                    trusted = app.get('slug') == 'github-actions' and app.get('owner', {}).get('login') == 'github'
                    gate = {'head_sha': run.get('head_sha'), 'status': run.get('status'), 'conclusion': run.get('conclusion'), 'app': 'github-actions' if trusted else None}
                # Canonical body pairs are trusted only with the verified bot author
                # and exact head rechecked after complete check collection.
                graphql = self._json(['gh', 'pr', 'view', str(entry['number']), '--repo', name,
                                      '--json', 'author,headRefOid,mergeStateStatus,statusCheckRollup,reviewDecision'])
                if graphql.get('headRefOid') != head or graphql.get('author', {}).get('login') not in {'app/dependabot', 'dependabot[bot]'}:
                    raise PolicyError('PR head or author changed during check collection')
                response = self._runner(['gh', 'pr', 'checks', str(entry['number']), '--repo', name, '--required', '--json', 'bucket,name'])
                if response.returncode not in {0, 1, 8}:
                    raise PolicyError('required check lookup failed')
                try:
                    required = json.loads(response.stdout)
                except (TypeError, json.JSONDecodeError) as error:
                    raise PolicyError('invalid required checks JSON') from error
                if not isinstance(required, list): raise PolicyError('required checks must be an array')
                records.append({'number': detail['number'], 'url': detail['html_url'], 'head_sha': head,
                                'author': 'dependabot[bot]', 'update_type': verified_body_update_type(detail), 'mergeable': detail.get('mergeable'),
                                'behind': graphql.get('mergeStateStatus') == 'BEHIND', 'gate': gate,
                                'required_checks_pass': bool(required) and all(check.get('bucket') == 'pass' for check in required),
                                'metadata_evidence': {'source': 'authenticated-dependabot-canonical-body',
                                                      'head_sha': head,
                                                      'body_sha256': hashlib.sha256((detail.get('body') or '').encode()).hexdigest()},
                                'external_blocker': 'required review approval' if graphql.get('reviewDecision') == 'REVIEW_REQUIRED' else None})
        return sorted(records, key=lambda pr: (pr['url'], pr['number']))


def main(argv=None, *, client=None, mutation_handler=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--request-rebase', action='store_true')
    mode.add_argument('--apply-remediation', action='store_true')
    args = parser.parse_args(argv)
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]*', args.owner): raise PolicyError('invalid owner')
    if not args.check and mutation_handler is None:
        raise PolicyError('mutation mode requires an explicitly supplied reviewed remediation handler')
    records = (client or ReconciliationClient()).collect(args.owner)
    decisions = [classify_pr(pr) for pr in records]
    if not args.check:
        for decision in decisions:
            if args.request_rebase and decision.state == 'request-rebase': mutation_handler('request-rebase', decision)
            elif args.apply_remediation and decision.state in {'remediate', 'close-with-reason'}: mutation_handler('apply-remediation', decision)
    print(json.dumps([asdict(decision) for decision in decisions], indent=2, sort_keys=True))
    return int(any(decision.state not in {'merge-eligible', 'manual-major', 'manual-unknown'} for decision in decisions))


if __name__ == '__main__': raise SystemExit(main())
