# Automated security repair

The central repair workflow selects one vulnerable repository per run, prioritizing critical and high alerts. It requires a reviewed automatic policy and an actual application adapter. Manual, empty, unclassified and workflow-only repositories are recorded by maintenance but are not silently accepted for application repairs.

Each advisory-number set has at most three attempts. An attempt branch is reserved before the model starts, so failed model or validation runs consume the same bounded budget. An existing open repair PR prevents duplicates. A changed advisory set receives a new fingerprint.

Planning and publication use the dedicated GitHub credential. The application repair job has no repository write credential. The pinned OpenAI Codex Action uses a workspace permission profile and drops privileged execution; it receives the OpenAI API key through its API proxy. The model cannot publish or merge.

The model updates vulnerable dependencies or proposes compatible maintained replacements. It cannot change workflows, tests, security/lint configuration, credentials, deployment policy or agent instructions. After repair, the trusted policy validates the patch boundary and executes existing project commands. Publication verifies the default-branch SHA, creates a commit through GitHub Git APIs without running target code, creates a draft PR, applies `human-only` before marking it ready, and leaves independent hosted checks and review required.

Compatibility-changing model repairs are not automatically merged by the existing Dependabot-author-only controller. A separately reviewed acceptance path is required before enabling unattended model repair merges. This first implementation deliberately preserves that review boundary; it is not complete universal automatic remediation.

Configure `COMPANY_MODEL_API_KEY` and `COMPANY_MODEL_RESPONSES_ENDPOINT` as central Actions secrets, and `SECURITY_REPAIR_MODEL` as a repository variable. The endpoint must expose an authenticated Responses API with valid TLS; certificate verification is never disabled. The gateway credential is passed only to the pinned Action API proxy, not to application preparation, validation, or publication. This uses the configured enterprise model gateway rather than a personal OpenAI API key or ChatGPT login. Usage is charged or metered by that gateway.

Run `Model Gateway Check` before a live repair canary. It verifies a real model response on a GitHub-hosted runner without executing application code or receiving the repository maintenance token. Scheduled model execution remains disabled until `SECURITY_REPAIR_ENABLED=true`; workflow dispatch allows a controlled repair canary. Both workflows run in GitHub without requiring a local workstation to stay online.

Remaining acceptance work includes a successful real model canary, independent review of generated repairs, exact runtime/service parity for every adapter, immutable repair provenance and closure evidence, all manual repository adapters, post-merge rescan confirmation, and a reviewed automatic acceptance policy for model-authored code. Never claim an unpatched advisory or unavailable API result is resolved.
