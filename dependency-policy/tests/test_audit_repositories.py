from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from lib.github_client import GitHubClient
from lib.models import Inventory, PolicyError, Project, Repository, load_inventory
from scripts.audit_repositories import (
    DiscoveredRepository,
    discover_repositories,
    main,
    reconcile,
)


class FakeGitHubClient:
    def __init__(self, repositories, trees=None, blobs=None):
        self._repositories = repositories
        self._trees = trees or {}
        self._blobs = blobs or {}

    def list_repositories(self, owner):
        return self._repositories

    def repository_tree(self, repository, default_branch):
        return self._trees[repository]

    def blob_text(self, repository, sha):
        return self._blobs[(repository, sha)]


class GitHubClientTest(unittest.TestCase):
    def test_runs_repo_list_and_api_as_json_only_commands(self):
        calls = []
        responses = [
            subprocess.CompletedProcess([], 0, stdout='[{"name":"repo"}]', stderr=""),
            subprocess.CompletedProcess([], 0, stdout='{"tree":[],"truncated":false}', stderr=""),
        ]

        def runner(command):
            calls.append(command)
            return responses.pop(0)

        client = GitHubClient(runner=runner)

        self.assertEqual(client.list_repositories("owner"), [{"name": "repo"}])
        self.assertEqual(client.repository_tree("owner/repo", "main"), [])
        self.assertEqual(
            calls,
            [
                [
                    "gh", "repo", "list", "owner", "--limit", "1000", "--source",
                    "--json", "name,nameWithOwner,isArchived,defaultBranchRef",
                ],
                ["gh", "api", "repos/owner/repo/git/trees/main?recursive=1"],
            ],
        )

    def test_decodes_blob_text_and_fails_closed_without_echoing_process_output(self):
        responses = [
            subprocess.CompletedProcess([], 0, stdout='{"encoding":"base64","content":"aGVsbG8=\\n"}', stderr=""),
            subprocess.CompletedProcess([], 7, stdout="secret stdout", stderr="secret stderr"),
        ]
        client = GitHubClient(runner=lambda command: responses.pop(0))

        self.assertEqual(client.blob_text("owner/repo", "abc123"), "hello")
        with self.assertRaisesRegex(PolicyError, "GitHub CLI command failed with exit code 7") as raised:
            client.list_repositories("owner")
        self.assertNotIn("secret", str(raised.exception))

    def test_rejects_truncated_trees_and_non_json_responses(self):
        responses = [
            subprocess.CompletedProcess([], 0, stdout='{"tree":[],"truncated":true}', stderr=""),
            subprocess.CompletedProcess([], 0, stdout="not json", stderr=""),
        ]
        client = GitHubClient(runner=lambda command: responses.pop(0))

        with self.assertRaisesRegex(PolicyError, "truncated"):
            client.repository_tree("owner/repo", "main")
        with self.assertRaisesRegex(PolicyError, "invalid JSON"):
            client.list_repositories("owner")


