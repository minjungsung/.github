# Controlled fixture validation

`Controlled Fixture Validation` is an operator-dispatched workflow that calls the same local reusable validation workflow as repository callers. It has no pull-request trigger, merge permission, or merge automation. The policy checkout uses the dispatch commit SHA.

The `pr-author` input is synthetic routing data. These runs are controlled adapter and routing evidence, not real Dependabot PR evidence. They do not establish major-update handling or authorize automatic merging. Real Dependabot patch/minor and major metadata behavior remains a separate acceptance check.

Select one scenario per dispatch on the reviewed release commit:

| Scenario | Required conclusion | Required evidence |
| --- | --- | --- |
| ordinary | Success | Ordinary pull request successful no-op summary; matrix validation skipped |
| npm-pass | Success | Install, test, build and overall result PASS |
| npm-peer-conflict | Failure | Install FAIL, ERESOLVE in logs, overall result FAIL |
| npm-fail-test | Failure | Install PASS, test FAIL, overall result FAIL |
| npm-fail-build | Failure | Install and test PASS, build FAIL, overall result FAIL |
| python-requirements-fail | Failure | Install FAIL because the controlled nonexistent package cannot resolve; overall result FAIL |

Negative scenarios intentionally remain failed workflow runs. No aggregator converts an expected failure into a successful gate. Inspect the failing validation job logs and phase summary: an infrastructure error or missing summary is not the expected result. Record the immutable run SHA, run URL, conclusion, and specific failure evidence in the acceptance report.

For example, after the workflow is available on the default branch:

```sh
gh workflow run controlled-fixture-validation.yml --ref REVIEWED_RELEASE_SHA -f scenario=npm-fail-test
gh run list --workflow controlled-fixture-validation.yml
gh run view RUN_ID --log-failed
```

Replace the placeholders with the reviewed full commit SHA and actual run ID. Compare the workflow run's head SHA with the requested release SHA before using its evidence.

Gradle fixture pass/failure is exercised separately in Policy CI using a checksum-verified Gradle distribution. The reusable Gradle adapter requires a real project wrapper; these delegated fixture wrappers do not provision Gradle themselves. Workflow lint negative validation and real Dependabot major-update behavior remain pending separate evidence. The generated canary caller's check-runs API response supplies the aggregate required-check name; this controlled workflow does not emulate that caller check or supply its required context.
