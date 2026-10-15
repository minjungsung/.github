# Dependency Gate rollout evidence

Status: **in progress**. Acceptance remains **false**. Latest observed active inventory has 33 repositories and 33 reviewed entries; TangoDJ now has main and is nonempty; fresh live inventory audit exited0 with33 active repositories and no ambiguities or unclassified entries. Central PRs 2–9 are merged, and central protection is applied and verified.

Canary caller is merged; hosted strict CI and gate succeeded. Required `dependency-gate` binds GitHub Actions App15368. Earlier HTTP422 failed-before-mutation evidence is historical; corrected protection and idempotence verification succeeded. Original backups and SHA-256 evidence are listed in the JSON report.

Action-only wave merges and enforcement below reflect hashed mutable snapshots. A successful ordinary/default-push no-op proves caller execution rather than application validation. Controlled synthetic cases remain separate from real Dependabot acceptance.

| Repository | Baseline | Rollout / enforcement | Notes |
|---|---|---|---|
| .github | not-executed | caller-merged / applied-and-verified | Central caller merged and required dependency-gate protection verified. |
| Algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Chatbot | failed | not-rolled-out / not-observed | Strict Python3.12 requirements installation failed: TensorFlow2.12.1 has no compatible wheel; candidate constraints and missing runtime assets remain unresolved. |
| Interview | not-executed | not-rolled-out / not-observed | No repository-specific acceptance evidence recorded |
| KakaoBot | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| KakaoBot-API | hosted-ci-pass-deployment-blocked | caller-pr-open / not-observed | Strict hosted Python3.12 requirements installation passed; test/build explicitly skipped because unconfigured. PR33 remains unmerged because Vercel deployment is blocked. |
| Leethub | hosted-pass | caller-merged / applied-and-verified | Reviewed remediation PR42 merged after hosted strict CI passed; caller PR43 merged and required dependency-gate protection applied and verified. |
| LingoCast | not-executed | not-rolled-out / not-observed | Static web command added; actual project baseline enforcement not yet observed |
| Nbody | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| TangoDJ | hosted-pass | caller-merged / applied-and-verified | Audited Node24 project; source CI and caller PR2 merged. Default-branch strict CI and gate passed; required dependency-gate protection applied and verified. |
| TangoMBTI | hosted-ci-pass-audit-failed | not-rolled-out / not-observed | PR remains unmerged: unpatched braces GHSA-vfj7-8cjw-p6xm in framework lint dependencies; Tailwind4 migration builds locally but does not clear audit. |
| Undead-Survivor | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| ai_algorithm_design_and_analysis | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| applied_generative_ai | not-executed | caller-merged / applied-and-verified | Caller merged; CI and gate succeeded; protection applied and verified. |
| applied_machine_learning | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| course-manager | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| creating_ai_enabled_systems | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| dongle-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| eltango | remediation-merged | caller-merged / applied-and-verified | Caller merged after hosted checks; required dependency-gate protection applied and verified. |
| hackdigest | not-executed | not-rolled-out / not-observed | Worker test script explicitly exits1; unresolved baseline blocker |
| house-scanner-frontend | hosted-ci-pass-deployment-blocked | not-rolled-out / not-observed | Strict hosted Node20 CI passed; PR remains unmerged because Vercel deployment is blocked. |
| introduction_to_algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| jhu_software_concepts | not-executed | not-rolled-out / not-observed | No repository-specific acceptance evidence recorded |
| kiro-skills | not-executed | not-rolled-out / not-observed | Bun adapter unavailable; source script suppression requires manual review |
| medium | not-executed | not-rolled-out / not-observed | No repository-specific acceptance evidence recorded |
| minjungsung | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| portfolio-backend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend-inner | hosted-pass | caller-merged / applied-and-verified | PR45 merged; default-branch CI/gate succeeded; required dependency-gate check bound to Actions App15368. Second apply was idempotent. |
| repo-template | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| senior_eltango | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| shooting-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| visionRAG | not-executed | not-rolled-out / not-observed | Reviewed extras configured; auto-merge disabled pending actual baseline validation |

TangoDJ source CI/lockfile PR1 merged at `b363243abc875af71005509a79ff724835a84801`; central inventory PR9 merged at `83f181030ef7208baf55f4e708a90ba0f4307d98`. Caller PR2 merged at `949ed5cecbd2c438c4a802e16c14871950b698ff`; default-branch strict CI run38672659092 and gate run38672659674 passed at that SHA. Required `dependency-gate` protection binds Actions App15368 and was applied and verified. All 33 active repositories now have reviewed inventory entries.

Verified protection now covers 22 repositories, including TangoDJ, applied_generative_ai, Leethub and eltango. Leethub caller PR43 and eltango caller PR28 are merged and their required-check settings were re-queried successfully. Backend remediation PR37 and eltango remediation PR26 passed hosted Node20 CI before merge. House PR122 remains open because Vercel deployment is blocked; Tango PR32 remains open because its audit fails on unpatched braces.

Real repo-template Dependabot major PR2 at recorded head prefix `008901f` has a successful gate run38670842929, verified major metadata and null auto-merge request. This is scoped identity/head evidence, not fleet reconciliation.

All currently available protection backup files are hashed with portable report references in JSON. Mutable source snapshots are identified by SHA-256. Partial rollout, external deployment/audit blockers, manual repositories and incomplete Dependabot reconciliation keep acceptance false.

The latest live Dependabot snapshot contains38 rows: 15 manual-major,20 manual-unknown and3 incomplete API discoveries. Exact records and source hash are embedded in JSON. No patch/minor merge-eligibility or complete reconciliation is claimed. Chatbot strict Python baseline failed due to TensorFlow2.12.1/Python3.12 incompatibility and candidate constraints/missing runtime assets; portable candidate source references are hashed in JSON.

Historical initial local npm failure phases remain in JSON with explicit evidence scope; later reviewed and hosted remediation outcomes are separate. KakaoBot-API PR33 passed hosted strict Python CI but remains unmerged due to Vercel; Leethub remediation PR42 passed hosted strict CI before merge. All 22 protection backups are hashed.

KakaoBot-API strict CI run38671382979 passed at `82dabca9548212d719f47c2d02cc402b7a56809b`. Leethub strict Node20 CI run38671435653 passed at `4d05d274481258b8688990adb09f6fa111a9e746`. These runs and the successful live inventory audit source hash are embedded in JSON. The inventory audit does not establish fleet enforcement or complete Dependabot reconciliation.
