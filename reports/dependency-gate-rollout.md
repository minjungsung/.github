# Dependency Gate Rollout Evidence

Status: incomplete. All33 active repositories are classified, and30 have merged audited callers with verified required dependency-gate protection bound to App15368. Protection and caller snapshots are exact-head evidence at their recorded times; LingoCast current main lacks a fresh gate after ordinary automation merged its wiki PR.

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
| LingoCast | hosted-pass | caller-merged / applied-and-verified | Actual minor PR118 passed all3 projects and auto-merged. Wiki PR121 was merged by ordinary automation before full CI; checks later passed. Required human-only journal PR122 is blocked by Vercel quota; fresh current-main gate proof remains missing. |
| medium | hosted-pass | caller-merged / applied-and-verified | Strict Python3.11 install and Pages publication passed; reviewed generated-file main push guard avoids detached-HEAD push and serializes writes. |
| minjungsung | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Nbody | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| portfolio-backend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend-inner | hosted-pass | caller-merged / applied-and-verified | Strict Node20 baseline and metadata canary passed, required gate verified. Release PR47 merged after CI/Vercel with exact gate/lint prerequisites. Wiki guard PR48 latest head is blocked by24-hour Vercel quota. |
| repo-template | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| senior_eltango | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| shooting-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| TangoDJ | hosted-pass | caller-merged / applied-and-verified | Audited Node24 project; source CI and caller PR2 merged. Default-branch strict CI and gate passed; required dependency-gate protection applied and verified. |
| TangoMBTI | hosted-ci-pass-audit-failed | not-rolled-out / not-observed | PR remains unmerged: unpatched braces GHSA-vfj7-8cjw-p6xm in framework lint dependencies; Tailwind4 migration builds locally but does not clear audit. |
| Undead-Survivor | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| visionRAG | hosted-pass-manual | manual-caller-merged / applied-and-verified | All3 strict projects passed, including original extras and87 actual tests. Main CI/DVC/Docker build and smoke passed. Manual caller/wiki/release guards and requiredgate verified; external GPU/OCR behavior remains manual. |

All21 reviewed automatic-merge policy promotion PRs passed checks, then exact main caller bytes and idempotent protection were verified. Actual LingoCast minor PR118 passed all3 projects and trusted gate before metadata-driven automatic merge. Actual JHU major PR40 passed15 central projects and64 existing tests with PostgreSQL16, then remained open with no auto-merge request.

Hosted timeout, authorized cancellation, partial matrix failure and malformed actionlint samples produced expected non-success outcomes. GitHub explicitly annotated the one-minute timeout; it is accurately recorded as cancelled. These are synthetic adapter samples, separate from real bot identity and end-to-end merge prevention.

The publishing inventory records64 actual paths. Source review confirms fresh validation guard structure on25 of29 wiki paths;4 remain blocked in open guard PRs. The20-repository wiki guard wave merged18 PRs:17 manually after successful checks, and LingoCast through existing ordinary automation before checks completed. Its checks later passed. House/Tango wiki and release guards remain in their blocked PRs. Kiro release now validates all4 actual projects and fails closed on unsupported Bun/scripts; no release was dispatched. Frontend-inner release now requires exact trusted gate, fresh lint and existing strict install/test/build.

Remaining blockers: House-scanner and KakaoBot-API deployments fail, and TangoMBTI enforcing vulnerability audit fails. KakaoBot-API wiki guard remains blocked by deployment. Frontend-inner wiki guard and LingoCast required journal correction are blocked by Vercel24-hour build quota. Failed checks are preserved, and no quota retries or failing merges are performed.

The recorded reconciliation snapshot has7 manual-major,13 manual-unknown and8 manual-repository rows. Manual inventory policy is authoritative. No complete fleet patch/minor reconciliation or universal failed-update publication-denial coverage is claimed.

English JSON records exact source hashes, workflow heads, check outcomes,64 publication paths, original30 protection backups, review scope and remaining gaps. Acceptance-complete remains false.
