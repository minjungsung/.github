#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Callable, Mapping, Sequence

from lib.commands import Command, plan_commands
from lib.models import PolicyError, parse_project


Runner = Callable[..., subprocess.CompletedProcess]


def _append_summary(environ: Mapping[str, str], line: str) -> None:
    summary_path = environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a") as summary:
            summary.write(f"{line}\n")


def _display(command: tuple[str, ...] | str) -> str:
    return command if isinstance(command, str) else shlex.join(command)


def _project_root(repository_root: Path, project_path: str) -> Path:
    repository_root = repository_root.resolve()
    if not repository_root.is_dir():
        raise PolicyError(f"repository root is not a directory: {repository_root}")
    candidate = (repository_root / project_path).resolve()
    try:
        candidate.relative_to(repository_root)
    except ValueError as error:
        raise PolicyError(f"project path escapes repository root: {project_path}") from error
    if not candidate.is_dir():
        raise PolicyError(f"project path is not a directory: {project_path}")
    return candidate


def run_project(
    project_json: str,
    repository_root: Path | str,
    *,
    runner: Runner = subprocess.run,
    environ: Mapping[str, str] | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    try:
        raw_project = json.loads(project_json)
        project = parse_project(raw_project)
        root = _project_root(Path(repository_root), project.path)
        plan = plan_commands(project, root)
    except (json.JSONDecodeError, OSError, PolicyError, TypeError) as error:
        _append_summary(environment, f"- configuration: FAIL — {error}")
        _append_summary(environment, "- result: FAIL")
        return 1

    _append_summary(environment, f"### Dependency gate: {project.name}")
    _append_summary(environment, f"- ecosystem: {project.ecosystem}")
    _append_summary(environment, f"- working-directory: {project.path}")

    phases = (("install", plan.install), ("test", plan.test), ("build", plan.build))
    for phase, command in phases:
        if command is None:
            _append_summary(environment, f"- {phase}: SKIP — not configured")
            continue
        display = _display(command)
        child_environment = dict(os.environ)
        child_environment.update(environment)
        if project.ecosystem == 'npm':
            for key in list(child_environment):
                if key.lower() in {'npm_config_legacy_peer_deps', 'npm_config_force', 'npm_config_strict_peer_deps'}:
                    del child_environment[key]
            child_environment.update(npm_config_legacy_peer_deps='false', npm_config_force='false',
                                     npm_config_strict_peer_deps='true')
        kwargs = {"cwd": root, "check": True, "env": child_environment}
        if isinstance(command, str):
            command = ("bash", "-e", "-o", "pipefail", "-c", command)
        try:
            runner(command, **kwargs)
        except subprocess.CalledProcessError as error:
            _append_summary(environment, f"- {phase}: `{display}` — FAIL")
            _append_summary(environment, "- result: FAIL")
            return error.returncode if error.returncode != 0 else 1
        except OSError as error:
            _append_summary(environment, f"- {phase}: `{display}` — FAIL — {error}")
            _append_summary(environment, "- result: FAIL")
            return 1
        _append_summary(environment, f"- {phase}: `{display}` — PASS")

    _append_summary(environment, "- result: PASS")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run strict validation for one audited project")
    parser.add_argument("--project-json", required=True, help="one project descriptor JSON object")
    parser.add_argument("--repository-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    return run_project(arguments.project_json, arguments.repository_root)


if __name__ == "__main__":
    raise SystemExit(main())
