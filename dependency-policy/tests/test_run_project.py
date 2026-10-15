import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts.run_project import run_project


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeRunner:
    def __init__(self, failing_command=None, returncode=7):
        self.calls = []
        self.failing_command = failing_command
        self.returncode = returncode

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command == self.failing_command:
            raise subprocess.CalledProcessError(self.returncode, command)
        return subprocess.CompletedProcess(command, 0)


class RunProjectTest(unittest.TestCase):
    def copy_fixture(self, name):
        temp = TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(FIXTURES / name, root / "project")
        self.addCleanup(temp.cleanup)
        return root

    def project_json(self, **overrides):
        value = {
            "name": "fixture",
            "ecosystem": "npm",
            "path": "project",
            "runtime-version": "20",
            "manifest": "package.json",
        }
        value.update(overrides)
        return json.dumps(value)

    def summary_environment(self, root):
        summary = root / "summary.md"
        return {"GITHUB_STEP_SUMMARY": str(summary)}, summary

    def test_executes_phases_in_order_with_check_true_and_appends_summary(self):
        root = self.copy_fixture("npm-pass")
        runner = FakeRunner()
        environ, summary = self.summary_environment(root)

        result = run_project(self.project_json(), root, runner=runner, environ=environ)

        self.assertEqual(result, 0)
        self.assertEqual([call[0] for call in runner.calls], [
            ("npm", "install"),
            ("npm", "test", "--", "--watchAll=false"),
            ("npm", "run", "build"),
        ])
        for _, kwargs in runner.calls:
            self.assertTrue(kwargs["check"])
            self.assertEqual(kwargs["cwd"], (root / "project").resolve())
        text = summary.read_text()
        self.assertIn("install", text)
        self.assertIn("test", text)
        self.assertIn("build", text)
        self.assertEqual(text.count("PASS"), 4)

    def test_npm_subprocess_environment_neutralizes_resolution_bypasses(self):
        root = self.copy_fixture('npm-pass')
        runner = FakeRunner()
        result = run_project(self.project_json(), root, runner=runner,
                             environ={'NPM_CONFIG_LEGACY_PEER_DEPS': 'true', 'npm_config_force': 'true'})
        self.assertEqual(result, 0)
        for _, kwargs in runner.calls:
            self.assertNotIn('NPM_CONFIG_LEGACY_PEER_DEPS', kwargs['env'])
            self.assertEqual(kwargs['env']['npm_config_legacy_peer_deps'], 'false')
            self.assertEqual(kwargs['env']['npm_config_force'], 'false')
            self.assertEqual(kwargs['env']['npm_config_strict_peer_deps'], 'true')

    def test_stops_on_first_failing_phase_and_returns_its_code(self):
        root = self.copy_fixture("npm-fail-test")
        failing = ("npm", "test", "--", "--watchAll=false")
        runner = FakeRunner(failing)
        environ, summary = self.summary_environment(root)

        result = run_project(self.project_json(), root, runner=runner, environ=environ)

        self.assertEqual(result, 7)
        self.assertEqual([call[0] for call in runner.calls], [("npm", "install"), failing])
        text = summary.read_text()
        self.assertIn("install: `npm install` — PASS", text)
        self.assertIn("test: `npm test -- --watchAll=false` — FAIL", text)
        self.assertNotIn("npm run build", text)
        self.assertIn("result: FAIL", text)

    def test_reports_absent_scripts_as_explicit_skips(self):
        root = self.copy_fixture("npm-no-scripts")
        runner = FakeRunner()
        environ, summary = self.summary_environment(root)

        result = run_project(self.project_json(), root, runner=runner, environ=environ)

        self.assertEqual(result, 0)
        self.assertEqual([call[0] for call in runner.calls], [("npm", "install")])
        text = summary.read_text()
        self.assertIn("test: SKIP", text)
        self.assertIn("build: SKIP", text)

    def test_configured_missing_manifest_or_lockfile_fails_without_running(self):
        for field, filename in (("manifest", "missing.json"), ("lockfile", "missing-lock.json")):
            root = self.copy_fixture("npm-pass")
            runner = FakeRunner()
            environ, summary = self.summary_environment(root)
            key = field.replace("_", "-")

            with self.subTest(field=field):
                result = run_project(self.project_json(**{key: filename}), root, runner=runner, environ=environ)
                self.assertNotEqual(result, 0)
                self.assertEqual(runner.calls, [])
                self.assertIn("result: FAIL", summary.read_text())

    def test_reuses_strict_project_model_validation(self):
        root = self.copy_fixture("npm-pass")
        runner = FakeRunner()
        environ, summary = self.summary_environment(root)
        invalid = json.loads(self.project_json())
        invalid["unknown"] = True

        result = run_project(json.dumps(invalid), root, runner=runner, environ=environ)

        self.assertNotEqual(result, 0)
        self.assertEqual(runner.calls, [])
        self.assertIn("unknown field", summary.read_text())

    def test_rejects_project_path_that_resolves_outside_repository(self):
        with TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repository"
            outside = Path(temp_name) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "package.json").write_text("{}")
            try:
                (root / "project").symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            runner = FakeRunner()
            environ, summary = self.summary_environment(root)

            result = run_project(self.project_json(), root, runner=runner, environ=environ)

            self.assertNotEqual(result, 0)
            self.assertEqual(runner.calls, [])
            self.assertIn("escapes repository root", summary.read_text())

    def test_string_override_uses_a_shell_but_argv_defaults_do_not(self):
        root = self.copy_fixture("npm-no-scripts")
        runner = FakeRunner()
        environ, _ = self.summary_environment(root)

        result = run_project(
            self.project_json(**{"test-command": "npm run test:ci"}),
            root,
            runner=runner,
            environ=environ,
        )

        self.assertEqual(result, 0)
        self.assertNotIn("shell", runner.calls[0][1])
        self.assertEqual(runner.calls[1][0][:5], ("bash", "-e", "-o", "pipefail", "-c"))

    def test_executable_lookup_error_fails_closed_with_summary(self):
        root = self.copy_fixture("npm-no-scripts")
        environ, summary = self.summary_environment(root)

        def missing_executable(command, **kwargs):
            raise FileNotFoundError("controlled missing executable")

        result = run_project(
            self.project_json(),
            root,
            runner=missing_executable,
            environ=environ,
        )

        self.assertNotEqual(result, 0)
        self.assertIn("install: `npm install` — FAIL", summary.read_text())
        self.assertIn("controlled missing executable", summary.read_text())

    def python_project_json(self, fixture, ecosystem, manifest):
        return json.dumps({
            "name": fixture,
            "ecosystem": ecosystem,
            "path": "project",
            "runtime-version": "3.12",
            "manifest": manifest,
        })

    def test_python_without_tests_does_not_install_pytest_and_reports_skip(self):
        with TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            project_root = root / "project"
            project_root.mkdir()
            (project_root / "requirements.txt").write_text("")
            runner = FakeRunner()
            environ, summary = self.summary_environment(root)

            result = run_project(
                self.python_project_json("python-no-tests", "python-requirements", "requirements.txt"),
                root,
                runner=runner,
                environ=environ,
            )

            self.assertEqual(result, 0)
            self.assertEqual(len(runner.calls), 1)
            self.assertNotIn("pip install pytest", runner.calls[0][0])
            text = summary.read_text()
            self.assertIn("test: SKIP", text)
            self.assertIn("result: PASS", text)

    def test_real_runner_passes_python_requirements_fixture(self):
        root = self.copy_fixture("python-pass")
        environ, summary = self.summary_environment(root)

        result = run_project(
            self.python_project_json("python-pass", "python-requirements", "requirements.txt"),
            root,
            environ=environ,
        )

        self.assertEqual(result, 0)
        text = summary.read_text()
        self.assertIn("install:", text)
        self.assertIn("test: `.dependency-gate-venv/bin/python -m pytest` — PASS", text)
        self.assertIn("result: PASS", text)

    def test_real_runner_passes_python_pyproject_fixture(self):
        root = self.copy_fixture("python-pyproject-pass")
        environ, summary = self.summary_environment(root)

        result = run_project(
            self.python_project_json("python-pyproject-pass", "python-pyproject", "pyproject.toml"),
            root,
            environ=environ,
        )

        self.assertEqual(result, 0)
        text = summary.read_text()
        self.assertIn("install:", text)
        self.assertIn("test: `.dependency-gate-venv/bin/python -m pytest` — PASS", text)
        self.assertIn("result: PASS", text)

    def test_real_runner_fails_python_requirements_failure_fixture(self):
        root = self.copy_fixture("python-requirements-fail")
        environ, summary = self.summary_environment(root)

        result = run_project(
            self.python_project_json(
                "python-requirements-fail",
                "python-requirements",
                "requirements.txt",
            ),
            root,
            environ=environ,
        )

        self.assertNotEqual(result, 0)
        text = summary.read_text()
        self.assertIn("install:", text)
        self.assertIn("— FAIL", text)
        self.assertNotIn("test:", text)
        self.assertIn("result: FAIL", text)

    def test_real_runner_fails_python_pyproject_test_fixture(self):
        root = self.copy_fixture("python-pyproject-fail")
        environ, summary = self.summary_environment(root)

        result = run_project(
            self.python_project_json("python-pyproject-fail", "python-pyproject", "pyproject.toml"),
            root,
            environ=environ,
        )

        self.assertNotEqual(result, 0)
        text = summary.read_text()
        self.assertIn("install:", text)
        self.assertIn("— PASS", text)
        self.assertIn("test: `.dependency-gate-venv/bin/python -m pytest` — FAIL", text)
        self.assertIn("result: FAIL", text)


if __name__ == "__main__":
    unittest.main()
