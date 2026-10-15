from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any


ECOSYSTEMS = {"npm", "python-requirements", "python-pyproject", "gradle", "github-actions"}
DEFAULT_TIMEOUTS = {
    "npm": 15,
    "python-requirements": 15,
    "python-pyproject": 15,
    "gradle": 30,
    "github-actions": 5,
}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Project:
    name: str
    ecosystem: str
    path: str
    runtime_version: str | None = None
    manifest: str | None = None
    lockfile: str | None = None
    install_command: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    gradle_wrapper: str | None = None
    timeout_minutes: int = 0


@dataclass(frozen=True)
class Repository:
    name: str
    default_branch: str
    projects: tuple[Project, ...]
    deployment_workflows: tuple[str, ...] = ()
    auto_merge_enabled: bool = True


@dataclass(frozen=True)
class Inventory:
    schema_version: int
    repositories: tuple[Repository, ...]

    def repository(self, name: str) -> Repository:
        matches = [repository for repository in self.repositories if repository.name == name]
        if not matches:
            raise PolicyError(f"repository not found: {name}")
        return matches[0]


def _reject_unknown(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PolicyError(f"{context}: unknown field(s): {', '.join(unknown)}")


def _safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


PROJECT_FIELDS = {
    "name", "ecosystem", "path", "runtime-version", "manifest", "lockfile",
    "install-command", "test-command", "build-command", "gradle-wrapper",
    "timeout-minutes",
}
REPOSITORY_FIELDS = {
    "name", "default-branch", "projects", "deployment-workflows",
    "auto-merge-enabled",
}
REQUIRED_BY_ECOSYSTEM = {
    "npm": {"runtime-version", "manifest"},
    "python-requirements": {"runtime-version", "manifest"},
    "python-pyproject": {"runtime-version", "manifest"},
    "gradle": {"runtime-version", "manifest", "gradle-wrapper"},
    "github-actions": set(),
}


def _required_string(value: dict[str, Any], key: str, context: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise PolicyError(f"{context}: {key} must be a non-empty string")
    return result


def parse_project(value: dict[str, Any], context: str = "project") -> Project:
    if not isinstance(value, dict):
        raise PolicyError(f"{context}: must be an object")
    _reject_unknown(value, PROJECT_FIELDS, context)
    name = _required_string(value, "name", context)
    ecosystem = _required_string(value, "ecosystem", context)
    project_path = _required_string(value, "path", context)
    if ecosystem not in ECOSYSTEMS:
        raise PolicyError(f"{context}: unknown ecosystem: {ecosystem}")
    if not _safe_path(project_path):
        raise PolicyError(f"{context}: unsafe path: {project_path}")
    for key in REQUIRED_BY_ECOSYSTEM[ecosystem]:
        _required_string(value, key, context)
    optional_strings = (
        "runtime-version", "manifest", "lockfile", "install-command",
        "test-command", "build-command", "gradle-wrapper",
    )
    for key in optional_strings:
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise PolicyError(f"{context}: {key} must be a non-empty string")
    timeout = value.get("timeout-minutes", DEFAULT_TIMEOUTS[ecosystem])
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 45:
        raise PolicyError(f"{context}: timeout-minutes must be an integer from 1 to 45")
    return Project(
        name=name,
        ecosystem=ecosystem,
        path=project_path,
        runtime_version=value.get("runtime-version"),
        manifest=value.get("manifest"),
        lockfile=value.get("lockfile"),
        install_command=value.get("install-command"),
        test_command=value.get("test-command"),
        build_command=value.get("build-command"),
        gradle_wrapper=value.get("gradle-wrapper"),
        timeout_minutes=timeout,
    )


def _parse_repository(value: dict[str, Any], index: int) -> Repository:
    context = f"repositories[{index}]"
    if not isinstance(value, dict):
        raise PolicyError(f"{context}: must be an object")
    _reject_unknown(value, REPOSITORY_FIELDS, context)
    name = _required_string(value, "name", context)
    default_branch = _required_string(value, "default-branch", context)
    raw_projects = value.get("projects")
    if not isinstance(raw_projects, list) or not raw_projects:
        raise PolicyError(f"{context}: projects must be a non-empty array")
    projects = tuple(
        parse_project(project, f"{context}.projects[{project_index}]")
        for project_index, project in enumerate(raw_projects)
    )
    project_names = [project.name for project in projects]
    if len(project_names) != len(set(project_names)):
        raise PolicyError(f"{context}: duplicate project name")
    deployments = value.get("deployment-workflows", [])
    if not isinstance(deployments, list) or not all(isinstance(item, str) for item in deployments):
        raise PolicyError(f"{context}: deployment-workflows must be an array of strings")
    auto_merge = value.get("auto-merge-enabled", True)
    if not isinstance(auto_merge, bool):
        raise PolicyError(f"{context}: auto-merge-enabled must be boolean")
    return Repository(
        name=name,
        default_branch=default_branch,
        projects=projects,
        deployment_workflows=tuple(deployments),
        auto_merge_enabled=auto_merge,
    )


def load_inventory(path: Path) -> Inventory:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise PolicyError("inventory must be an object")
    _reject_unknown(value, {"schema-version", "repositories"}, "inventory")
    schema_version = value.get("schema-version")
    if type(schema_version) is not int or schema_version != 1:
        raise PolicyError("inventory: schema-version must equal 1")
    raw_repositories = value.get("repositories")
    if not isinstance(raw_repositories, list):
        raise PolicyError("inventory: repositories must be an array")
    repositories = tuple(
        _parse_repository(repository, index)
        for index, repository in enumerate(raw_repositories)
    )
    names = [repository.name for repository in repositories]
    if len(names) != len(set(names)):
        raise PolicyError("inventory: duplicate repository name")
    return Inventory(schema_version=1, repositories=repositories)
