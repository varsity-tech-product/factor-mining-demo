#!/usr/bin/env bash
set -euo pipefail

MARKETPLACE_SOURCE="${FACTOR_MINING_DEMO_SOURCE:-varsity-tech-product/factor-mining-demo}"
MARKETPLACE_REF="${FACTOR_MINING_DEMO_REF:-main}"
MARKETPLACE_NAME="${FACTOR_MINING_DEMO_MARKETPLACE:-factor-mining-demo-marketplace}"
PLUGIN_NAME="${FACTOR_MINING_DEMO_PLUGIN:-factor-mining-demo}"
START_MODE="${FACTOR_MINING_DEMO_START_MODE:-cli}"
WORKSPACE_PATH="${FACTOR_MINING_DEMO_WORKSPACE:-.}"
CODEX_PROMPT="${FACTOR_MINING_DEMO_PROMPT:-Use Factor Mining Demo. Start with factor_mining_demo_status. If setup is required, use factor_mining_demo_setup_browser and tell me to enter the key in the local browser page. Then show me the public task list and wait for me to choose a task or provide a custom idea.}"

if [[ "${FACTOR_MINING_DEMO_START_CODEX:-1}" == "0" ]]; then
  START_MODE="none"
fi

usage() {
  cat <<'USAGE'
Usage: install-codex.sh [options]

Options:
  --desktop       Install, then open Codex Desktop for this workspace.
  --no-start      Install without starting Codex.
  --install-only  Install without starting Codex.
  -h, --help      Show this help.

Key setup is handled by the Factor Mining Demo MCP tools after install.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop)
      START_MODE="desktop"
      ;;
    --no-start|--install-only)
      START_MODE="none"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI is required. Install or update Codex, then run this installer again." >&2
  exit 1
fi

marketplace_configured() {
  codex plugin marketplace list 2>/dev/null | awk 'NR > 1 { print $1 }' | grep -Fxq "${MARKETPLACE_NAME}"
}

plugin_installed() {
  codex plugin list --marketplace "${MARKETPLACE_NAME}" 2>/dev/null \
    | grep -E "^${PLUGIN_NAME}@${MARKETPLACE_NAME}[[:space:]]+installed, enabled" >/dev/null
}

plugin_root() {
  local listed_path
  listed_path="$(codex plugin list --marketplace "${MARKETPLACE_NAME}" 2>/dev/null \
    | awk -v plugin="${PLUGIN_NAME}@${MARKETPLACE_NAME}" '$1 == plugin { print $NF; exit }'
  )"
  if [[ -n "${listed_path}" && -d "${listed_path}" ]]; then
    printf '%s\n' "${listed_path}"
    return
  fi

  local cache_root="${CODEX_HOME:-${HOME}/.codex}/plugins/cache/${MARKETPLACE_NAME}/${PLUGIN_NAME}"
  if [[ -d "${cache_root}" ]]; then
    find "${cache_root}" -mindepth 1 -maxdepth 1 -type d -print | sort | tail -n 1
  fi
}

echo "Configuring Codex marketplace: ${MARKETPLACE_NAME}"
if marketplace_configured; then
  echo "Marketplace already configured; refreshing if it is Git-backed."
  codex plugin marketplace upgrade "${MARKETPLACE_NAME}" >/dev/null 2>&1 || true
else
  if [[ -d "${MARKETPLACE_SOURCE}" ]]; then
    codex plugin marketplace add "${MARKETPLACE_SOURCE}"
  else
    codex plugin marketplace add "${MARKETPLACE_SOURCE}" --ref "${MARKETPLACE_REF}"
  fi
fi

echo "Installing Factor Mining Demo package: ${PLUGIN_NAME}@${MARKETPLACE_NAME}"
if plugin_installed; then
  echo "Plugin already installed."
else
  codex plugin add "${PLUGIN_NAME}@${MARKETPLACE_NAME}"
fi

PLUGIN_ROOT="$(plugin_root)"
if [[ -z "${PLUGIN_ROOT}" || ! -d "${PLUGIN_ROOT}" ]]; then
  echo "Could not locate installed plugin root for ${PLUGIN_NAME}@${MARKETPLACE_NAME}." >&2
  exit 1
fi

if [[ ! -f "${PLUGIN_ROOT}/.mcp.json" ]]; then
  echo "Installed plugin is missing .mcp.json." >&2
  exit 1
fi

if [[ "${START_MODE}" == "none" ]]; then
  echo "Factor Mining Demo is installed. Start it with:"
  printf 'codex %q\n' "${CODEX_PROMPT}"
  echo "For Codex Desktop, run:"
  printf 'codex app %q\n' "${WORKSPACE_PATH}"
  exit 0
fi

if [[ "${START_MODE}" == "desktop" ]]; then
  echo "Opening Codex Desktop."
  echo "Start a new chat with this prompt:"
  printf '%s\n' "${CODEX_PROMPT}"
  exec codex app "${WORKSPACE_PATH}"
fi

echo "Starting Codex CLI."
exec codex "${CODEX_PROMPT}"
