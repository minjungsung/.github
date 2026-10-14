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
                    "timeout-minutes": 15
                }]
            }]
        })
        inventory = load_inventory(path)
        self.assertEqual(inventory.repository("portfolio-frontend-inner").projects[0].ecosystem, "npm")

    def test_rejects_unknown_fields(self):
        path = self.write_inventory({"schema-version": 1, "repositories": [], "surprise": True})
        with self.assertRaisesRegex(PolicyError, "unknown field"):
            load_inventory(path)

    def test_rejects_duplicate_repository_and_project_names(self):
        repository = {
            "name": "duplicate",
            "default-branch": "main",
            "projects": [
                {"name": "same", "ecosystem": "github-actions", "path": "."},
                {"name": "same", "ecosystem": "github-actions", "path": "."}
            ]
        }
        path = self.write_inventory({"schema-version": 1, "repositories": [repository, repository]})
        with self.assertRaises(PolicyError):
            load_inventory(path)

    def test_rejects_escaping_path_unknown_ecosystem_and_timeout_over_45(self):
        for project in (
            {"name": "bad", "ecosystem": "npm", "path": "../outside"},
            {"name": "bad", "ecosystem": "nuget", "path": "."},
            {"name": "bad", "ecosystem": "npm", "path": ".", "timeout-minutes": 46},
        ):
            path = self.write_inventory({
                "schema-version": 1,
                "repositories": [{"name": "repo", "default-branch": "main", "projects": [project]}]
            })
            with self.subTest(project=project), self.assertRaises(PolicyError):
                load_inventory(path)
