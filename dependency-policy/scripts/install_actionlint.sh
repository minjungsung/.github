#!/usr/bin/env bash
set -euo pipefail
version=1.7.12
archive="actionlint_${version}_linux_amd64.tar.gz"
url="https://github.com/rhysd/actionlint/releases/download/v${version}/${archive}"
expected="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
curl --fail --location --silent --show-error "$url" --output "$RUNNER_TEMP/$archive"
printf '%s  %s\n' "$expected" "$RUNNER_TEMP/$archive" | sha256sum --check -
tar -xzf "$RUNNER_TEMP/$archive" -C "$RUNNER_TEMP" actionlint
printf '%s\n' "$RUNNER_TEMP" >> "$GITHUB_PATH"
