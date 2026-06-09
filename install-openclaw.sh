#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="factor-mining-demo"
AGENT_ID="factormining"
AGENT_NAME="factormining"
WORKSPACE_DIR="${FACTOR_MINING_DEMO_WORKSPACE:-${HOME}/.openclaw/workspaces/factor-mining-agent}"
AGENT_DIR="${FACTOR_MINING_DEMO_AGENT_DIR:-${HOME}/.openclaw/agents/factor-mining}"
SET_DEFAULT="${FACTOR_MINING_DEMO_SET_DEFAULT:-1}"
STATUS_HELPER="${HOME}/.openclaw/extensions/${PLUGIN_ID}/bin/factor-mining-demo-status"

log() {
  printf '==> %s\n' "$*"
}

warn() {
  printf 'WARNING: %s\n' "$*" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local name="$1"
  local instruction="$2"
  if ! command -v "${name}" >/dev/null 2>&1; then
    printf 'ERROR: %s is required but was not found.\n\n' "${name}" >&2
    printf '%s\n' "${instruction}" >&2
    exit 1
  fi
}

normalize_path() {
  local path="$1"
  python3 - "${path}" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1].strip()).expanduser())
PY
}

json_service_loaded() {
  python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    loaded = data.get("service", {}).get("loaded") is True
except Exception:
    loaded = False
print("yes" if loaded else "no")
' <<<"${1:-}"
}

json_service_running() {
  python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    runtime = data.get("service", {}).get("runtime", {})
    status = str(runtime.get("status") or runtime.get("state") or "").lower()
    running = status == "running" or data.get("rpc", {}).get("ok") is True
except Exception:
    running = False
print("yes" if running else "no")
' <<<"${1:-}"
}

json_connected_node_count() {
  python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    nodes = data.get("nodes") if isinstance(data, dict) else []
    count = sum(1 for node in nodes if isinstance(node, dict) and node.get("connected") is True)
except Exception:
    count = 0
print(count)
' <<<"${1:-}"
}

