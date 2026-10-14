import argparse
from dataclasses import dataclass, fields
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Sequence

from lib.github_client import GitHubClient
from lib.models import Inventory, PolicyError, Project, Repository, load_inventory


POLICY_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = POLICY_ROOT / "repositories.json"
DEFAULT_OWNER = "minjungsung"
DEFAULT_RUNTIMES = {
    "npm": "20",
    "python-requirements": "3.12",
    "python-pyproject": "3.12",
    "gradle": "21",
}
IGNORED_PARTS = {
    ".git",
    ".gradle",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "Pods",
    "target",
    "vendor",
}
SUPPORTED_DEPENDABOT_ECOSYSTEMS = {"github-actions", "npm", "pip", "gradle"}
DEPENDABOT_ECOSYSTEM_NAMES = {
    "bundler": "ruby-bundler",
    "cargo": "cargo",
    "composer": "php-composer",
    "docker": "docker",
    "gomod": "go",
    "maven": "maven",
    "nuget": "nuget",
    "pub": "dart-pub",
    "swift": "swift",
}
PROJECT_KEYS = {field.name: field.name.replace("_", "-") for field in fields(Project)}


@dataclass(frozen=True)
class DiscoveredRepository:
    name: str
    default_branch: str
    archived: bool
    projects: tuple[Project, ...] = ()
    dependabot_config: str | None = None
    workflow_paths: tuple[str, ...] = ()
    auto_merge_workflows: tuple[str, ...] = ()
    deployment_workflows: tuple[str, ...] = ()
    unsupported_ecosystems: tuple[str, ...] = ()
    auto_merge_enabled: bool = True
    ambiguities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditReport:
    inventory: Inventory
    unclassified: tuple[str, ...] = ()
    archived: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()


def _required_repository_fields(value: dict[str, Any]) -> tuple[str, str, bool]:
    name = value.get("name")
    full_name = value.get("nameWithOwner")
    archived = value.get("isArchived")
    default_branch = value.get("defaultBranchRef")
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(full_name, str)
        or not full_name
        or not isinstance(archived, bool)
        or not isinstance(default_branch, dict)
        or not isinstance(default_branch.get("name"), str)
        or not default_branch["name"]
    ):
        raise PolicyError("GitHub repository response is missing required fields")
    return name, full_name, archived


