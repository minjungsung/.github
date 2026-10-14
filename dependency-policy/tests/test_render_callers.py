from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib.commands import FORBIDDEN_FRAGMENTS
from lib.models import Project, Repository
from scripts.render_callers import main, render_caller


POLICY_SHA = "a" * 40
SNAPSHOT = Path(__file__).parent / "snapshots" / "portfolio-frontend-inner.yml"


class RenderCallersTest(unittest.TestCase):
    def repository(self, *, auto_merge_enabled=True):
        return Repository(
            name="portfolio-frontend-inner",
            default_branch="main",
            projects=(
                Project(
                    name="root-node",
                    ecosystem="npm",
                    path=".",
                    runtime_version="20",
                    manifest="package.json",
                    lockfile="package-lock.json",
                    timeout_minutes=15,
                ),
            ),
            deployment_workflows=("vercel:production-from-main",),
            auto_merge_enabled=auto_merge_enabled,
        )

    def test_render_is_deterministic_and_uses_compact_schema_json(self):
        first = render_caller(self.repository(), POLICY_SHA)
        second = render_caller(self.repository(), POLICY_SHA)

        self.assertEqual(first.encode(), second.encode())
        expected_projects = json.dumps(
            [{
                "name": "root-node",
                "ecosystem": "npm",
                "path": ".",
                "runtime-version": "20",
                "manifest": "package.json",
                "lockfile": "package-lock.json",
                "timeout-minutes": 15,
            }],
            separators=(",", ":"),
        )
        self.assertIn(f"projects-json: '{expected_projects}'", first)

    def test_render_pins_policy_sha_exactly_twice(self):
        rendered = render_caller(self.repository(), POLICY_SHA)

        self.assertEqual(rendered.count(POLICY_SHA), 2)
        self.assertIn(f"dependency-validation.yml@{POLICY_SHA}", rendered)
        self.assertIn(f"policy-ref: {POLICY_SHA}", rendered)

    def test_render_uses_pr_identity_concurrency_and_aggregation_gate(self):
        rendered = render_caller(self.repository(), POLICY_SHA)

        self.assertNotIn("github.actor", rendered)
        self.assertIn("pr-author: ${{ github.event.pull_request.user.login }}", rendered)
        self.assertIn(
            "group: dependency-gate-${{ github.repository }}-${{ github.event.pull_request.number }}",
            rendered,
        )
        self.assertIn("cancel-in-progress: true", rendered)
        self.assertIn("  dependency-gate:\n    name: dependency-gate\n    if: always()", rendered)
        self.assertIn("    needs: validate-dependencies", rendered)
        self.assertIn("VALIDATION_RESULT: ${{ needs.validate-dependencies.result }}", rendered)
        self.assertIn('run: test "$VALIDATION_RESULT" = success', rendered)
        self.assertIn("  dependabot-auto-merge:", rendered)
        self.assertIn("    needs: dependency-gate", rendered)

    def test_render_only_auto_merges_patch_and_minor_dependabot_updates(self):
        rendered = render_caller(self.repository(), POLICY_SHA)

        self.assertIn(
            "uses: dependabot/fetch-metadata@08eff52bf64351f401fb50d4972fa95b9f2c2d1b",
            rendered,
        )
        self.assertIn("steps.dependabot-metadata.outputs.update-type == 'version-update:semver-patch'", rendered)
        self.assertIn("steps.dependabot-metadata.outputs.update-type == 'version-update:semver-minor'", rendered)
        self.assertIn("gh pr review --approve", rendered)
        self.assertIn("gh pr merge --auto --squash", rendered)
        self.assertIn("Manual review required", rendered)

    def test_render_omits_auto_merge_job_when_repository_disables_it(self):
        rendered = render_caller(self.repository(auto_merge_enabled=False), POLICY_SHA)

        self.assertNotIn("dependabot-auto-merge", rendered)
        self.assertNotIn("dependabot/fetch-metadata", rendered)
        self.assertIn("dependency-gate", rendered)

    def test_render_rejects_non_commit_policy_refs(self):
        for invalid in ("a" * 39, "a" * 41, "g" * 40, "A" * 40):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "policy SHA"):
                render_caller(self.repository(), invalid)

    def test_render_contains_no_forbidden_permissive_fragments(self):
        rendered = " ".join(render_caller(self.repository(), POLICY_SHA).lower().split())
        searchable = f" {rendered}"

        for fragment in FORBIDDEN_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, searchable)

    def test_render_escapes_yaml_quotes_without_replacing_tokens_in_project_data(self):
        repository = Repository(
            name="quoted-command",
            default_branch="main",
            projects=(
                Project(
                    name="root-node",
                    ecosystem="npm",
                    path=".",
                    runtime_version="20",
                    manifest="package.json",
                    test_command="printf 'AUTO_MERGE_JOB'",
                    timeout_minutes=15,
                ),
            ),
        )

        rendered = render_caller(repository, POLICY_SHA)

        self.assertIn('"test-command":"printf \'\'AUTO_MERGE_JOB\'\'"', rendered)
        self.assertEqual(rendered.count("dependabot-auto-merge:"), 1)

    def test_snapshot_matches_canary_repository(self):
        self.assertEqual(render_caller(self.repository(), POLICY_SHA), SNAPSHOT.read_text())

    def test_cli_check_returns_zero_for_match_and_prints_unified_diff_for_mismatch(self):
        repository = Repository(
            name=".github",
            default_branch="main",
            projects=(
                Project(
                    name="workflow-policy",
                    ecosystem="github-actions",
                    path=".",
                    timeout_minutes=5,
                ),
            ),
        )
        with TemporaryDirectory() as temp:
            target = Path(temp) / "dependency-gate.yml"
            target.write_text(render_caller(repository, POLICY_SHA))
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                matched = main([
                    "--repository", ".github",
                    "--policy-sha", POLICY_SHA,
                    "--check", str(target),
                ])
            self.assertEqual(matched, 0)
            self.assertEqual(stdout.getvalue(), "")

            target.write_text("name: stale\n")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                mismatched = main([
                    "--repository", ".github",
                    "--policy-sha", POLICY_SHA,
                    "--check", str(target),
                ])
            self.assertEqual(mismatched, 1)
            self.assertIn(f"--- {target}", stdout.getvalue())
            self.assertIn(f"+++ {target} (generated)", stdout.getvalue())
            self.assertIn("-name: stale", stdout.getvalue())
            self.assertIn("+name: Dependency Gate", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

    def test_cli_output_creates_parent_directories_with_generated_bytes(self):
        with TemporaryDirectory() as temp:
            output = Path(temp) / ".github" / "workflows" / "dependency-gate.yml"
            result = main([
                "--repository", ".github",
                "--policy-sha", POLICY_SHA,
                "--output", str(output),
            ])

            self.assertEqual(result, 0)
            self.assertEqual(output.read_text().count(POLICY_SHA), 2)


if __name__ == "__main__":
    unittest.main()
