from dataclasses import dataclass
import json
from pathlib import Path
import shlex
from typing import Any

from lib.models import PolicyError, Project


Command = tuple[str, ...] | str | None
FORBIDDEN_FRAGMENTS = (
    "--legacy-peer-deps",
    " --force",
    "|| true",
    "--exit-zero",
    "continue-on-error",
    "2>/dev/null",
)
VENV_DIRECTORY = ".dependency-gate-venv"
VENV_PYTHON = f"{VENV_DIRECTORY}/bin/python"


@dataclass(frozen=True)
class CommandPlan:
    install: Command
    test: Command
    build: Command
    skips: tuple[str, ...]


def reject_forbidden(command: str) -> None:
    normalized = " ".join(command.lower().split())
    searchable = f" {normalized}"
    for fragment in FORBIDDEN_FRAGMENTS:
        if fragment in searchable:
            raise PolicyError(f"command contains forbidden fragment: {fragment.strip()}")


def _configured_file(root: Path, value: str | None, label: str) -> Path:
    if value is None:
        raise PolicyError(f"{label} is not configured")
    root = root.resolve()
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PolicyError(f"{label} escapes project root: {value}") from error
    if not candidate.is_file():
        raise PolicyError(f"configured {label} not found: {value}")
    return candidate


def _npm_commands(project: Project, root: Path) -> tuple[Command, Command, Command]:
    manifest_path = _configured_file(root, project.manifest, "manifest")
    if project.lockfile is not None:
        _configured_file(root, project.lockfile, "lockfile")
        install: Command = ("npm", "ci")
    else:
        install = ("npm", "install")

    try:
        manifest: Any = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"invalid npm manifest: {project.manifest}") from error
    if not isinstance(manifest, dict):
        raise PolicyError(f"invalid npm manifest: {project.manifest}")
    scripts = manifest.get("scripts", {})
    if not isinstance(scripts, dict):
        raise PolicyError(f"invalid npm manifest scripts: {project.manifest}")
    test: Command = ("npm", "test", "--", "--watchAll=false") if "test" in scripts else None
    build: Command = ("npm", "run", "build") if "build" in scripts else None
    return install, test, build


def _has_python_tests(root: Path) -> bool:
    if any((root / name).is_file() for name in ("pytest.ini", "tox.ini")):
        return True
    if (root / "tests").is_dir():
        return True
    return any(root.glob("test*.py"))


def _python_commands(project: Project, root: Path) -> tuple[Command, Command, Command]:
    manifest_path = _configured_file(root, project.manifest, "manifest")
    quoted_manifest = shlex.quote(str(manifest_path.relative_to(root.resolve())))
    has_tests = _has_python_tests(root)
    create_venv = f"python3 -m venv --clear {VENV_DIRECTORY}"
    if project.ecosystem == "python-requirements":
        install_project = f"{VENV_PYTHON} -m pip install -r {quoted_manifest}"
    else:
        install_project = f"{VENV_PYTHON} -m pip install ."
    install_steps = [create_venv, install_project]
    if has_tests:
        install_steps.append(f"{VENV_PYTHON} -m pip install pytest")
    install: Command = " && ".join(install_steps)
    test: Command = (VENV_PYTHON, "-m", "pytest") if has_tests else None
    return install, test, None


def _gradle_commands(project: Project, root: Path) -> tuple[Command, Command, Command]:
    _configured_file(root, project.manifest, "manifest")
    _configured_file(root, project.gradle_wrapper, "gradle wrapper")
    wrapper = project.gradle_wrapper
    assert wrapper is not None
    executable = wrapper if wrapper.startswith("./") else f"./{wrapper}"
    return None, (executable, "--no-daemon", "check"), None


def _action_commands() -> tuple[Command, Command, Command]:
    return None, ("actionlint",), None


def plan_commands(project: Project, root: Path) -> CommandPlan:
    root = Path(root)
    if not root.is_dir():
        raise PolicyError(f"project root is not a directory: {root}")

    for command in (project.install_command, project.test_command, project.build_command):
        if command is not None:
            reject_forbidden(command)

    if project.ecosystem == "npm":
        install, test, build = _npm_commands(project, root)
    elif project.ecosystem in {"python-requirements", "python-pyproject"}:
        install, test, build = _python_commands(project, root)
    elif project.ecosystem == "gradle":
        install, test, build = _gradle_commands(project, root)
    elif project.ecosystem == "github-actions":
        install, test, build = _action_commands()
    else:
        raise PolicyError(f"unknown ecosystem: {project.ecosystem}")

    install = project.install_command if project.install_command is not None else install
    test = project.test_command if project.test_command is not None else test
    build = project.build_command if project.build_command is not None else build
    phases = (("install", install), ("test", test), ("build", build))
    skips = tuple(name for name, command in phases if command is None)
    return CommandPlan(install=install, test=test, build=build, skips=skips)