config_hash() {
  local path="$1"
  python3 - "${path}" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
if not path.exists():
    print("missing")
else:
    print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

read_status_json() {
  local service="$1"
  "${OPENCLAW_BIN}" "${service}" status --json 2>/dev/null || true
}

agent_exists() {
  local agents_json
  agents_json="$("${OPENCLAW_BIN}" agents list --json 2>/dev/null || true)"
  AGENTS_JSON="${agents_json}" python3 - "${AGENT_ID}" <<'PY'
import json
import os
import sys

agent_id = sys.argv[1]
try:
    agents = json.loads(os.environ.get("AGENTS_JSON") or "[]")
except Exception:
    agents = []
found = any(isinstance(agent, dict) and agent.get("id") == agent_id for agent in agents)
raise SystemExit(0 if found else 1)
PY
}

ensure_service_running() {
  local service="$1"
  local label="$2"
  local status_json loaded running

  status_json="$(read_status_json "${service}")"
  loaded="$(json_service_loaded "${status_json}")"
  if [[ "${loaded}" != "yes" ]]; then
    log "Installing OpenClaw ${label} service"
    if ! "${OPENCLAW_BIN}" "${service}" install; then
      status_json="$(read_status_json "${service}")"
      loaded="$(json_service_loaded "${status_json}")"
      [[ "${loaded}" == "yes" ]] || fail "Unable to install the OpenClaw ${label} service."
    fi
  else
    log "OpenClaw ${label} service is installed"
  fi

  status_json="$(read_status_json "${service}")"
  running="$(json_service_running "${status_json}")"
  if [[ "${running}" != "yes" ]]; then
    log "Starting OpenClaw ${label} service"
    if ! "${OPENCLAW_BIN}" "${service}" start; then
      status_json="$(read_status_json "${service}")"
      running="$(json_service_running "${status_json}")"
      [[ "${running}" == "yes" ]] || fail "Unable to start the OpenClaw ${label} service."
    fi
  else
    log "OpenClaw ${label} service is running"
  fi
}

patch_agent_config() {
  CONFIG_PATH="${CONFIG_PATH}" \
  AGENT_ID="${AGENT_ID}" \
  AGENT_NAME="${AGENT_NAME}" \
  WORKSPACE_DIR="${WORKSPACE_DIR}" \
  AGENT_DIR="${AGENT_DIR}" \
  PLUGIN_ID="${PLUGIN_ID}" \
  SET_DEFAULT="${SET_DEFAULT}" \
  python3 <<'PY'
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"]).expanduser()
agent_id = os.environ["AGENT_ID"]
agent_name = os.environ["AGENT_NAME"]
workspace_dir = os.environ["WORKSPACE_DIR"]
agent_dir = os.environ["AGENT_DIR"]
plugin_id = os.environ["PLUGIN_ID"]
set_default = os.environ["SET_DEFAULT"] != "0"

required_local_capabilities = {
    "read",
    "write",
    "edit",
    "apply_patch",
    "exec",
    "process",
    "web_fetch",
}
required_blockers = required_local_capabilities | {"group:fs", "group:runtime", "group:web"}

if config_path.exists():
    original_text = config_path.read_text(encoding="utf-8")
    config = json.loads(original_text)
else:
    original_text = "{}\n"
    config = {}

if not isinstance(config, dict):
    raise SystemExit(f"OpenClaw config must be a JSON object: {config_path}")

changed = False

def assign(target, key, value):
    global changed
    if target.get(key) != value:
        target[key] = value
        changed = True

agents_config = config.setdefault("agents", {})
if not isinstance(agents_config, dict):
    raise SystemExit("OpenClaw config field agents must be an object.")

agent_list = agents_config.setdefault("list", [])
if not isinstance(agent_list, list):
    raise SystemExit("OpenClaw config field agents.list must be an array.")

agent = None
for candidate in agent_list:
    if isinstance(candidate, dict) and candidate.get("id") == agent_id:
        agent = candidate
        break

if agent is None:
    agent = {"id": agent_id}
    agent_list.append(agent)
    changed = True

assign(agent, "id", agent_id)
assign(agent, "name", agent_name)
assign(agent, "workspace", workspace_dir)
assign(agent, "agentDir", agent_dir)
assign(agent, "skills", [plugin_id])

tools = agent.get("tools")
if not isinstance(tools, dict):
    tools = {}
    agent["tools"] = tools
    changed = True
assign(tools, "profile", "full")

deny = tools.get("deny")
if deny is None:
    deny = []
elif not isinstance(deny, list):
    deny = []
else:
    deny = [entry for entry in deny if isinstance(entry, str)]

new_deny = [entry for entry in deny if entry not in required_blockers]
if new_deny != deny:
    tools["deny"] = new_deny
    changed = True

if set_default:
    for candidate in agent_list:
        if not isinstance(candidate, dict):
            continue
        if candidate is agent:
            assign(candidate, "default", True)
        elif candidate.get("default") is True:
            candidate["default"] = False
            changed = True

global_deny = config.get("tools", {}).get("deny", [])
if isinstance(global_deny, list):
    global_blockers = sorted(required_blockers.intersection(entry for entry in global_deny if isinstance(entry, str)))
else:
    global_blockers = []

if changed:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = config_path.with_name(f"{config_path.name}.bak.{timestamp}")
        shutil.copy2(config_path, backup_path)
        print(f"config_backup={backup_path}")
    tmp_path = config_path.with_name(f"{config_path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(config_path)
    print("agent_config_changed=true")
else:
    print("agent_config_changed=false")

if global_blockers:
    print("global_deny_blockers=" + ",".join(global_blockers))
else:
    print("global_deny_blockers=")
PY
}

verify_skills() {
  local skills_text skills_json
  log "Verifying Factor Mining skill visibility"
  skills_text="$("${OPENCLAW_BIN}" skills check --agent "${AGENT_ID}" 2>&1)" || {
    printf '%s\n' "${skills_text}" >&2
    fail "OpenClaw skills check failed for agent ${AGENT_ID}."
  }
  printf '%s\n' "${skills_text}"

  skills_json="$("${OPENCLAW_BIN}" skills check --agent "${AGENT_ID}" --json 2>/dev/null)" || {
    fail "OpenClaw skills check JSON output failed for agent ${AGENT_ID}."
  }
  SKILLS_JSON="${skills_json}" python3 - "${PLUGIN_ID}" <<'PY'
import json
import os
import sys

plugin_id = sys.argv[1]
payload = json.loads(os.environ.get("SKILLS_JSON") or "{}")
model_visible = set(payload.get("modelVisible") or [])
agent_filtered = set(payload.get("agentFiltered") or [])
if plugin_id not in model_visible:
    raise SystemExit(f"{plugin_id} is not modelVisible for the factormining agent.")
if plugin_id in agent_filtered:
    raise SystemExit(f"{plugin_id} is agent-filtered for the factormining agent.")
PY
}

verify_nodes() {
  local nodes_text nodes_json connected_count
  log "Verifying connected OpenClaw node"
  nodes_text="$("${OPENCLAW_BIN}" nodes status 2>&1)" || true
  printf '%s\n' "${nodes_text}"
  nodes_json="$("${OPENCLAW_BIN}" nodes status --json 2>/dev/null || true)"
  connected_count="$(json_connected_node_count "${nodes_json}")"
  if [[ "${connected_count}" -lt 1 ]]; then
    warn "No connected OpenClaw node is currently approved."
    printf '%s\n' "Next action:"
    printf '%s\n' "  1. Run: openclaw nodes pending"
    printf '%s\n' "  2. Approve the pending local node: openclaw nodes approve <node-id>"
    printf '%s\n' "  3. Restart the node host if needed: openclaw node restart"
    printf '%s\n' "  4. Re-run: openclaw nodes status"
  fi
}

verify_status_helper() {
  local output exit_code
  log "Verifying Factor Mining status helper"
  if [[ ! -x "${STATUS_HELPER}" ]]; then
    fail "Missing installed status helper: ${STATUS_HELPER}"
  fi

  set +e
  output="$("${STATUS_HELPER}" 2>&1)"
  exit_code=$?
  set -e
  printf '%s\n' "${output}"

  if [[ "${exit_code}" -eq 0 ]]; then
    return
  fi
  if [[ "${output}" == *"Missing Factor Mining config"* && "${output}" == *"Run setup first."* ]]; then
    log "Status helper is installed; Factor Mining key setup is still required"
    return
  fi
  fail "Factor Mining status helper failed unexpectedly."
}

require_command "openclaw" "Install the OpenClaw CLI first, then rerun this installer. For npm-based installs, run: npm install -g openclaw"
require_command "python3" "Install Python 3, then rerun this installer."

OPENCLAW_BIN="$(command -v openclaw)"
CONFIG_PATH="$(normalize_path "$("${OPENCLAW_BIN}" config file)")"
WORKSPACE_DIR="$(normalize_path "${WORKSPACE_DIR}")"
AGENT_DIR="$(normalize_path "${AGENT_DIR}")"

case "${CONFIG_PATH}" in
  "${HOME}/~/"*)
    fail "OpenClaw config path was not normalized correctly: ${CONFIG_PATH}"
    ;;
esac

mkdir -p "${WORKSPACE_DIR}" "${AGENT_DIR}"

initial_gateway_status="$(read_status_json "gateway")"
gateway_was_running="$(json_service_running "${initial_gateway_status}")"
config_hash_before="$(config_hash "${CONFIG_PATH}")"
gateway_reload_needed="0"

log "Installing or updating OpenClaw plugin ${PLUGIN_ID}"
plugin_install_output="$("${OPENCLAW_BIN}" plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo --force 2>&1)" || {
  printf '%s\n' "${plugin_install_output}" >&2
  fail "OpenClaw plugin install failed."
}
printf '%s\n' "${plugin_install_output}"
if [[ "${plugin_install_output}" == *"Restart the gateway"* ]]; then
  gateway_reload_needed="1"
fi

if agent_exists; then
  log "OpenClaw agent ${AGENT_ID} already exists"
else
  log "Creating OpenClaw agent ${AGENT_ID}"
  if ! "${OPENCLAW_BIN}" agents add "${AGENT_ID}" --workspace "${WORKSPACE_DIR}" --agent-dir "${AGENT_DIR}" --non-interactive --json >/dev/null; then
    warn "OpenClaw agents add did not complete; applying the config patch path."
  fi
fi

patch_output="$(patch_agent_config)"
printf '%s\n' "${patch_output}"

config_changed="0"
config_hash_after="$(config_hash "${CONFIG_PATH}")"
if [[ "${config_hash_before}" != "${config_hash_after}" || "${patch_output}" == *"agent_config_changed=true"* ]]; then
  config_changed="1"
  gateway_reload_needed="1"
fi

if [[ "${patch_output}" == *"global_deny_blockers="* ]]; then
  blockers="$(printf '%s\n' "${patch_output}" | awk -F= '/^global_deny_blockers=/{print $2}')"
  if [[ -n "${blockers}" ]]; then
    warn "OpenClaw global tools.deny blocks required local-agent capabilities: ${blockers}"
    warn "Factor Mining local-agent work needs local read/write/edit/apply_patch/exec/process/web_fetch capability. This installer does not change global deny policy."
  fi
fi

if [[ "${patch_output}" == *"agent_config_changed=true"* ]]; then
  log "Validating OpenClaw config"
  "${OPENCLAW_BIN}" config validate
fi

ensure_service_running "gateway" "gateway"
if [[ "${gateway_reload_needed}" == "1" && "${gateway_was_running}" == "yes" ]]; then
  log "Restarting OpenClaw gateway to load updated plugin/configuration"
  "${OPENCLAW_BIN}" gateway restart
  ensure_service_running "gateway" "gateway"
fi
ensure_service_running "node" "node host"

log "Verifying installed OpenClaw plugin"
"${OPENCLAW_BIN}" plugins inspect "${PLUGIN_ID}"
verify_skills
verify_nodes
verify_status_helper

printf '\n%s\n' "OpenClaw Factor Mining Demo is installed."
printf '\n%s\n' "Next commands:"
printf '%s\n' 'openclaw agent --agent factormining --message "Use Factor Mining Demo. Open the local browser setup page for my Factor Mining Agent API Key, then verify status. Do not ask me to paste the key into chat."'
printf '%s\n' 'openclaw agent --agent factormining --message "Use Factor Mining Demo. Verify status, then show me the Factor Mining public task list. Do not create a session until I choose a public task or provide a custom idea."'
