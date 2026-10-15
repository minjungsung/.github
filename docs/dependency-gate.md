# Dependency Gate operator guide

The required aggregate check is `Dependency Gate / dependency-gate`. A failure means at least one inventoried project failed strict installation, tests, builds, or workflow validation. Inspect the validation job and its summary for the failing project and command. Missing required manifests, lockfiles, or runtimes also fail closed.

To reproduce locally, use the inventoried runtime and project directory. For npm projects with a reviewed lockfile, run `npm ci`; otherwise run `npm install`. Run `npm ls --all` as an additional local diagnostic. For Python, use a fresh virtual environment, install the inventoried requirements or project, then optionally run `python -m pip check` as an additional local diagnostic. For Gradle, use the checked-in wrapper and the inventoried validation command. Follow the same test/build commands as `dependency-policy/repositories.json` and `dependency-policy/scripts/run_project.py`.

Do not add permissive installation flags, ignore failed dependency checks, or skip tests to make a PR green. Align the application and its peer dependencies to compatible supported versions, regenerate the lockfile with the reviewed runtime, and run strict installation again. Fix the incompatible manifest or package choice instead of suppressing the resolver.

Tests and builds run only where an applicable command was inventoried. The job summary explicitly reports omitted tests/builds; an omission does not establish application correctness. Add missing commands through inventory review. Unsupported application validation disables automatic merging until reviewed support exists.

Only Dependabot patch/minor updates may enable auto-merge after successful validation. Major and other update types require manual review. After a Dependabot rebase, validation runs for the new head SHA. Use Dependabot's rebase command when necessary; review the new results before merging, and rerun failed infrastructure jobs on that current head instead of relying on an older successful commit.

## Generate and publish rollout PRs

Run from the policy repository with authenticated `gh` and `git`. Set `POLICY_SHA` to a reviewed immutable 40-character lowercase commit SHA:

```sh
export PYTHONPATH=dependency-policy
python3 dependency-policy/scripts/rollout.py \
  --repository portfolio-frontend-inner --policy-sha "$POLICY_SHA" \
  --workspace ./rollout-preview
```

The default clones into the explicit workspace, checks origin, clean status, the reviewed live default branch, and its exact fetched commit, then prints diffs and JSON. It writes generated local files, including removing only the exact reviewed legacy standalone workflow. It does not commit or publish. Keep the preview for review; use a fresh workspace for publication because generated preview changes make the clone dirty.

```sh
python3 dependency-policy/scripts/rollout.py \
  --repository portfolio-frontend-inner --policy-sha "$POLICY_SHA" \
  --workspace ./rollout-publish --push --create-pr
```

Both publication flags are required. The branch is `chore/dependency-merge-safeguard`, and the PR title is `ci: gate Dependabot merges on validation`. Only exact generated workflow paths are staged. JSON includes the resulting PR URL. A matching existing PR is returned without creating another; changed policy pins, unexpected PR files, dirty clones, and orphaned rollout branches require review. After a partial failure, inspect the branch and PR before retrying. Nothing is force-pushed or reset automatically.

Customized or independent auto-merge workflows block rollout for review. Deployment workflows are not rewritten: audit deployment commands separately and review explicit remediation before promotion. Do not remove arbitrary workflows merely because their names mention auto-merge.

Promote `portfolio-frontend-inner` first: review and merge its rollout PR, observe a successful gate on the exact canary commit and validate enforcement before rolling out remaining repositories. Future central policy releases use the same `rollout.py --policy-sha NEW_SHA` path. Update and verify the canary first, then open one generated SHA-bump PR per remaining repository. Resolve any previous open rollout PR before changing its requested pin. There is no mutable-tag updater.

## Apply protection and recover

After the canary succeeds, preview the required-context change using its exact successful commit SHA:

```sh
python3 dependency-policy/scripts/configure_protection.py \
  --repository portfolio-frontend-inner --sha "$CANARY_SHA"
```

Review the before/after output. Apply with the immutable policy pin only after the caller is merged and the exact check succeeds:

```sh
python3 dependency-policy/scripts/configure_protection.py \
  --repository portfolio-frontend-inner --sha "$CANARY_SHA" \
  --policy-sha "$POLICY_SHA" --apply
```

The protection command preserves existing requirements and backs up settings before mutation under `reports/protection-backups/`. Preserve that backup. For rollback, compare current settings with the backup, remove only the newly added `Dependency Gate / dependency-gate` requirement, and restore the backed-up required-check settings while preserving subsequent unrelated changes. Never delete all required checks or overwrite unrelated branch protections. Revert the rollout workflow PR separately if needed, after confirming the required context will no longer block merges.
