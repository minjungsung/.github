# Fleet automation

## Source migration

The standalone repository template is superseded by this central policy
repository. Its security scanners, weekly Dependabot updates, automatic dependency
merging, and tagged releases are implemented as centrally maintained workflows.
Source commit: `56656549c6d9a023ac82a08c8a1ac6153bbe9d33`.

| Portable source reference | SHA-256 |
| --- | --- |
| `repo-template:.github/workflows/security-secrets.yml` | `99c7d9f7d4b54613da9802a1b355d0c0608096a9a3a5caaf7e84c9b221844d06` |
| `repo-template:.github/workflows/release.yml` | `edd29a6735c7eb5cb31c2386bc54b265491e71fb14e6de2dc5802e9c88437e3e` |
| `repo-template:.github/dependabot.yml` | `8cb2bf6b79ee92f6a6c0c6f3a741eea573bee8256752c2011761e119c935dee4` |

The obsolete template may be archived after the central workflows and at least
one connected repository pass their hosted checks. Archiving retains provenance;
it does not remove any installed caller workflows.

## Configure unattended access

Use a dedicated GitHub App or maintenance token configured as described in
`dependency-policy/MAINTENANCE.md`. Fleet synchronization additionally needs
repository administration access to enable security settings, configure Actions
PR approval, and add required checks. The credential must reach all managed
repositories, including private and newly created repositories. It receives no
permission to bypass protections. Never save an interactive CLI credential as an
Actions secret.

## Operation

Run **Fleet Synchronization** manually from the Actions page after a policy release
or repository creation; its schedule also runs every six hours. It performs these
steps for active source repositories:

1. Discover manifests, follow repository rename redirects, and preserve reviewed
   runtime versions and commands. Remove entries that no longer exist from the
   proposed inventory. Unsupported or ambiguous applications retain manual
   dependency acceptance.
2. Enable dependency alerts, dependency security updates, automatic merging, and
   Actions PR approval. Public repositories also enable native secret scanning
   and push protection. Private repositories use the workflow scanners regardless
   of native GitHub security product availability.
3. Open or update `automation/central-policy` with exact managed files. Add missing
   Dependabot ecosystems without replacing existing schedules or groups. Install
   a centrally pinned dependency caller and secret-scanning caller. Add a release
   caller only when no customized release workflow occupies that path.
4. Merge the configuration PR only after its current GitHub Actions dependency
   and secret checks and all other emitted checks and statuses pass. GitHub still
   enforces existing review and branch protection rules. Failed checks, unresolved
   reviews, orphan branches, and unrelated PR changes remain visible blockers.
5. Observe successful dependency and secret checks on the actual default-branch
   commit, then add required checks while preserving existing protections.
6. Open a central inventory update PR, and merge it only after Policy CI and the
   dependency and secret checks pass.

Newly enrolled dependency callers validate applications on all PRs and default
branch pushes. Existing deployments are not rewritten. Policy SHA updates use
the same checked PR path; changes to the central source do not silently change
old pinned callers.

Push scans cover the new commits; PR scans cover the PR range. Weekly scans
revisit repository history. TruffleHog scans Git objects without downloading LFS
payloads; the full history audit also excludes LFS payloads. Missing historical
LFS server objects therefore do not prevent scanning the available Git history.

The scheduled controller pins the most recent commit that changed workflow or
policy code. Inventory-only and documentation-only commits do not start another
fleet-wide policy promotion.

The synchronization job reports API failures as failures. Pending enrollment PRs
are recorded as pending, not accepted coverage. Dependency Maintenance separately
continues to fail when unresolved vulnerability alerts, unsupported applications,
or incomplete dependency acceptance remain. A successful synchronization run
therefore establishes that the controller ran, not that all applications are
secure or all pending updates have merged.

## Local preview

Use an isolated environment and authenticated GitHub CLI:

```sh
python3 -m venv .policy-venv
.policy-venv/bin/python -m pip install -r dependency-policy/requirements.txt
PYTHONPATH=dependency-policy .policy-venv/bin/python \
  dependency-policy/scripts/sync_fleet.py --owner OWNER \
  --policy-sha REVIEWED_40_CHARACTER_COMMIT_SHA --output sync-preview.json
```

The preview reads GitHub and writes local evidence. Add `--apply` to configure
repositories and publish checked configuration PRs. Inspect the Actions summary
and `fleet-synchronization-evidence` artifact for pending rollout and protection.
