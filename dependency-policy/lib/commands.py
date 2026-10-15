from dataclasses import dataclass
import json
import configparser
import tomllib
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


def reject_forbidden(command: str, *, shell_syntax: bool = False) -> None:
    if shell_syntax:
        quote = None
        escaped = False
        for character in command:
            if escaped:
                escaped = False
                continue
            if character == '\\' and quote != "'":
                escaped = True
                continue
            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
            elif character in {'\n', '\r'} and quote is None:
                raise PolicyError('command contains forbidden shell newline separator')
        lexer = shlex.shlex(command, posix=False, punctuation_chars=';&|')
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError as error:
            raise PolicyError('invalid shell command quoting') from error
        if any(token in {'||', ';', '|', '&', ';;'} for token in tokens):
            raise PolicyError('command contains forbidden failure-swallowing shell syntax')
    searchable = ' ' + ' '.join(command.lower().split())
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
    npmrc = root / '.npmrc'
    if npmrc.is_file():
        for line in npmrc.read_text().splitlines():
            key, separator, value = line.partition('=')
            key = key.strip().lower().replace('_', '-')
            if separator and ((key in {'legacy-peer-deps', 'force'} and value.strip().lower() not in {'false', '0'}) or
                              (key == 'strict-peer-deps' and value.strip().lower() in {'false', '0'})):
                raise PolicyError('npmrc contains a dependency-resolution bypass')
    for script in scripts.values():
        if not isinstance(script, str):
            raise PolicyError('npm manifest script must be a string')
        reject_forbidden(script, shell_syntax=True)
    test: Command = ("npm", "test", "--", "--watchAll=false") if "test" in scripts else None
    build: Command = ("npm", "run", "build") if "build" in scripts else None
    return install, test, build


def _has_python_tests(root: Path) -> bool:
    pyproject = root / 'pyproject.toml'
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text())
            tool = data.get('tool', {})
            if not isinstance(tool, dict) or not isinstance(tool.get('pytest', {}), dict):
                raise PolicyError('invalid pytest configuration')
            if 'ini_options' in tool.get('pytest', {}):
                return True
        except tomllib.TOMLDecodeError as error:
            raise PolicyError('invalid pyproject configuration') from error
    setup = root / 'setup.cfg'
    if setup.is_file():
        parser = configparser.ConfigParser()
        try:
            parser.read(setup)
        except configparser.Error as error:
            raise PolicyError('invalid pytest configuration') from error
        if parser.has_section('tool:pytest'):
            return True
    if any((root / name).is_file() for name in ("pytest.ini", "tox.ini")):
        return True
    if (root / "tests").is_dir():
        return True
    return any(root.glob("test*.py"))


def _python_commands(project: Project, root: Path) -> tuple[Command, Command, Command]:
    manifest_path = _configured_file(root, project.manifest, "manifest")
    quoted_manifest = shlex.quote(str(manifest_path.relative_to(root.resolve())))
    has_tests = _has_python_tests(root)
    if (root / VENV_DIRECTORY).is_symlink():
        raise PolicyError('virtual environment directory must not be a symlink')
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
            reject_forbidden(command, shell_syntax=True)

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
