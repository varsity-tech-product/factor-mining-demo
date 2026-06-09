#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

sync_one() {
  local target="$1"
  rm -rf "${target}/scripts"
  mkdir -p "${target}"
  cp -R "${ROOT}/scripts" "${target}/scripts"
  find "${target}/scripts" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "${target}/scripts" -type f -name '*.pyc' -delete
}

sync_one "${ROOT}/adapters/claude-code/factor-mining-demo"
