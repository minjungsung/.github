from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib.commands import CommandPlan, plan_commands, reject_forbidden
from lib.models import PolicyError, Project


class CommandsTest(unittest.TestCase):
    def make_root(self, files):
        temp = TemporaryDirectory()
        root = Path(temp.name)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.addCleanup(temp.cleanup)
        return root

    def project(self, ecosystem, **overrides):
        values = {
            "name": "fixture",
            "ecosystem": ecosystem,
            "path": ".",
            "runtime_version": "20" if ecosystem == "npm" else "3.12",
            "manifest": "package.json" if ecosystem == "npm" else None,
            "timeout_minutes": 15,
        }
        values.update(overrides)
        return Project(**values)

    def test_plans_strict_npm_commands_from_manifest(self):
        root = self.make_root({
            "package.json": json.dumps({"scripts": {"test": "node test.js", "build": "node build.js"}}),
            "package-lock.json": "{}",
        })
        plan = plan_commands(self.project("npm", lockfile="package-lock.json"), root)
        self.assertEqual(plan.install, ("npm", "ci"))
        self.assertEqual(plan.test, ("npm", "test", "--", "--watchAll=false"))
        self.assertEqual(plan.build, ("npm", "run", "build"))
        self.assertEqual(plan.skips, ())

    def test_rejects_npmrc_and_script_failure_bypasses(self):
        for files in ({'package.json': '{}', '.npmrc': 'legacy-peer-deps=true\n'},
                      {'package.json': json.dumps({'scripts': {'test': 'false || true'}})},
                      {'package.json': json.dumps({'scripts': {'build': 'false; echo success'}})}):
            root = self.make_root(files)
            with self.assertRaises(PolicyError):
                plan_commands(self.project('npm'), root)

    def test_shell_swallowing_rejected_but_literals_and_and_sequences_allowed(self):
        for command in ('false || :', 'false; echo done', 'false | true'):
            with self.assertRaises(PolicyError):
                reject_forbidden(command, shell_syntax=True)
        for command in ("printf 'literal || and ; text'", 'python -m venv env && env/bin/python -m pip install .'):
            reject_forbidden(command, shell_syntax=True)

    def test_python_configured_pytest_paths_are_detected(self):
        for config, text in [('pyproject.toml', '[tool.pytest.ini_options]\ntestpaths=["spec"]\n'),
                             ('setup.cfg', '[tool:pytest]\ntestpaths=spec\n')]:
            root = self.make_root({config: text, 'requirements.txt': '', 'spec/test_example.py': 'assert False'})
            plan = plan_commands(self.project('python-requirements', manifest='requirements.txt'), root)
            self.assertIsNotNone(plan.test)

    def test_python_venv_symlink_rejected_without_deleting_target(self):
        root = self.make_root({'requirements.txt': '', 'outside/evidence': 'preserve'})
        (root / '.dependency-gate-venv').symlink_to(root / 'outside', target_is_directory=True)
        with self.assertRaises(PolicyError):
            plan_commands(self.project('python-requirements', manifest='requirements.txt'), root)
        self.assertEqual((root / 'outside/evidence').read_text(), 'preserve')

    def test_uses_npm_install_when_no_lockfile_is_configured(self):
        root = self.make_root({"package.json": json.dumps({"scripts": {}})})
        plan = plan_commands(self.project("npm"), root)
        self.assertEqual(plan.install, ("npm", "install"))

    def test_explicit_commands_override_defaults(self):
        root = self.make_root({"package.json": json.dumps({"scripts": {}})})
        project = self.project(
            "npm",
            install_command="npm install --strict-peer-deps",
            test_command="npm run test:ci",
            build_command="npm run compile",
        )
        plan = plan_commands(project, root)
        self.assertEqual(plan.install, "npm install --strict-peer-deps")
        self.assertEqual(plan.test, "npm run test:ci")
        self.assertEqual(plan.build, "npm run compile")
        self.assertEqual(plan.skips, ())

    def test_absent_npm_scripts_are_explicit_skips(self):
        root = self.make_root({"package.json": json.dumps({"scripts": {"lint": "node lint.js"}})})
        plan = plan_commands(self.project("npm"), root)
        self.assertIsNone(plan.test)
        self.assertIsNone(plan.build)
        self.assertEqual(plan.skips, ("test", "build"))

    def test_plans_requirements_venv_pip_and_pytest(self):
        root = self.make_root({"requirements.txt": "", "test_fixture.py": "def test_ok():\n    assert True\n"})
        project = self.project(
            "python-requirements",
            manifest="requirements.txt",
            runtime_version="3.12",
        )
        plan = plan_commands(project, root)
        self.assertIn("python3 -m venv --clear .dependency-gate-venv", plan.install)
        self.assertIn(".dependency-gate-venv/bin/python -m pip install -r requirements.txt", plan.install)
        self.assertIn(".dependency-gate-venv/bin/python -m pip install pytest", plan.install)
        self.assertNotIn("pip install --upgrade pip", plan.install)
        self.assertEqual(plan.test, (".dependency-gate-venv/bin/python", "-m", "pytest"))
        self.assertIsNone(plan.build)
        self.assertEqual(plan.skips, ("build",))

    def test_plans_pyproject_install_and_pytest(self):
        root = self.make_root({
            "pyproject.toml": "[build-system]\nrequires = []\nbuild-backend = 'build_backend'\n",
            "tests/test_fixture.py": "def test_ok():\n    assert True\n",
        })
        project = self.project(
            "python-pyproject",
            manifest="pyproject.toml",
            runtime_version="3.12",
        )
        plan = plan_commands(project, root)
        self.assertIn(".dependency-gate-venv/bin/python -m pip install .", plan.install)
        self.assertEqual(plan.test, (".dependency-gate-venv/bin/python", "-m", "pytest"))
        self.assertEqual(plan.skips, ("build",))

    def test_python_without_tests_does_not_install_pytest(self):
        root = self.make_root({"requirements.txt": ""})
        project = self.project(
            "python-requirements",
            manifest="requirements.txt",
            runtime_version="3.12",
        )

        plan = plan_commands(project, root)

        self.assertNotIn("pip install pytest", plan.install)
        self.assertIsNone(plan.test)
        self.assertEqual(plan.skips, ("test", "build"))

    def test_plans_gradle_wrapper_check_without_daemon(self):
        root = self.make_root({"build.gradle.kts": "", "gradlew": "#!/usr/bin/env bash\n"})
        project = self.project(
            "gradle",
            runtime_version="21",
            manifest="build.gradle.kts",
            gradle_wrapper="gradlew",
            timeout_minutes=30,
        )
        plan = plan_commands(project, root)
        self.assertIsNone(plan.install)
        self.assertEqual(plan.test, ("./gradlew", "--no-daemon", "check"))
        self.assertIsNone(plan.build)
        self.assertEqual(plan.skips, ("install", "build"))

    def test_plans_actionlint_with_non_applicable_phases_skipped(self):
        root = self.make_root({".github/workflows/ci.yml": "name: CI\n"})
        project = self.project("github-actions", runtime_version=None, manifest=None, timeout_minutes=5)
        plan = plan_commands(project, root)
        self.assertIsNone(plan.install)
        self.assertEqual(plan.test, ("actionlint",))
        self.assertIsNone(plan.build)
        self.assertEqual(plan.skips, ("install", "build"))

    def test_rejects_missing_configured_files_instead_of_falling_back(self):
        cases = (
            (self.project("npm", manifest="missing.json"), "manifest"),
            (self.project("npm", lockfile="missing-lock.json"), "lockfile"),
            (
                self.project("gradle", runtime_version="21", manifest="build.gradle.kts", gradle_wrapper="missing"),
                "manifest",
            ),
        )
        for project, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(PolicyError, expected):
                plan_commands(project, self.make_root({"package.json": "{}"}))

    def test_rejects_malformed_npm_manifest(self):
        with self.assertRaisesRegex(PolicyError, "manifest"):
            plan_commands(self.project("npm"), self.make_root({"package.json": "not-json"}))

    def test_rejects_every_forbidden_fragment_case_insensitively(self):
        fragments = (
            "--legacy-peer-deps",
            " --force",
            "|| true",
            "--exit-zero",
            "continue-on-error",
            "2>/dev/null",
        )
        for fragment in fragments:
            with self.subTest(fragment=fragment), self.assertRaisesRegex(PolicyError, "forbidden"):
                reject_forbidden(f"RUN {fragment.upper()}")

    def test_command_plan_is_immutable(self):
        plan = CommandPlan(None, None, None, ("install", "test", "build"))
        with self.assertRaises(FrozenInstanceError):
            plan.install = ("changed",)


if __name__ == "__main__":
    unittest.main()