def _tree_files(tree: list[dict[str, Any]], repository: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path")
        sha = entry.get("sha")
        if not isinstance(path, str) or not path or not isinstance(sha, str) or not sha:
            raise PolicyError(f"GitHub tree contains an invalid blob for {repository}")
        if path in result:
            raise PolicyError(f"GitHub tree contains a duplicate path for {repository}: {path}")
        result[path] = sha
    return result


def _ignored(path: str) -> bool:
    return any(part in IGNORED_PARTS for part in PurePosixPath(path).parts[:-1])


def _parent(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "." if parent == "." else parent


def _relative_file(project_path: str, path: str) -> str:
    if project_path == ".":
        return path
    return str(PurePosixPath(path).relative_to(project_path))


def _project_name(project_path: str, suffix: str) -> str:
    prefix = "root" if project_path == "." else "-".join(PurePosixPath(project_path).parts)
    return f"{prefix}-{suffix}"


def _project(
    ecosystem: str,
    project_path: str,
    manifest_path: str,
    files: set[str],
) -> Project:
    lockfile = None
    gradle_wrapper = None
    if ecosystem == "npm":
        for candidate in ("package-lock.json", "npm-shrinkwrap.json"):
            full_path = candidate if project_path == "." else f"{project_path}/{candidate}"
            if full_path in files:
                lockfile = candidate
                break
        suffix = "node"
    elif ecosystem == "python-requirements":
        suffix = "python-requirements"
    elif ecosystem == "python-pyproject":
        suffix = "python-pyproject"
    elif ecosystem == "gradle":
        wrapper_path = "gradlew" if project_path == "." else f"{project_path}/gradlew"
        if wrapper_path in files:
            gradle_wrapper = "gradlew"
        suffix = "gradle"
    else:
        raise PolicyError(f"unsupported discovered ecosystem: {ecosystem}")
    return Project(
        name=_project_name(project_path, suffix),
        ecosystem=ecosystem,
        path=project_path,
        runtime_version=DEFAULT_RUNTIMES[ecosystem],
        manifest=_relative_file(project_path, manifest_path),
        lockfile=lockfile,
        gradle_wrapper=gradle_wrapper,
        timeout_minutes=30 if ecosystem == "gradle" else 15,
    )


def _discover_projects(files: set[str]) -> tuple[tuple[Project, ...], tuple[str, ...]]:
    candidates: dict[tuple[str, str], list[str]] = {}
    manifest_names = {
        "package.json": "npm",
        "requirements.txt": "python-requirements",
        "pyproject.toml": "python-pyproject",
        "build.gradle": "gradle",
        "build.gradle.kts": "gradle",
    }
    for path in sorted(files):
        if _ignored(path):
            continue
        ecosystem = manifest_names.get(PurePosixPath(path).name)
        if ecosystem is not None:
            candidates.setdefault((ecosystem, _parent(path)), []).append(path)

    projects: list[Project] = []
    ambiguities: list[str] = []
    for (ecosystem, project_path), manifests in sorted(candidates.items()):
        if len(manifests) > 1:
            ambiguities.append(
                f"{ecosystem} project at {project_path} has multiple manifests: "
                + ", ".join(manifests)
            )
        project = _project(ecosystem, project_path, manifests[0], files)
        if ecosystem == "gradle" and project.gradle_wrapper is None:
            ambiguities.append(
                f"gradle project at {project_path} is missing gradlew"
            )
        projects.append(project)
    names = [project.name for project in projects]
    if len(names) != len(set(names)):
        ambiguities.append("discovered project names are not unique")
    return tuple(sorted(projects, key=lambda project: project.name)), tuple(ambiguities)


def _manifest_unsupported_ecosystems(files: set[str]) -> set[str]:
    unsupported: set[str] = set()
    for path in files:
        if _ignored(path):
            continue
        pure = PurePosixPath(path)
        name = pure.name
        lowered = path.lower()
        if name.endswith((".csproj", ".fsproj", ".vbproj")) or name in {
            "packages.config", "Directory.Packages.props",
        }:
            unsupported.add("nuget")
        if len(pure.parts) >= 2 and pure.parts[-2:] == ("Packages", "manifest.json"):
            unsupported.add("unity")
        if name in {"bun.lock", "bun.lockb"}:
            unsupported.add("bun")
        if name == "Cargo.toml":
            unsupported.add("cargo")
        if name == "go.mod":
            unsupported.add("go")
        if lowered.endswith((".sln", ".slnx")):
            unsupported.add("nuget")
    return unsupported


def _dependabot_ecosystems(content: str) -> set[str]:
    values = re.findall(
        r"(?im)^\s*(?:-\s*)?(?:package-ecosystem|package_ecosystem)\s*:\s*['\"]?([^\s#'\"]+)",
        content,
    )
    unsupported: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_DEPENDABOT_ECOSYSTEMS:
            unsupported.add(DEPENDABOT_ECOSYSTEM_NAMES.get(normalized, normalized))
    return unsupported


def _is_auto_merge_workflow(path: str, content: str) -> bool:
    searchable = f"{path}\n{content}".lower()
    return "dependabot" in searchable and (
        "gh pr merge" in searchable
        or "pull-requests: write" in searchable
        or ("auto" in searchable and "merge" in searchable)
    )


def _is_deployment_workflow(path: str, content: str) -> bool:
    stem = PurePosixPath(path).stem.lower()
    if re.search(r"(?:^|[-_])(deploy|publish)(?:[-_]|$)", stem):
        return True

    executable_lines = [
        line.lower()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for line in executable_lines:
        if re.match(r"^\s*name\s*:\s*.*\b(deploy|publish)\b", line):
            return True
        if re.match(r"^\s*(deploy|publish)\s*:", line):
            return True
        if re.search(r"environment\s*:\s*['\"]?production\b", line):
            return True
        if any(marker in line for marker in (
            "actions/deploy-pages@",
            "firebase deploy",
            "gh release create",
            "netlify deploy",
            "npm publish",
            "vercel deploy",
        )):
            return True
    return False


def discover_repositories(
    client: GitHubClient,
    owner: str = DEFAULT_OWNER,
) -> tuple[DiscoveredRepository, ...]:
    discovered: list[DiscoveredRepository] = []
    records = sorted(client.list_repositories(owner), key=lambda value: str(value.get("name", "")))
    for record in records:
        name, full_name, archived = _required_repository_fields(record)
        default_branch_value = record["defaultBranchRef"]
        default_branch = default_branch_value["name"]
        if archived:
            discovered.append(DiscoveredRepository(name, default_branch, True))
            continue

        files_by_path = _tree_files(client.repository_tree(full_name, default_branch), full_name)
        file_paths = set(files_by_path)
        projects, ambiguities = _discover_projects(file_paths)
        dependabot_config = (
            ".github/dependabot.yml"
            if ".github/dependabot.yml" in files_by_path
            else ".github/dependabot.yaml"
            if ".github/dependabot.yaml" in files_by_path
            else None
        )
        unsupported = _manifest_unsupported_ecosystems(file_paths)
        if dependabot_config is not None:
            unsupported.update(
                _dependabot_ecosystems(
                    client.blob_text(full_name, files_by_path[dependabot_config])
                )
            )

        workflow_paths = tuple(sorted(
            path
            for path in files_by_path
            if PurePosixPath(path).parent == PurePosixPath(".github/workflows")
            and PurePosixPath(path).suffix.lower() in {".yml", ".yaml"}
        ))
        auto_merge_workflows: list[str] = []
        deployment_workflows: list[str] = []
        for workflow_path in workflow_paths:
            content = client.blob_text(full_name, files_by_path[workflow_path])
            if _is_auto_merge_workflow(workflow_path, content):
                auto_merge_workflows.append(workflow_path)
            if _is_deployment_workflow(workflow_path, content):
                deployment_workflows.append(workflow_path)

        if not projects:
            projects = (Project(
                name="github-actions",
                ecosystem="github-actions",
                path=".",
                timeout_minutes=5,
            ),)
        discovered.append(DiscoveredRepository(
            name=name,
            default_branch=default_branch,
            archived=False,
            projects=projects,
            dependabot_config=dependabot_config,
            workflow_paths=workflow_paths,
            auto_merge_workflows=tuple(auto_merge_workflows),
            deployment_workflows=tuple(deployment_workflows),
            unsupported_ecosystems=tuple(sorted(unsupported)),
            auto_merge_enabled=not unsupported,
            ambiguities=ambiguities,
        ))
    return tuple(discovered)


def _merge_project(reviewed: Project, discovered: Project) -> Project:
    return Project(
        name=reviewed.name,
        ecosystem=discovered.ecosystem,
        path=discovered.path,
        runtime_version=reviewed.runtime_version or discovered.runtime_version,
        manifest=discovered.manifest,
        lockfile=discovered.lockfile,
        install_command=reviewed.install_command,
        test_command=reviewed.test_command,
        build_command=reviewed.build_command,
        gradle_wrapper=reviewed.gradle_wrapper or discovered.gradle_wrapper,
        timeout_minutes=reviewed.timeout_minutes,
    )


def _merge_repository(
    reviewed: Repository,
    discovered: DiscoveredRepository,
) -> tuple[Repository, tuple[str, ...]]:
    existing_by_identity: dict[tuple[str, str], list[Project]] = {}
    for project in reviewed.projects:
        existing_by_identity.setdefault((project.ecosystem, project.path), []).append(project)

    merged: list[Project] = []
    ambiguities: list[str] = []
    discovered_identities: set[tuple[str, str]] = set()
    for project in discovered.projects:
        identity = (project.ecosystem, project.path)
        discovered_identities.add(identity)
        matches = existing_by_identity.get(identity, [])
        if len(matches) == 1:
            merged.append(_merge_project(matches[0], project))
        elif not matches:
            merged.append(project)
        else:
            ambiguities.append(
                f"{reviewed.name}: {project.ecosystem} project at {project.path} "
                "matches multiple reviewed projects"
            )
            merged.extend(matches)

    for identity, projects in existing_by_identity.items():
        if identity not in discovered_identities:
            ambiguities.append(
                f"{reviewed.name}: reviewed {identity[0]} project at {identity[1]} "
                "was not rediscovered"
            )
            merged.extend(projects)

    return Repository(
        name=reviewed.name,
        default_branch=discovered.default_branch,
        projects=tuple(sorted(merged, key=lambda project: project.name)),
        deployment_workflows=discovered.deployment_workflows,
        auto_merge_enabled=reviewed.auto_merge_enabled and discovered.auto_merge_enabled,
    ), tuple(ambiguities)


def reconcile(
    inventory: Inventory,
    discovered: Sequence[DiscoveredRepository],
) -> AuditReport:
    discovered_by_name = {repository.name: repository for repository in discovered}
    if len(discovered_by_name) != len(discovered):
        raise PolicyError("discovery returned duplicate repository names")
    reviewed_by_name = {repository.name: repository for repository in inventory.repositories}

    unclassified = tuple(sorted(
        repository.name
        for repository in discovered
        if not repository.archived and repository.name not in reviewed_by_name
    ))
    archived = tuple(sorted(
        repository.name
        for repository in discovered
        if repository.archived and repository.name in reviewed_by_name
    ))
    ambiguities: list[str] = []
    reconciled: list[Repository] = []

    for repository in sorted(discovered, key=lambda item: item.name):
        if repository.archived:
            continue
        ambiguities.extend(f"{repository.name}: {message}" for message in repository.ambiguities)
        reviewed = reviewed_by_name.get(repository.name)
        if reviewed is None:
            reconciled.append(Repository(
                name=repository.name,
                default_branch=repository.default_branch,
                projects=repository.projects,
                deployment_workflows=repository.deployment_workflows,
                auto_merge_enabled=repository.auto_merge_enabled,
            ))
            continue
        merged, merge_ambiguities = _merge_repository(reviewed, repository)
        reconciled.append(merged)
        ambiguities.extend(merge_ambiguities)

    for repository in inventory.repositories:
        if repository.name not in discovered_by_name:
            ambiguities.append(
                f"{repository.name}: reviewed repository was not returned by GitHub discovery"
            )
            reconciled.append(repository)

    return AuditReport(
        inventory=Inventory(1, tuple(sorted(reconciled, key=lambda item: item.name))),
        unclassified=unclassified,
        archived=archived,
        ambiguities=tuple(sorted(set(ambiguities))),
    )


def _project_dict(project: Project) -> dict[str, Any]:
    return {
        PROJECT_KEYS[field.name]: value
        for field in fields(Project)
        if (value := getattr(project, field.name)) is not None
    }


def inventory_dict(inventory: Inventory) -> dict[str, Any]:
    return {
        "schema-version": inventory.schema_version,
        "repositories": [
            {
                "name": repository.name,
                "default-branch": repository.default_branch,
                "deployment-workflows": list(repository.deployment_workflows),
                "auto-merge-enabled": repository.auto_merge_enabled,
                "projects": [_project_dict(project) for project in repository.projects],
            }
            for repository in inventory.repositories
        ],
    }


def _report_dict(report: AuditReport) -> dict[str, Any]:
    return {
        "active-repositories": len(report.inventory.repositories),
        "unclassified": list(report.unclassified),
        "archived": list(report.archived),
        "ambiguities": list(report.ambiguities),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover GitHub repositories and reconcile dependency policy inventory"
    )
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail when inventory differs from discovery")
    mode.add_argument("--write", type=Path, help="write the reconciled inventory explicitly")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client: GitHubClient | None = None,
    inventory_path: Path = INVENTORY_PATH,
) -> int:
    args = _parser().parse_args(argv)
    inventory = load_inventory(inventory_path)
    report = reconcile(inventory, discover_repositories(client or GitHubClient(), args.owner))
    print(json.dumps(_report_dict(report), indent=2, sort_keys=True))

    if args.write is not None:
        if report.ambiguities:
            print("refusing to write ambiguous reconciliation")
            return 2
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(inventory_dict(report.inventory), indent=2) + "\n")
        load_inventory(args.write)
        return 0

    if args.check:
        current = inventory_dict(inventory)
        proposed = inventory_dict(report.inventory)
        if report.unclassified or report.archived or report.ambiguities or current != proposed:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
