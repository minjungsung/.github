import base64
import binascii
import json
import subprocess
from typing import Any, Callable, Sequence
from urllib.parse import quote

from lib.models import PolicyError


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise PolicyError("unable to execute GitHub CLI") from error


class GitHubClient:
    """Small JSON-only boundary around authenticated ``gh`` commands."""

    def __init__(self, runner: CommandRunner = _default_runner):
        self._runner = runner

    def _json(self, command: Sequence[str]) -> Any:
        result = self._runner(list(command))
        if result.returncode != 0:
            raise PolicyError(
                f"GitHub CLI command failed with exit code {result.returncode}"
            )
        try:
            return json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as error:
            raise PolicyError("GitHub CLI returned invalid JSON") from error

    def list_repositories(self, owner: str) -> list[dict[str, Any]]:
        value = self._json([
            "gh",
            "repo",
            "list",
            owner,
            "--limit",
            "1000",
            "--source",
            "--json",
            "name,nameWithOwner,isArchived,defaultBranchRef",
        ])
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise PolicyError("GitHub repository response must be a JSON array of objects")
        return value

    def repository_tree(self, repository: str, default_branch: str) -> list[dict[str, Any]]:
        encoded_branch = quote(default_branch, safe="")
        value = self._json([
            "gh",
            "api",
            f"repos/{repository}/git/trees/{encoded_branch}?recursive=1",
        ])
        if not isinstance(value, dict):
            raise PolicyError("GitHub tree response must be a JSON object")
        if value.get("truncated") is not False:
            raise PolicyError(f"GitHub tree response is truncated for {repository}")
        tree = value.get("tree")
        if not isinstance(tree, list) or not all(isinstance(item, dict) for item in tree):
            raise PolicyError("GitHub tree response must contain an array of objects")
        return tree

    def blob_text(self, repository: str, sha: str) -> str:
        value = self._json(["gh", "api", f"repos/{repository}/git/blobs/{sha}"])
        if not isinstance(value, dict) or value.get("encoding") != "base64":
            raise PolicyError("GitHub blob response must use base64 encoding")
        content = value.get("content")
        if not isinstance(content, str):
            raise PolicyError("GitHub blob response must contain text content")
        try:
            decoded = base64.b64decode("".join(content.split()), validate=True)
            return decoded.decode()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise PolicyError("GitHub blob response contains invalid text") from error
