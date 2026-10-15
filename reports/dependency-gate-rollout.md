# Dependency Gate Rollout Evidence

Status: in progress. Acceptance remains incomplete. All33 active repositories are inventoried; this snapshot verifies29 required dependency-gate protections bound to GitHub Actions App15368.

| Repository | Baseline | Rollout / enforcement | Evidence and limitations |
|---|---|---|---|
| .github | not-executed | caller-merged / applied-and-verified | Central caller merged and required dependency-gate protection verified. |
| ai_algorithm_design_and_analysis | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| applied_generative_ai | not-executed | caller-merged / applied-and-verified | Caller merged; CI and gate succeeded; protection applied and verified. |
| applied_machine_learning | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Chatbot | hosted-model-compatibility-pass | manual-caller-merged / applied-and-verified | Strict Python3.12 constrained install, pip check and both real model tests passed. Native import order fixed; manual caller/release/wiki guards and required gate verified. Missing production assets remain unaccepted. |
| course-manager | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| creating_ai_enabled_systems | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| dongle-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| eltango | remediation-merged | caller-merged / applied-and-verified | Caller merged after hosted checks; required dependency-gate protection applied and verified. |
| hackdigest | hosted-pass | caller-merged / applied-and-verified | Strict Node24 worker install, five actual request regressions and build plus Python3.12 install passed. Main-only digest/subscriber and tag release verification guards reviewed. |
| house-scanner-frontend | hosted-ci-pass-deployment-blocked | not-rolled-out / not-observed | Strict hosted Node20 CI passed; PR remains unmerged because Vercel deployment is blocked. |
| Interview | hosted-pass | caller-merged / applied-and-verified | Strict Node20 install/test/build, Python3.12 and actual Ruff checks passed. Reviewed caller, wiki and release guards merged; exact-main required gate verified. |
| introduction_to_algorithm | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| jhu_software_concepts | hosted-pass | service-aware-caller-pending / not-observed | Clean remediation PR58 passed all15 strict matrix entries and existing tests, including disposable PostgreSQL integration tests. Central service support is under review before caller rollout. |
| KakaoBot | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| KakaoBot-API | hosted-ci-pass-deployment-blocked | caller-pr-open / not-observed | Strict hosted Python3.12 requirements installation passed; test/build explicitly skipped because unconfigured. PR33 remains unmerged because Vercel deployment is blocked. |
| kiro-skills | manual-unaccepted | caller-merged / applied-and-verified | Fail-closed manual caller retains all four audited projects. Bun is unsupported and script suppression remains an explicit application blocker; auto-merge disabled. |
| Leethub | hosted-pass | caller-merged / applied-and-verified | Reviewed remediation PR42 merged after hosted strict CI passed; caller PR43 merged and required dependency-gate protection applied and verified. |
| LingoCast | hosted-pass | caller-merged / applied-and-verified | Actual Node20/Java21 validation passed. Immutable PR author routing guards existing automation. Journal PR119 established exact-main gate proof; grouped metadata canary PR120 remains pending. |
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
| visionRAG | hosted-pass-manual | manual-caller-merged / applied-and-verified | All3 strict projects and87 actual tests passed. Main CI/DVC/Docker smoke and gate passed; manual guards and protection verified. External GPU/OCR behavior remains manual. |

The original canary proved strict validation and idempotent enforcement. Six controlled fixture runs are synthetic evidence. Actual repo-template major bot evidence remained manual after a successful gate. The recorded reconciliation snapshot contains28 open bot records:9 manual-major and19 manual-unknown. One actual minor automatic merge is proven below; fleet reconciliation and patch evidence remain incomplete.

Central metadata release `912a4df6333443b9f8a012275627d971a8218a03` passed independent review and hosted policy CI. Exact upstream v3.1.0 metadata was tested against the authenticated grouped LingoCast update; separately reviewed canary PR120 merged; actual minor automatic merge is proven. Existing fleet callers except LingoCast remain pinned to the prior reviewed policy53eef and therefore differ from the latest renderer until explicit promotion.

House-scanner and KakaoBot-API remain blocked by failed Vercel deployment checks without accessible deployment logs. TangoMBTI remains blocked by enforced audit GHSA-vfj7-8cjw-p6xm. These failures are preserved. Chatbot production assets and kiro-skills Bun/script issues remain manual limitations. JHU central service support must pass review and actual hosted integration checks before rollout.

JSON embeds exact API heads/checks, current reconciliation records, prior controlled evidence and source hashes. Backup hashes identify original protected-setting snapshots. Default-push ordinary no-op checks establish caller execution only; application validation is recorded separately.

Chatbot main `99a59d891cbeed7752ff2bc0ed1a1ac71597f472` passed actual CI run38676767794 and gate run38676768029 before protection application/readback. Auto-merge remains disabled and production assets are still unavailable. Latest live inventory check returned1 despite zero classification ambiguities; serialized inventory drift is under investigation.

VisionRAG main `9a840d4cacb342b7489f42332a5650ce0f03dde8` passed strict run38676835167, CI/DVC/Docker run38676835137 and gate38676835544 before manual protection. LingoCast canary PR120 merged at578f1117; bot PR118 was updated through the expected-head GitHub API to7094f93e ; subsequent strict gate and metadata proof is recorded below.

Actual LingoCast Dependabot minor PR118 passed all3 strict project jobs and trusted gate on head `7094f93ebf59ae670cdc2aaf38fb280927aaeb46`. Reviewed metadata25dd classified jsoup1.17.2→1.23.2 as semver-minor without verification skips. Auto-merge job38677298115/116234521695 succeeded and GitHub merged `5bd5fe28f784cc552635bbc2ad47321fe521ba01`. No manual merge was performed. This proves one minor case; patch coverage, fleet reconciliation, remaining manual/unknown cases and production acceptance are still separate.