class AuditRepositoriesTest(unittest.TestCase):
    def repository_record(self, name, *, archived=False, default_branch="main"):
        return {
            "name": name,
            "nameWithOwner": f"owner/{name}",
            "isArchived": archived,
            "defaultBranchRef": (
                {"name": default_branch} if default_branch is not None else None
            ),
        }

    def test_branchless_repositories_are_reported_without_aborting_discovery(self):
        client = FakeGitHubClient([
            self.repository_record("active-empty", default_branch=None),
            self.repository_record("archived-empty", archived=True, default_branch=None),
        ])
        inventory = Inventory(
            schema_version=1,
            repositories=(
                Repository(
                    name="archived-empty",
                    default_branch="main",
                    projects=(Project("actions", "github-actions", ".", timeout_minutes=5),),
                ),
            ),
        )

        discovered = discover_repositories(client, "owner")
        report = reconcile(inventory, discovered)

        self.assertEqual(
            [(repository.name, repository.default_branch) for repository in discovered],
            [("active-empty", None), ("archived-empty", None)],
        )
        self.assertEqual(report.archived, ("archived-empty",))
        self.assertEqual(report.unclassified, ("active-empty",))
        self.assertEqual(
            report.ambiguities,
            ("active-empty: active repository has no default branch",),
        )
        self.assertEqual(report.inventory.repositories, ())

    def tree_entry(self, path, sha):
        return {"path": path, "mode": "100644", "type": "blob", "sha": sha}

    def discovery_client(self):
        paths = [
            "package.json",
            "package-lock.json",
            "services/api/requirements.txt",
            "services/modern/pyproject.toml",
            "android/build.gradle.kts",
            "android/gradlew",
            "nested/web/package.json",
            "nested/web/package-lock.json",
            ".github/dependabot.yml",
            ".github/workflows/dependabot-auto-merge.yml",
            ".github/workflows/deploy-production.yml",
            "dotnet/App.csproj",
            "UnityProject/Packages/manifest.json",
            "rust/Cargo.toml",
            "go/go.mod",
        ]
        trees = {
            "owner/active": [self.tree_entry(path, f"sha-{index}") for index, path in enumerate(paths)],
            "owner/archived": [],
        }
        blobs = {
            ("owner/active", f"sha-{paths.index('package.json')}"): "{}",
            ("owner/active", f"sha-{paths.index('nested/web/package.json')}"): "{}",
            ("owner/active", f"sha-{paths.index('.github/dependabot.yml')}"): """
version: 2
updates:
  - package-ecosystem: npm
    directory: /
  - package-ecosystem: nuget
    directory: /dotnet
  - package-ecosystem: cargo
    directory: /rust
  - package-ecosystem: gomod
    directory: /go
""",
            ("owner/active", f"sha-{paths.index('.github/workflows/dependabot-auto-merge.yml')}"): """
name: Dependabot Auto Merge
on: pull_request
jobs:
  merge:
    runs-on: ubuntu-latest
    steps:
      - run: gh pr merge --auto --squash "$PR_URL"
""",
            ("owner/active", f"sha-{paths.index('.github/workflows/deploy-production.yml')}"): """
name: Deploy production
on:
  push:
    branches: [main]
jobs:
  deploy:
    environment: production
    steps:
      - run: npm run deploy
""",
        }
        return FakeGitHubClient(
            [self.repository_record("archived", archived=True), self.repository_record("active")],
            trees,
            blobs,
        )

    def test_discovers_supported_nested_projects_policy_and_workflow_paths_deterministically(self):
        discovered = discover_repositories(self.discovery_client(), "owner")

        self.assertEqual([repository.name for repository in discovered], ["active", "archived"])
        active = discovered[0]
        self.assertEqual(
            [(project.name, project.ecosystem, project.path, project.manifest) for project in active.projects],
            [
                ("android-gradle", "gradle", "android", "build.gradle.kts"),
                ("nested-web-node", "npm", "nested/web", "package.json"),
                ("root-node", "npm", ".", "package.json"),
                ("services-api-python-requirements", "python-requirements", "services/api", "requirements.txt"),
                ("services-modern-python-pyproject", "python-pyproject", "services/modern", "pyproject.toml"),
            ],
        )
        self.assertEqual(active.projects[0].gradle_wrapper, "gradlew")
        self.assertEqual(active.projects[1].lockfile, "package-lock.json")
        self.assertEqual(active.dependabot_config, ".github/dependabot.yml")
        self.assertEqual(active.auto_merge_workflows, (".github/workflows/dependabot-auto-merge.yml",))
        self.assertEqual(active.deployment_workflows, (".github/workflows/deploy-production.yml",))
        self.assertEqual(active.workflow_paths, (
            ".github/workflows/dependabot-auto-merge.yml",
            ".github/workflows/deploy-production.yml",
        ))
        self.assertEqual(active.unsupported_ecosystems, ("cargo", "go", "nuget", "unity"))
        self.assertFalse(active.auto_merge_enabled)
        self.assertTrue(discovered[1].archived)

    def test_reports_new_active_and_newly_archived_repositories_separately(self):
        inventory = Inventory(
            schema_version=1,
            repositories=(
                Repository(
                    name="archived",
                    default_branch="main",
                    projects=(Project("actions", "github-actions", ".", timeout_minutes=5),),
                ),
            ),
        )

        report = reconcile(inventory, discover_repositories(self.discovery_client(), "owner"))

        self.assertEqual(report.unclassified, ("active",))
        self.assertEqual(report.archived, ("archived",))
        self.assertEqual([repository.name for repository in report.inventory.repositories], ["active"])
        self.assertFalse(report.inventory.repository("active").auto_merge_enabled)

    def test_reconciliation_preserves_reviewed_runtime_commands_and_timeout(self):
        reviewed = Project(
            name="frontend",
            ecosystem="npm",
            path=".",
            runtime_version="18.19.1",
            manifest="package.json",
            lockfile="package-lock.json",
            install_command="npm ci --ignore-scripts",
            test_command="npm run test:ci",
            build_command="npm run build:prod",
            timeout_minutes=23,
        )
        inventory = Inventory(
            schema_version=1,
            repositories=(Repository("active", "trunk", (reviewed,)),),
        )
        discovered = discover_repositories(self.discovery_client(), "owner")

        report = reconcile(inventory, discovered)
        project = next(
            project
            for project in report.inventory.repository("active").projects
            if project.ecosystem == "npm" and project.path == "."
        )

        self.assertEqual(project.name, "frontend")
        self.assertEqual(project.runtime_version, "18.19.1")
        self.assertEqual(project.install_command, "npm ci --ignore-scripts")
        self.assertEqual(project.test_command, "npm run test:ci")
        self.assertEqual(project.build_command, "npm run build:prod")
        self.assertEqual(project.timeout_minutes, 23)
        self.assertEqual(report.inventory.repository("active").default_branch, "main")

    def test_reconciliation_reports_python_manifest_disagreement_and_preserves_review(self):
        reviewed = Project(
            name="reviewed-python",
            ecosystem="python-requirements",
            path=".",
            runtime_version="3.12",
            manifest="requirements-prod.txt",
            timeout_minutes=15,
        )
        discovered_project = Project(
            name="root-python-requirements",
            ecosystem="python-requirements",
            path=".",
            runtime_version="3.12",
            manifest="requirements.txt",
            timeout_minutes=15,
        )

        report = reconcile(
            Inventory(1, (Repository("python", "main", (reviewed,)),)),
            (DiscoveredRepository("python", "main", False, (discovered_project,)),),
        )

        project = report.inventory.repository("python").projects[0]
        self.assertEqual(project.manifest, "requirements-prod.txt")
        self.assertEqual(len(report.ambiguities), 1)
        self.assertIn("python-requirements project at . manifest differs", report.ambiguities[0])

    def test_reconciliation_reports_npm_lockfile_disagreement_and_preserves_review(self):
        reviewed = Project(
            name="reviewed-node",
            ecosystem="npm",
            path=".",
            runtime_version="20",
            manifest="package.json",
            lockfile="npm-shrinkwrap.json",
            timeout_minutes=15,
        )
        discovered_project = Project(
            name="root-node",
            ecosystem="npm",
            path=".",
            runtime_version="20",
            manifest="package.json",
            lockfile="package-lock.json",
            timeout_minutes=15,
        )

        report = reconcile(
            Inventory(1, (Repository("node", "main", (reviewed,)),)),
            (DiscoveredRepository("node", "main", False, (discovered_project,)),),
        )

        project = report.inventory.repository("node").projects[0]
        self.assertEqual(project.lockfile, "npm-shrinkwrap.json")
        self.assertEqual(len(report.ambiguities), 1)
        self.assertIn("npm project at . lockfile differs", report.ambiguities[0])

    def test_reconciliation_fails_closed_on_ambiguous_reviewed_project_identity(self):
        duplicate_identity = (
            Project("first", "npm", ".", "18", "package.json", timeout_minutes=15),
            Project("second", "npm", ".", "20", "package.json", timeout_minutes=15),
        )
        inventory = Inventory(
            schema_version=1,
            repositories=(Repository("active", "main", duplicate_identity),),
        )

        report = reconcile(inventory, discover_repositories(self.discovery_client(), "owner"))

        self.assertEqual(len(report.ambiguities), 1)
        self.assertIn("active: npm project at .", report.ambiguities[0])

    def test_missing_gradle_wrapper_is_ambiguous_and_cannot_be_written(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "repositories.json"
            path.write_text(json.dumps({"schema-version": 1, "repositories": []}) + "\n")
            before = path.read_bytes()
            client = FakeGitHubClient(
                [self.repository_record("gradle")],
                {"owner/gradle": [self.tree_entry("build.gradle.kts", "manifest")]},
            )

            discovered = discover_repositories(client, "owner")
            report = reconcile(Inventory(1, ()), discovered)
            self.assertIn("missing gradlew", report.ambiguities[0])

            with redirect_stdout(io.StringIO()):
                result = main(
                    ["--owner", "owner", "--write", str(path)],
                    client=client,
                    inventory_path=path,
                )
            self.assertEqual(result, 2)
            self.assertEqual(path.read_bytes(), before)

    def test_bun_package_manager_without_lockfile_disables_auto_merge(self):
        client = FakeGitHubClient(
            [self.repository_record("bun-project")],
            {"owner/bun-project": [
                self.tree_entry("package.json", "package"),
            ]},
            {
                ("owner/bun-project", "package"): json.dumps({
                    "name": "bun-project",
                    "packageManager": "bun@1.2.21",
                }),
            },
        )

        repository = discover_repositories(client, "owner")[0]

        self.assertEqual(repository.projects[0].ecosystem, "npm")
        self.assertEqual(repository.projects[0].lockfile, None)
        self.assertEqual(repository.unsupported_ecosystems, ("bun",))
        self.assertFalse(repository.auto_merge_enabled)

    def test_security_workflow_product_mentions_are_not_deployment_triggers(self):
        client = FakeGitHubClient(
            [self.repository_record("security")],
            {"owner/security": [
                self.tree_entry(".github/workflows/security.yml", "workflow"),
            ]},
            {
                ("owner/security", "workflow"): """
name: Secret scanning
on: pull_request
jobs:
  scan:
    steps:
      # Detect accidentally committed Vercel and Netlify credentials.
      - run: python scan_secrets.py
""",
            },
        )

        repository = discover_repositories(client, "owner")[0]

        self.assertEqual(repository.deployment_workflows, ())

    def test_bun_managed_node_project_disables_auto_merge_until_adapter_exists(self):
        client = FakeGitHubClient(
            [self.repository_record("bun-project")],
            {"owner/bun-project": [
                self.tree_entry("package.json", "package"),
                self.tree_entry("bun.lock", "lock"),
            ]},
            {("owner/bun-project", "package"): "{}"},
        )

        repository = discover_repositories(client, "owner")[0]

        self.assertEqual(repository.projects[0].ecosystem, "npm")
        self.assertEqual(repository.unsupported_ecosystems, ("bun",))
        self.assertFalse(repository.auto_merge_enabled)

    def test_unsupported_dependabot_config_disables_auto_merge_without_manifest(self):
        client = FakeGitHubClient(
            [self.repository_record("unity")],
            {"owner/unity": [
                self.tree_entry(".github/dependabot.yml", "dependabot"),
            ]},
            {
                ("owner/unity", "dependabot"): """
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
  - package-ecosystem: "nuget"
    directory: "/"
""",
            },
        )

        repository = discover_repositories(client, "owner")[0]

        self.assertEqual(repository.unsupported_ecosystems, ("nuget",))
        self.assertFalse(repository.auto_merge_enabled)

    def test_repository_with_only_unsupported_application_manifest_gets_manual_actions_project(self):
        client = FakeGitHubClient(
            [self.repository_record("dotnet")],
            {"owner/dotnet": [
                self.tree_entry("App.csproj", "project"),
                self.tree_entry(".github/workflows/build.yml", "workflow"),
            ]},
            {("owner/dotnet", "workflow"): "name: Build\non: pull_request\n"},
        )

        repository = discover_repositories(client, "owner")[0]

        self.assertEqual(
            [(project.name, project.ecosystem, project.path) for project in repository.projects],
            [("github-actions", "github-actions", ".")],
        )
        self.assertEqual(repository.unsupported_ecosystems, ("nuget",))
        self.assertFalse(repository.auto_merge_enabled)

    def test_default_cli_is_dry_run_and_only_explicit_write_changes_inventory(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "repositories.json"
            path.write_text(json.dumps({"schema-version": 1, "repositories": []}, indent=2) + "\n")
            before = path.read_bytes()
            client = FakeGitHubClient(
                [self.repository_record("new-repo")],
                {"owner/new-repo": []},
            )

            with redirect_stdout(io.StringIO()):
                dry_run = main(["--owner", "owner"], client=client, inventory_path=path)
            self.assertEqual(dry_run, 0)
            self.assertEqual(path.read_bytes(), before)

            with redirect_stdout(io.StringIO()):
                written = main(
                    ["--owner", "owner", "--write", str(path)],
                    client=client,
                    inventory_path=path,
                )
            self.assertEqual(written, 0)
            self.assertEqual([repo.name for repo in load_inventory(path).repositories], ["new-repo"])

    def test_check_fails_for_unclassified_or_ambiguous_state(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "repositories.json"
            path.write_text(json.dumps({"schema-version": 1, "repositories": []}))
            client = FakeGitHubClient(
                [self.repository_record("new-repo")],
                {"owner/new-repo": []},
            )

            with redirect_stdout(io.StringIO()):
                result = main(
                    ["--owner", "owner", "--check"],
                    client=client,
                    inventory_path=path,
                )

            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
