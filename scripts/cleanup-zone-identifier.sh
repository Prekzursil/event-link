#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
find "$repo_root" -name '*:Zone.Identifier' -type f -delete

echo "Removed Zone.Identifier artifacts under: $repo_root"

