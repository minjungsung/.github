# Dependency Gate Rollout Evidence

Status: in progress. Acceptance is incomplete. All33 active repositories are inventoried and the authoritative normalized live audit passes. All30 enrolled default branches have exact reviewed callers and require dependency-gate from GitHub Actions App15368. Three failed deployment/audit repositories remain unenrolled.

| Repository | Baseline | Rollout / enforcement | Evidence and limits |
|---|---|---|---|
| .github | not-executed | caller-merged / applied-and-verified | Central caller merged and required dependency-gate protection verified. |
| ai_algorithm_design_and_analysis | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| applied_generative_ai | not-executed | caller-merged / applied-and-verified | Caller merged; CI and gate succeeded; protection applied and verified. |
| applied_machine_learning | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Chatbot | hosted-model-compatibility-pass | manual-caller-merged / applied-and-verified | Reviewed constrained Python3.12 dependency graph, pip check and actual CNN/HDF5 plus SBERT same-process tests passed on Linux. Native import order fixed. Manual caller/release/wiki guards and required dependency gate verified on exactmain. Missing production config, vocabulary and model assets remain unaccepted. |
| course-manager | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| creating_ai_enabled_systems | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| dongle-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| eltango | remediation-merged | caller-merged / applied-and-verified | Caller merged after hosted checks; required dependency-gate protection applied and verified. |
| hackdigest | hosted-pass | caller-merged / applied-and-verified | Strict Node24 worker install, five actual request regressions and build plus Python3.12 install passed. Main-only digest/subscriber and tag release verification guards reviewed. |
| house-scanner-frontend | hosted-ci-pass-deployment-blocked | not-rolled-out / not-observed | Strict hosted Node20 CI passed; PR remains unmerged because Vercel deployment is blocked. |
| Interview | hosted-pass | caller-merged / applied-and-verified | Strict Node20 install/test/build, Python3.12 and actual Ruff checks passed. Reviewed caller, wiki and release guards merged; exact-main required gate verified. |
| introduction_to_algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| jhu_software_concepts | hosted-pass | caller-merged / applied-and-verified | All15 strict projects and existing tests passed with PostgreSQL16. Service-aware caller/wiki/release guards and requiredgate verified. Actual majorbot40 central15-project gate passed at d5910b5a; PR remained open with null autoMergeRequest. |
| KakaoBot | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| KakaoBot-API | hosted-ci-pass-deployment-blocked | caller-pr-open / not-observed | Strict hosted Python3.12 requirements installation passed; test/build explicitly skipped because unconfigured. PR33 remains unmerged because Vercel deployment is blocked. |
| kiro-skills | manual-unaccepted | caller-merged / applied-and-verified | Fail-closed manual caller retains all four audited projects. Bun is unsupported and script suppression remains an explicit application blocker; auto-merge disabled. |
| Leethub | hosted-pass | caller-merged / applied-and-verified | Reviewed remediation PR42 merged after hosted strict CI passed; caller PR43 merged and required dependency-gate protection applied and verified. |
| LingoCast | hosted-pass | caller-merged / applied-and-verified | Actual Node20/Java21 validation and required protection passed. Reviewed metadata canary enabled actual grouped jsoup minor PR118 to pass all3 strict projects and auto-merge at exacthead7094f93e; merged5bd5fe28. Fleet promotion and production acceptance remain separate. |
| medium | hosted-pass | caller-merged / applied-and-verified | Strict Python3.11 install and Pages publication passed; reviewed generated-file main push guard avoids detached-HEAD push and serializes writes. |
| minjungsung | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Nbody | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| portfolio-backend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend-inner | hosted-pass | caller-merged / applied-and-verified | PR45 merged; default-branch CI/gate succeeded; required dependency-gate check bound to Actions App15368. Second apply was idempotent. |
| repo-template | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| senior_eltango | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| shooting-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| TangoDJ | hosted-pass | caller-merged / applied-and-verified | Audited Node24 project; source CI and caller PR2 merged. Default-branch strict CI and gate passed; required dependency-gate protection applied and verified. |
| TangoMBTI | hosted-ci-pass-audit-failed | not-rolled-out / not-observed | PR remains unmerged: unpatched braces GHSA-vfj7-8cjw-p6xm in framework lint dependencies; Tailwind4 migration builds locally but does not clear audit. |
| Undead-Survivor | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| visionRAG | hosted-pass-manual | manual-caller-merged / applied-and-verified | All3 strict projects passed, including original extras and87 actual tests. Main CI/DVC/Docker build and smoke passed. Manual caller/wiki/release guards and requiredgate verified; external GPU/OCR behavior remains manual. |

All21 reviewed automatic-merge policy promotions passed PR checks before merge, then exact main caller bytes, checks and idempotent App15368 enforcement. The original canary also passed its reviewed metadata promotion. Manual callers retain immutable reviewed policies. Ordinary no-op gate success establishes caller execution; actual application validation is recorded separately.

Actual LingoCast minor PR118 passed all3 strict projects and trusted gate at7094f93e; metadata25dd verified jsoup1.17.2→1.23.2 as minor and the auto-merge job completed. GitHub automatically merged5bd5fe28, with no manual merge. Actual JHU major PR40 passed all15 central projects and64 existing tests with PostgreSQL16 atd5910b5a, then remained open with no auto-merge request.

The recorded reconciliation snapshot contains28 open bot PRs:7 manual-major,13 manual-unknown and8 manual-repository. Repository policy overrides any supplied eligibility flags. Conservative unknown metadata remains manual; complete fleet patch/minor reconciliation is not claimed.

House-scanner and KakaoBot-API remain blocked by failed Vercel deployment checks whose logs are inaccessible to the available credentials. TangoMBTI remains blocked by enforced vulnerability audit GHSA-vfj7-8cjw-p6xm. Their guard PRs remain open and failed checks are preserved. Chatbot production assets and kiro-skills unsupported Bun/scripts remain manual limitations.

The publishing workflow inventory is being expanded for guarded paths missed by heuristic discovery. Hosted controlled timeout, cancellation, multi-project partial failure and malformed workflow samples produced their expected non-success outcomes. Timeout is recorded as cancelled with an explicit GitHub1m0s timeout annotation. These dispatches prove adapter behavior, not end-to-end auto-merge denial. Successful inventory reconciliation does not establish complete publishing-path detection or failed-update publication denial.

JSON embeds exact source hashes, API check heads, controlled fixture results, real bot outcomes,21 policy promotion records and30 original protection backup hashes. All acceptance gaps remain explicit; acceptance-complete is false.

Publication inventory PR23 records64 verified publishing paths. Structural review found23 of29 wiki paths requiring fresh validation or failure-propagation corrections; source guard changes are under review and deployment acceptance remains incomplete.
