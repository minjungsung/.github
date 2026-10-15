from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib.models import PolicyError, load_inventory


class ModelsTest(unittest.TestCase):
    def write_inventory(self, value):
        temp = TemporaryDirectory()
        path = Path(temp.name) / "repositories.json"
        path.write_text(json.dumps(value))
        self.addCleanup(temp.cleanup)
        return path

    def write_projects(self, projects):
        return self.write_inventory({
            "schema-version": 1,
            "repositories": [{
                "name": "repo",
                "default-branch": "main",
                "projects": projects,
            }],
        })

    def valid_project(self, ecosystem):
        project = {"name": ecosystem, "ecosystem": ecosystem, "path": "."}
        if ecosystem in {"npm", "python-requirements", "python-pyproject"}:
            project.update({"runtime-version": "3.12", "manifest": "manifest.txt"})
        elif ecosystem == "gradle":
            project.update({
                "runtime-version": "21",
                "manifest": "build.gradle",
                "gradle-wrapper": "gradlew",
            })
        return project

    def test_loads_valid_npm_project(self):
        path = self.write_inventory({
            "schema-version": 1,
            "repositories": [{
                "name": "portfolio-frontend-inner",
                "default-branch": "main",
                "deployment-workflows": ["vercel:production-from-main"],
                "projects": [{
                    "name": "root-node",
                    "ecosystem": "npm",
                    "path": ".",
                    "runtime-version": "20",
                    "manifest": "package.json",
                    "lockfile": "package-lock.json",
                    "timeout-minutes": 15,
                }],
            }],
        })
        inventory = load_inventory(path)
        self.assertEqual(inventory.repository("portfolio-frontend-inner").projects[0].ecosystem, "npm")

    def test_auto_merge_defaults_to_true(self):
        repository = load_inventory(self.write_projects([
            self.valid_project("github-actions"),
        ])).repository("repo")
        self.assertTrue(repository.auto_merge_enabled)

    def test_models_are_frozen(self):
        inventory = load_inventory(self.write_projects([
            self.valid_project("github-actions"),
        ]))
        repository = inventory.repository("repo")
        project = repository.projects[0]

        for instance, field, value in (
            (inventory, "schema_version", 2),
            (repository, "name", "changed"),
            (project, "path", "changed"),
        ):
            with self.subTest(instance=type(instance).__name__), self.assertRaises(FrozenInstanceError):
                setattr(instance, field, value)

    def test_rejects_boolean_schema_version(self):
        path = self.write_inventory({"schema-version": True, "repositories": []})
        with self.assertRaisesRegex(PolicyError, "schema-version must equal 1"):
            load_inventory(path)

    def test_rejects_non_1_schema_versions(self):
        for schema_version in (-1, 0, 2):
            path = self.write_inventory({"schema-version": schema_version, "repositories": []})
            with self.subTest(schema_version=schema_version), self.assertRaisesRegex(
                PolicyError, "schema-version must equal 1"
            ):
                load_inventory(path)

    def test_rejects_non_integer_schema_versions(self):
        for schema_version in (1.0, "1", None):
            path = self.write_inventory({"schema-version": schema_version, "repositories": []})
            with self.subTest(schema_version=schema_version), self.assertRaisesRegex(
                PolicyError, "schema-version must equal 1"
            ):
                load_inventory(path)

    def test_rejects_unknown_inventory_field(self):
        path = self.write_inventory({"schema-version": 1, "repositories": [], "surprise": True})
        with self.assertRaisesRegex(PolicyError, "inventory: unknown field"):
            load_inventory(path)

    def test_rejects_unknown_repository_field(self):
        path = self.write_inventory({
            "schema-version": 1,
            "repositories": [{
                "name": "repo",
                "default-branch": "main",
                "projects": [self.valid_project("github-actions")],
                "surprise": True,
            }],
        })
        with self.assertRaisesRegex(PolicyError, r"repositories\[0\]: unknown field"):
            load_inventory(path)

    def test_rejects_unknown_project_field(self):
        project = self.valid_project("github-actions")
        project["surprise"] = True
        with self.assertRaisesRegex(PolicyError, r"repositories\[0\]\.projects\[0\]: unknown field"):
            load_inventory(self.write_projects([project]))

    def test_rejects_duplicate_repository_names(self):
        repositories = [
            {
                "name": "duplicate",
                "default-branch": "main",
                "projects": [{"name": "first", "ecosystem": "github-actions", "path": "."}],
            },
            {
                "name": "duplicate",
                "default-branch": "main",
                "projects": [{"name": "second", "ecosystem": "github-actions", "path": "."}],
            },
        ]
        path = self.write_inventory({"schema-version": 1, "repositories": repositories})
        with self.assertRaisesRegex(PolicyError, "duplicate repository name"):
            load_inventory(path)

    def test_rejects_duplicate_project_names(self):
        projects = [
            {"name": "same", "ecosystem": "github-actions", "path": "."},
            {"name": "same", "ecosystem": "github-actions", "path": "workflows"},
        ]
        with self.assertRaisesRegex(PolicyError, "duplicate project name"):
            load_inventory(self.write_projects(projects))

    def test_rejects_escaping_path(self):
        project = self.valid_project("npm")
        project["path"] = "../outside"
        with self.assertRaisesRegex(PolicyError, "unsafe path"):
            load_inventory(self.write_projects([project]))

    def test_rejects_unknown_ecosystem(self):
        project = {"name": "bad", "ecosystem": "nuget", "path": "."}
        with self.assertRaisesRegex(PolicyError, "unknown ecosystem"):
            load_inventory(self.write_projects([project]))

    def test_timeout_boundaries_are_accepted(self):
        projects = []
        for name, timeout in (("minimum", 1), ("maximum", 45)):
            project = self.valid_project("npm")
            project.update({"name": name, "timeout-minutes": timeout})
            projects.append(project)

        loaded = load_inventory(self.write_projects(projects)).repository("repo").projects
        self.assertEqual([project.timeout_minutes for project in loaded], [1, 45])

    def test_timeout_defaults_by_ecosystem(self):
        expected = (
            ("npm", 15),
            ("python-requirements", 15),
            ("python-pyproject", 15),
            ("gradle", 30),
            ("github-actions", 5),
        )
        projects = [self.valid_project(ecosystem) for ecosystem, _ in expected]

        loaded = load_inventory(self.write_projects(projects)).repository("repo").projects
        self.assertEqual(
            [(project.ecosystem, project.timeout_minutes) for project in loaded],
            list(expected),
        )

    def test_rejects_invalid_timeouts(self):
        for timeout in (0, 46, True, 1.0):
            project = self.valid_project("npm")
            project["timeout-minutes"] = timeout
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                PolicyError, "timeout-minutes must be an integer from 1 to 45"
            ):
                load_inventory(self.write_projects([project]))

    def test_enforces_ecosystem_required_fields(self):
        required_fields = (
            ("npm", ("runtime-version", "manifest")),
            ("python-requirements", ("runtime-version", "manifest")),
            ("python-pyproject", ("runtime-version", "manifest")),
            ("gradle", ("runtime-version", "manifest", "gradle-wrapper")),
        )
        for ecosystem, fields in required_fields:
            for field in fields:
                project = self.valid_project(ecosystem)
                del project[field]
                with self.subTest(ecosystem=ecosystem, field=field), self.assertRaisesRegex(
                    PolicyError, field
                ):
                    load_inventory(self.write_projects([project]))
