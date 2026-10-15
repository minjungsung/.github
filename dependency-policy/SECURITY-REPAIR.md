# Automated security repair

The central repair workflow selects one vulnerable repository per run, prioritizing critical and high alerts. It requires a reviewed automatic policy and an actual application adapter. Manual, empty, unclassified and workflow-only repositories are recorded by maintenance but are not silently accepted for application repairs.

Each advisory-number set has at most three attempts. An attempt branch is reserved before the model starts, so failed model or validation runs consume the same bounded budget. An existing open repair PR prevents duplicates. A changed advisory set receives a new fingerprint.

Planning and publication use the dedicated GitHub credential. The application repair job has no repository write credential. The pinned OpenAI Codex Action uses a workspace permission profile and drops privileged execution; it receives the OpenAI API key through its API proxy. The model cannot publish or merge.

The model updates vulnerable dependencies or proposes compatible maintained replacements. It cannot change workflows, tests, security/lint configuration, credentials, deployment policy or agent instructions. After repair, the trusted policy validates the patch boundary and executes existing project commands. Publication verifies the default-branch SHA, creates a commit through GitHub Git APIs without running target code, creates a draft PR, applies `human-only` before marking it ready, and leaves independent hosted checks and review required.

Compatibility-changing model repairs are not automatically merged by the existing Dependabot-author-only controller. A separately reviewed acceptance path is required before enabling unattended model repair merges. This first implementation deliberately preserves that review boundary; it is not complete universal automatic remediation.

Configure `COMPANY_MODEL_API_KEY` and `COMPANY_MODEL_RESPONSES_ENDPOINT` as central Actions secrets, optionally `COMPANY_MODEL_CA_PEM` for the gateway issuing/root CA certificates already trusted by the operator, and `SECURITY_REPAIR_MODEL` as a repository variable. The endpoint must expose an authenticated Responses API with valid TLS; certificate verification is never disabled. The gateway credential is held by a root-owned loopback relay and is not passed to application preparation, validation, publication, or the model process. The pinned Action API proxy receives only an ephemeral relay key. This extra relay supports enterprise bearer token formats that the pinned proxy rejects. The relay forwards only authenticated Responses POST requests, preserves streaming, verifies upstream TLS, and suppresses request logging. This uses the configured enterprise model gateway rather than a personal OpenAI API key or ChatGPT login. Usage is charged or metered by that gateway.

Run `Model Gateway Check` before a live repair canary. It verifies a real model response on a GitHub-hosted runner without executing application code or receiving the repository maintenance token. Scheduled model execution remains disabled until `SECURITY_REPAIR_ENABLED=true`; workflow dispatch allows a controlled repair canary. Both workflows run in GitHub without requiring a local workstation to stay online.

Remaining acceptance work includes a successful real model canary, independent review of generated repairs, exact runtime/service parity for every adapter, immutable repair provenance and closure evidence, all manual repository adapters, post-merge rescan confirmation, and a reviewed automatic acceptance policy for model-authored code. Never claim an unpatched advisory or unavailable API result is resolved.

## Cloud connection evidence

The initial GitHub-hosted canary rejected the enterprise token alphabet before connecting to the gateway. The loopback relay addresses that incompatibility. Subsequent canaries reached the relay, but upstream connection failed with `gaierror`: the configured gateway hostname is not resolvable from GitHub-hosted runners. Local authenticated Responses requests succeeded. These results establish local gateway usability, not external cloud reachability.

Scheduled repair execution remains disabled. To use this gateway without an operator workstation, provide a continuously available runner with authorized access to the enterprise DNS/network, or an enterprise-supported externally reachable Responses endpoint. Do not bypass network controls, disable TLS verification, or expose the credential in repository files. A company-network runner must be ephemeral and dedicated to repair jobs: the pinned Action drops sudo and executes untrusted application code, so a shared corporate host is unsuitable.

Canary evidence: `Model Gateway Check` runs `38695662220` (token alphabet rejection), `38695884321` (upstream connection failure), and `38696316310` (redacted DNS failure category). None completed model execution. This is an explicit blocked connection state, not successful unattended remediation.
