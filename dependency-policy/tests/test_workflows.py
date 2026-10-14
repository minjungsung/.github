from pathlib import Path
import unittest

from lib.commands import FORBIDDEN_FRAGMENTS


ROOT = Path(__file__).resolve().parents[2]
VALIDATION_WORKFLOW = ROOT / ".github" / "workflows" / "dependency-validation.yml"
POLICY_CI_WORKFLOW = ROOT / ".github" / "workflows" / "policy-ci.yml"
INSTALL_ACTIONLINT = ROOT / "dependency-policy" / "scripts" / "install_actionlint.sh"

CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
SETUP_NODE = "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020"
SETUP_PYTHON = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
SETUP_JAVA = "actions/setup-java@cf277c60eb25467037889841efdb72551f06f6c3"
ACTIONLINT_SHA256 = "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            VALIDATION_WORKFLOW.is_file(),
            f"missing reusable workflow: {VALIDATION_WORKFLOW}",
        )
        self.validation = VALIDATION_WORKFLOW.read_text()

    def test_reusable_workflow_declares_required_string_inputs_and_read_only_permissions(self):
        self.assertIn("workflow_call:", self.validation)
        for input_name in ("pr-author", "projects-json", "policy-ref"):
            with self.subTest(input_name=input_name):
                self.assertIn(
                    f"      {input_name}:\n        required: true\n        type: string",
                    self.validation,
                )
        self.assertIn("permissions:\n  contents: read", self.validation)
        self.assertNotIn("secrets: inherit", self.validation)

    def test_ordinary_job_is_a_five_minute_no_op_only_for_non_dependabot_authors(self):
        ordinary = self.validation.split("  ordinary-pr:", 1)[1].split(
            "  validate-projects:", 1
        )[0]
        self.assertIn("if: inputs.pr-author != 'dependabot[bot]'", ordinary)
        self.assertIn("timeout-minutes: 5", ordinary)
        self.assertIn("GITHUB_STEP_SUMMARY", ordinary)
        self.assertIn("Ordinary pull request", ordinary)
        self.assertNotIn("actions/checkout", ordinary)
        self.assertNotIn("run_project.py", ordinary)

    def test_dependabot_job_uses_non_fail_fast_project_matrix_and_project_timeout(self):
        validate = self.validation.split("  validate-projects:", 1)[1]
        self.assertIn("if: inputs.pr-author == 'dependabot[bot]'", validate)
        self.assertIn("fail-fast: false", validate)
        self.assertIn(
            "project: ${{ fromJSON(inputs.projects-json) }}",
            validate,
        )
        self.assertIn("timeout-minutes: ${{ matrix.project.timeout-minutes }}", validate)
        self.assertIn("PROJECT_JSON: ${{ toJSON(matrix.project) }}", validate)

    def test_reusable_workflow_uses_exact_action_pins_and_conditional_runtimes(self):
        for pin in (CHECKOUT, SETUP_NODE, SETUP_PYTHON, SETUP_JAVA):
            with self.subTest(pin=pin):
                self.assertIn(f"uses: {pin}", self.validation)
        self.assertIn("matrix.project.ecosystem == 'npm'", self.validation)
        self.assertIn("startsWith(matrix.project.ecosystem, 'python-')", self.validation)
        self.assertIn("matrix.project.ecosystem == 'gradle'", self.validation)
        self.assertIn("node-version: ${{ matrix.project.runtime-version }}", self.validation)
        self.assertIn("python-version: ${{ matrix.project.runtime-version }}", self.validation)
        self.assertIn("java-version: ${{ matrix.project.runtime-version }}", self.validation)

    def test_policy_checkout_is_pinned_to_input_and_runner_receives_target_workspace(self):
        self.assertIn("repository: minjungsung/.github", self.validation)
        self.assertIn("ref: ${{ inputs.policy-ref }}", self.validation)
        self.assertIn("path: .dependency-policy-source", self.validation)
        command_lines = "\n".join(line.strip() for line in self.validation.splitlines())
        self.assertIn(
            "PYTHONPATH=.dependency-policy-source/dependency-policy \\\npython3 .dependency-policy-source/dependency-policy/scripts/run_project.py \\\n--project-json \"$PROJECT_JSON\" \\\n--repository-root \"$GITHUB_WORKSPACE\"",
            command_lines,
        )

    def test_actionlint_is_installed_only_for_github_actions_projects(self):
        self.assertIn("matrix.project.ecosystem == 'github-actions'", self.validation)
        self.assertIn(
            "bash .dependency-policy-source/dependency-policy/scripts/install_actionlint.sh",
            self.validation,
        )

    def test_policy_ci_runs_local_contracts_render_checks_and_actionlint(self):
        self.assertTrue(POLICY_CI_WORKFLOW.is_file(), f"missing policy CI: {POLICY_CI_WORKFLOW}")
        policy_ci = POLICY_CI_WORKFLOW.read_text()
        self.assertIn("pull_request:", policy_ci)
        self.assertIn("push:\n    branches:\n      - main", policy_ci)
        self.assertIn("permissions:\n  contents: read", policy_ci)
        self.assertIn(f"uses: {CHECKOUT}", policy_ci)
        self.assertIn(f"uses: {SETUP_NODE}", policy_ci)
        self.assertIn(f"uses: {SETUP_PYTHON}", policy_ci)
        self.assertIn(
            "python3 -m unittest discover -s dependency-policy/tests -v",
            policy_ci,
        )
        self.assertIn("render_callers.py", policy_ci)
        self.assertIn("--check \"$rendered\"", policy_ci)
        self.assertIn("bash dependency-policy/scripts/install_actionlint.sh", policy_ci)
        self.assertIn(
            "actionlint .github/workflows/*.yml dependency-policy/tests/snapshots/*.yml",
            policy_ci,
        )
        self.assertIn("dependency-policy/fixtures/npm-peer-conflict", policy_ci)
        self.assertIn(': > "$npm_user_config"', policy_ci)
        self.assertIn('NPM_CONFIG_USERCONFIG="$npm_user_config"', policy_ci)
        self.assertIn("grep -F ERESOLVE", policy_ci)

    def test_installer_is_version_and_checksum_pinned(self):
        self.assertTrue(INSTALL_ACTIONLINT.is_file(), f"missing installer: {INSTALL_ACTIONLINT}")
        installer = INSTALL_ACTIONLINT.read_text()
        self.assertIn("version=1.7.12", installer)
        self.assertIn(f'expected="{ACTIONLINT_SHA256}"', installer)
        self.assertIn("sha256sum --check -", installer)
        self.assertIn("set -euo pipefail", installer)

    def test_workflows_have_no_permissive_suppression_or_mutable_action_refs(self):
        workflows = self.validation
        if POLICY_CI_WORKFLOW.is_file():
            workflows += "\n" + POLICY_CI_WORKFLOW.read_text()
        normalized = " ".join(workflows.lower().split())
        searchable = f" {normalized}"
        for fragment in FORBIDDEN_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, searchable)
        self.assertNotIn("continue-on-error: true", normalized)
        for mutable_ref in ("actions/checkout@v", "actions/setup-node@v", "actions/setup-python@v", "actions/setup-java@v"):
            with self.subTest(mutable_ref=mutable_ref):
                self.assertNotIn(mutable_ref, workflows)


if __name__ == "__main__":
    unittest.main()
