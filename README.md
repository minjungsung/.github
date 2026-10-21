# Central GitHub automation

This repository replaces the standalone repository template as the source of
dependency validation, secret scanning, and verified release automation.

- **Fleet Synchronization** discovers active owned repositories every six hours,
  follows repository renames, adds missing Dependabot ecosystems, and opens or
  updates configuration pull requests pinned to an immutable policy commit.
- **Dependency Maintenance** checks dependency update pull requests every six
  hours, refreshes stale branches, and merges supported updates only after strict
  application validation and GitHub protection pass.
- **Secret Scanning** runs Gitleaks and TruffleHog in connected repositories on
  pushes, pull requests, and weekly schedules. Scanner binaries have fixed
  versions and verified checksums. Raw secrets are never published as evidence.
- **Verified Release** creates semantic-version releases and generated release
  notes only for checked commits reachable from the default branch. Existing
  customized release and deployment workflows remain in place.
- **Git History Security Audit** scans accessible repositories weekly without
  executing their code and retains sanitized provenance for triage.

Configuration changes merge only after the current commit's checks pass. Required
dependency and secret checks are added after the merged default-branch commit
passes them. Existing required checks and review requirements are preserved.

See [fleet automation](docs/fleet-automation.md) for setup and operating limits,
[dependency gate](docs/dependency-gate.md) for validation and recovery, and
[dependency maintenance](dependency-policy/MAINTENANCE.md) for unattended access.
