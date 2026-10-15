# Continuous dependency maintenance

The central `Dependency Maintenance` workflow runs every six hours and can be dispatched manually. It discovers all active repositories, records missing inventory coverage and open Dependabot alerts, and refreshes stale Dependabot branches using an expected immutable head SHA. It never dismisses alerts, bypasses checks, changes review requirements, or merges unvalidated updates. After canonical Dependabot version metadata, complete exact-head application matrix coverage and required checks pass, the trusted controller can merge by exact SHA with its workflow-capable credential. GitHub continues to enforce reviews and protection. Independently confirmed optional Vercel24-hour quota failures remain deployment blockers; required quota checks still block merging.

Actual metadata verification and strict application validation remain in each repository's audited caller. The controller accepts only canonical authenticated version pairs for its additional merge path; grouped or unknown metadata remains blocked. A new head needs new validation. The controller reports manual policies, missing credentials, incomplete API results and unresolved alerts as failures. A successful gate without successful application matrix jobs cannot authorize dependency acceptance.

## Authentication

Prefer a dedicated GitHub App installed on all managed repositories. Configure the central repository variable `DEPENDENCY_APP_ID` and Actions secret `DEPENDENCY_APP_PRIVATE_KEY`. The portable manifest in `config/github-app-manifest.json` requests contents, pull requests, workflow and Actions write access plus checks, statuses and vulnerability alert read access. It does not request branch-protection administration or bypass permission. Setup is incomplete until the installation permissions and repository access are verified.

Alternatively, use a dedicated token in the central Actions secret `DEPENDENCY_MAINTENANCE_TOKEN` with equivalent repository access. Do not use a developer's interactive CLI OAuth credential for unattended automation. Never include credential values in reports, command output, pull requests or chat. GitHub does not reveal stored Actions secrets through its API.

The scheduled controller runs only trusted default-branch code; it never checks out or executes a dependency PR with its privileged credential. Repository secrets are withheld from Dependabot pull-request workflows, so cross-repository authenticated maintenance belongs in this trusted controller.

## Limits and acceptance

This controller provides detection and bounded branch refresh. It does not implement arbitrary compatibility repairs or promise to fix every future vulnerability. Unpatched dependencies, unsupported application runtimes and external deployment failures still require a reviewed remediation. No universal security-resolution guarantee is made.

Acceptance requires every active repository to have an application validation adapter, automatic policy, enabled security updates, verified credentials, successful real major and security-update samples, and an exercised failure-to-remediation path. New or empty repositories must remain explicitly classified rather than disappear from coverage.
