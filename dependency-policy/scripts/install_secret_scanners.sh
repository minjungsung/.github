#!/usr/bin/env bash
set -euo pipefail
scanner_directory="${RUNNER_TEMP:?}/secret-scanners"
mkdir -p "$scanner_directory"
curl --fail --location --silent --show-error \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
  --output "$scanner_directory/gitleaks.tar.gz"
curl --fail --location --silent --show-error \
  https://github.com/trufflesecurity/trufflehog/releases/download/v3.99.3/trufflehog_3.99.3_linux_amd64.tar.gz \
  --output "$scanner_directory/trufflehog.tar.gz"
printf '%s  %s\n' \
  551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb "$scanner_directory/gitleaks.tar.gz" \
  029b182e0ed35fd5b02cd1eadc2a94bd457ab14ad22a9380b6e5d9652261d28d "$scanner_directory/trufflehog.tar.gz" \
  | sha256sum --check -
tar -xzf "$scanner_directory/gitleaks.tar.gz" -C "$scanner_directory" gitleaks
tar -xzf "$scanner_directory/trufflehog.tar.gz" -C "$scanner_directory" trufflehog
printf '%s\n' "$scanner_directory" >> "${GITHUB_PATH:?}"
