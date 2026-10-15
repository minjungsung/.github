# Dependency Gate Rollout Evidence

Status: incomplete across the fleet. All33 active repositories are classified;30 have required dependency-gate protection bound to App15368. In automatic-merge-enabled repositories, known patch, minor and major updates are now eligible for automatic merging after strict validation. Unknown update types remain manual.

The original frontend-inner outcome is achieved: [security migration PR50](https://github.com/minjungsung/portfolio-frontend-inner/pull/50) merged after strict install, two real tests, lint, TypeScript build, Vite build and browser smoke checks. The24 open GitHub Dependabot alerts became zero without dismissals; npm audit also reports zero vulnerabilities. Seven obsolete npm major PRs were closed with their implemented replacement. [Actual checkout major PR27](https://github.com/minjungsung/portfolio-frontend-inner/pull/27) automatically merged after strict application CI and the trusted gate passed. Vercel deployment remains blocked by its independently confirmed24-hour build quota.

The reviewed major-policy release is `0b9ee15e26f054586eeeab7601edebb9a32bfe57`. Of24 reviewed caller promotions,23 policy PRs merged; frontend-inner's duplicate promotion was incorporated into PR50. [JHU major PR40](https://github.com/minjungsung/jhu_software_concepts/pull/40) actually auto-merged after all15 project validations passed. Metadata verification remained enabled, and no manual merge was performed for either actual major sample.

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
| jhu_software_concepts | hosted-pass | caller-merged / applied-and-verified | Actual verified pytest-cov major40 automatically merged after all15 projects passed. Resulting GitHub-token main commit has no cascading push gate yet. |
| KakaoBot | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| KakaoBot-API | hosted-ci-pass-deployment-blocked | caller-pr-open / not-observed | Strict hosted Python3.12 requirements installation passed; test/build explicitly skipped because unconfigured. PR33 remains unmerged because Vercel deployment is blocked. |
| kiro-skills | manual-unaccepted | caller-merged / applied-and-verified | Fail-closed manual caller retains all four audited projects. Bun is unsupported and script suppression remains an explicit application blocker; auto-merge disabled. |
| Leethub | hosted-pass | caller-merged / applied-and-verified | Reviewed remediation PR42 merged after hosted strict CI passed; caller PR43 merged and required dependency-gate protection applied and verified. |
| LingoCast | hosted-pass | caller-merged / applied-and-verified | Actual minor118 auto-merged. Major-policy123 merged after all CI and Vercel passed; fresh main gate verified. Corrective journal122 merged after all strict CI checks passed; optional deployment quota remains. |
| medium | hosted-pass | caller-merged / applied-and-verified | Strict Python3.11 install and Pages publication passed; reviewed generated-file main push guard avoids detached-HEAD push and serializes writes. |
| minjungsung | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| Nbody | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| portfolio-backend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| portfolio-frontend-inner | hosted-pass / security-fixed | caller-merged / applied-and-verified | PR50 migrated the vulnerable dependency graph; open GitHub alerts24 to0, npm audit0. Seven npm major PRs incorporated; actual checkout major27 auto-merged after strict CI. Vercel quota still blocks deployment. Wiki48 merged with native test alignment and fresh main CI passed; no open PRs. |
| repo-template | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| senior_eltango | remediation-merged | caller-merged / applied-and-verified | Reviewed remediation and caller merged; required dependency-gate protection applied and verified. |
| shooting-game | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| TangoDJ | hosted-pass | caller-merged / applied-and-verified | Audited Node24 project; source CI and caller PR2 merged. Default-branch strict CI and gate passed; required dependency-gate protection applied and verified. |
| TangoMBTI | hosted-ci-pass-audit-failed | not-rolled-out / not-observed | PR remains unmerged: unpatched braces GHSA-vfj7-8cjw-p6xm in framework lint dependencies; Tailwind4 migration builds locally but does not clear audit. |
| Undead-Survivor | not-executed | caller-merged / applied-and-verified | Caller merged and required dependency-gate protection applied and verified. |
| visionRAG | hosted-pass-manual | manual-caller-merged / applied-and-verified | All3 strict projects passed, including original extras and87 actual tests. Main CI/DVC/Docker build and smoke passed. Manual caller/wiki/release guards and requiredgate verified; external GPU/OCR behavior remains manual. |

Four reviewed fleet policy PRs merged normally with only authenticated optional Vercel rate-limit failures after required checks and actual application CI passed. These deployment failures remain recorded. No administrator bypass, protection weakening, quota retry loop or successful-deployment claim was used. Actual required application, security, build and deployment failures continue to block.

Eight repositories retain manual automatic-merge settings: Chatbot, TangoMBTI, Undead-Survivor, dongle-game, house-scanner-frontend, kiro-skills, shooting-game and visionRAG. Unsupported Bun/Unity validation and external model/runtime requirements remain explicit gaps. KakaoBot-API remains unenrolled. The requested universal repository coverage is incomplete.

House-scanner and KakaoBot-API actual deployments fail; TangoMBTI's enforcing vulnerability audit fails on unpatched braces. Frontend-inner wiki48 merged after its native Vitest validation aligned; fresh latest-main CI passed. LingoCast corrective journal122 merged after all strict CI checks passed; optional Vercel quota remains deployment blocked.

GitHub-token automatic merges do not trigger cascading push workflows. The actual major PR heads have successful strict checks, but the resulting JHU main commit still needs fresh validation before exact-main publication. Frontend-inner received fresh main CI through the reviewed wiki48 merge; a prior head's green checks do not establish a new main commit's result.

Historical controlled timeout, authorized cancellation, partial matrix failure and malformed actionlint samples retain their observed failures. They are synthetic adapter evidence, separate from real bot identity and end-to-end merge prevention. The publication inventory retains64 source paths; complete fleet PR reconciliation and failed-update publication denial on every publishing workflow remain unproven.

The JSON report preserves historical exact-head snapshots with explicit supersession markers, current major-promotion records, real automatic-merge outcomes, source hashes, original protection backups and remaining gaps. Acceptance-complete remains false.

A subsequent refresh produced seven more actual major automatic merges across Leethub, Nbody, repo-template and senior_eltango. Reconciliation fix PR30 passed162 tests and now reads actual base protection instead of treating missing head checks as absent protection. Remaining open examples include Leethub32/39 with malformed lockfiles, Leethub30 with the GitHub App workflow permission restriction, and senior18 with optional Vercel quota. Successful automatic-merge PR heads do not establish cascading validation on new main commits.
