#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="factor-mining-batch-test"
BATCH_SKILL_ID="factor-mining-batch-test-batch"
MCP_SERVER_ID="fmbt"
AGENT_ID="factormining"
AGENT_NAME="factormining"
WORKSPACE_DIR="${FACTOR_MINING_BATCH_TEST_WORKSPACE:-${HOME}/.openclaw/workspaces/factor-mining-agent}"
AGENT_DIR="${FACTOR_MINING_BATCH_TEST_AGENT_DIR:-${HOME}/.openclaw/agents/factor-mining}"
SET_DEFAULT="${FACTOR_MINING_BATCH_TEST_SET_DEFAULT:-1}"
MARKETPLACE_SOURCE="${FACTOR_MINING_BATCH_TEST_MARKETPLACE:-https://github.com/varsity-tech-product/factor-mining-agent-plugins.git#feat/batch-test-local-mcp}"
REQUIRED_MCP_TOOLS=(
  factor_mining_batch_test_status
  factor_mining_batch_test_setup_browser
  factor_mining_batch_test_list_public_tasks
  factor_mining_batch_test_create_task_session
  factor_mining_batch_test_create_custom_session
  factor_mining_batch_test_parse_plugin_metadata
  factor_mining_batch_test_request_dedup_context
  factor_mining_batch_test_upload_backtest_wait
  factor_mining_batch_test_resume_run
  factor_mining_batch_test_get_workflow
  factor_mining_batch_test_get_job
  factor_mining_batch_test_get_artifact
  factor_mining_batch_test_batch_start
  factor_mining_batch_test_batch_next
  factor_mining_batch_test_batch_upload_backtest_wait
  factor_mining_batch_test_batch_status
  factor_mining_batch_test_batch_results
  factor_mining_batch_test_batch_cancel
  factor_mining_batch_test_clear_config
)

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
  BATCH_SKILL_ID="${BATCH_SKILL_ID}" \
  MCP_SERVER_ID="${MCP_SERVER_ID}" \
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
batch_skill_id = os.environ["BATCH_SKILL_ID"]
mcp_server_id = os.environ["MCP_SERVER_ID"]
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
required_agent_allow = [f"{mcp_server_id}__*"]

if config_path.exists():
    config = json.loads(config_path.read_text(encoding="utf-8"))
else:
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
assign(agent, "skills", [plugin_id, batch_skill_id])

tools = agent.get("tools")
if not isinstance(tools, dict):
    tools = {}
    agent["tools"] = tools
    changed = True
assign(tools, "profile", "full")

def merge_string_list(target, key, additions, removals=()):
    global changed
    removal_set = set(removals)
    current = target.get(key)
    if current is None:
        current = []
    elif not isinstance(current, list):
        current = []
    else:
        current = [entry for entry in current if isinstance(entry, str) and entry not in removal_set]
    merged = list(current)
    for entry in additions:
        if entry not in merged:
            merged.append(entry)
    if target.get(key) != merged:
        target[key] = merged
        changed = True

merge_string_list(tools, "alsoAllow", required_agent_allow, removals=["bundle-mcp"])

sandbox = tools.get("sandbox")
if sandbox is None:
    sandbox = {}
    tools["sandbox"] = sandbox
    changed = True
elif not isinstance(sandbox, dict):
    sandbox = {}
    tools["sandbox"] = sandbox
    changed = True

sandbox_tools = sandbox.get("tools")
if sandbox_tools is None:
    sandbox_tools = {}
    sandbox["tools"] = sandbox_tools
    changed = True
elif not isinstance(sandbox_tools, dict):
    sandbox_tools = {}
    sandbox["tools"] = sandbox_tools
    changed = True

merge_string_list(sandbox_tools, "alsoAllow", required_agent_allow, removals=["bundle-mcp"])

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
  log "Verifying Factor Mining Batch Test skill visibility"
  skills_text="$("${OPENCLAW_BIN}" skills check --agent "${AGENT_ID}" 2>&1)" || {
    printf '%s\n' "${skills_text}" >&2
    fail "OpenClaw skills check failed for agent ${AGENT_ID}."
  }
  printf '%s\n' "${skills_text}"

  skills_json="$("${OPENCLAW_BIN}" skills check --agent "${AGENT_ID}" --json 2>/dev/null)" || {
    fail "OpenClaw skills check JSON output failed for agent ${AGENT_ID}."
  }
  SKILLS_JSON="${skills_json}" python3 - "${PLUGIN_ID}" "${BATCH_SKILL_ID}" <<'PY'
import json
import os
import sys

required = sys.argv[1:]
payload = json.loads(os.environ.get("SKILLS_JSON") or "{}")
model_visible = set(payload.get("modelVisible") or [])
agent_filtered = set(payload.get("agentFiltered") or [])
missing = [skill for skill in required if skill not in model_visible]
filtered = [skill for skill in required if skill in agent_filtered]
if missing:
    raise SystemExit(f"required skills are not modelVisible for the factormining agent: {', '.join(missing)}")
if filtered:
    raise SystemExit(f"required skills are agent-filtered for the factormining agent: {', '.join(filtered)}")
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

verify_model_auth() {
  local status_text
  log "Verifying OpenClaw model auth for agent ${AGENT_ID}"
  if status_text="$("${OPENCLAW_BIN}" models status --agent "${AGENT_ID}" --check 2>&1)"; then
    printf '%s\n' "${status_text}"
    return 0
  fi

  printf '%s\n' "${status_text}" >&2
  warn "OpenClaw model auth is not configured for the isolated ${AGENT_ID} agent."
  warn "Configure the model provider for this agent before running Factor Mining Batch Test turns."
  printf '%s\n' "Next action:"
  printf '%s\n' "  OPENCLAW_AGENT_DIR=\"${AGENT_DIR}\" openclaw models auth paste-api-key --provider minimax --profile-id minimax:manual"
}

tools_in_payload() {
  local payload="$1"
  local server_id="$2"
  REQUIRED_TOOLS_JSON="$(printf '%s\n' "${REQUIRED_MCP_TOOLS[@]}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')" \
  MCP_SERVER_ID="${server_id}" \
  PROBE_JSON="${payload}" python3 <<'PY'
import json
import os
import sys

required = json.loads(os.environ["REQUIRED_TOOLS_JSON"])
payload = os.environ.get("PROBE_JSON") or ""
server_id = os.environ["MCP_SERVER_ID"]

def names(value):
    found = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"name", "toolName", "id"} and isinstance(item, str):
                found.add(item)
            found.update(names(item))
    elif isinstance(value, list):
        for item in value:
            found.update(names(item))
    return found

try:
    parsed = json.loads(payload)
except Exception as exc:
    print(f"probe_json_parse_error={exc}", file=sys.stderr)
    raise SystemExit(1)

raw_names = names(parsed)
visible = {
    tool
    for tool in required
    if tool in raw_names or f"{server_id}__{tool}" in raw_names
}

missing = [tool for tool in required if tool not in visible]
if missing:
    print("missing=" + ",".join(missing))
    raise SystemExit(1)
print("all_required_mcp_tools_visible=true")
PY
}

verify_mcp_tools() {
  local output inspect_json plugin_root server_json probe_stdout probe_stderr probe_stderr_file

  log "Verifying installed OpenClaw plugin bundle"
  output="$("${OPENCLAW_BIN}" plugins inspect "${PLUGIN_ID}" 2>&1)" || {
    printf '%s\n' "${output}" >&2
    fail "OpenClaw plugin inspect failed for ${PLUGIN_ID}."
  }
  printf '%s\n' "${output}"
  if ! printf '%s\n' "${output}" | grep -Eiq 'mcp|bundle|factor_mining_batch_test_status'; then
    warn "Plugin inspect output did not show MCP details. Continuing to tool visibility checks."
  fi

  inspect_json="$("${OPENCLAW_BIN}" plugins inspect "${PLUGIN_ID}" --json --runtime 2>/dev/null)" || {
    fail "OpenClaw plugin inspect JSON output failed for ${PLUGIN_ID}."
  }
  plugin_root="$(INSPECT_JSON="${inspect_json}" python3 <<'PY'
import json
import os

payload = json.loads(os.environ["INSPECT_JSON"])
plugin = payload.get("plugin") or {}
if plugin.get("format") != "bundle":
    raise SystemExit("installed plugin is not a bundle")
if "mcpServers" not in set(payload.get("bundleCapabilities") or plugin.get("bundleCapabilities") or []):
    raise SystemExit("installed bundle does not report mcpServers capability")
root = plugin.get("rootDir") or plugin.get("source")
if not root:
    raise SystemExit("installed bundle root was not reported")
print(root)
PY
  )" || fail "OpenClaw plugin bundle metadata did not include the expected MCP capability."

  server_json="$(PLUGIN_ROOT="${plugin_root}" PYTHON_FOR_MCP="${PYTHON_FOR_MCP}" python3 <<'PY'
import json
import os

print(json.dumps({
    "command": os.environ["PYTHON_FOR_MCP"],
    "cwd": os.environ["PLUGIN_ROOT"],
    "args": ["./mcp/launch.py"],
}))
PY
  )"
  log "Configuring OpenClaw MCP startup for ${MCP_SERVER_ID}"
  "${OPENCLAW_BIN}" mcp set "${MCP_SERVER_ID}" "${server_json}" >/dev/null
  probe_stderr_file="$(mktemp)"
  if probe_stdout="$("${OPENCLAW_BIN}" mcp probe "${MCP_SERVER_ID}" --json 2>"${probe_stderr_file}")"; then
    probe_stderr="$(cat "${probe_stderr_file}")"
    rm -f "${probe_stderr_file}"
  else
    probe_stderr="$(cat "${probe_stderr_file}")"
    rm -f "${probe_stderr_file}"
    [[ -z "${probe_stdout:-}" ]] || printf '%s\n' "${probe_stdout}" >&2
    [[ -z "${probe_stderr}" ]] || printf '%s\n' "${probe_stderr}" >&2
    fail "OpenClaw MCP probe failed for ${MCP_SERVER_ID}."
  fi
  if printf '%s\n' "${probe_stderr}" | grep -Eiq 'provider[- ]?safe.*truncat|truncat.*provider[- ]?safe'; then
    printf '%s\n' "${probe_stderr}" >&2
    fail "OpenClaw MCP probe reported provider-safe tool-name truncation for ${MCP_SERVER_ID}."
  fi
  tools_in_payload "${probe_stdout}" "${MCP_SERVER_ID}" || fail "OpenClaw MCP probe JSON did not expose all Factor Mining Batch Test tools."
}

require_command "openclaw" "Install the OpenClaw CLI first, then rerun this installer. For npm-based installs, run: npm install -g openclaw"
require_command "python3" "Install Python 3, then rerun this installer."

OPENCLAW_BIN="$(command -v openclaw)"
PYTHON_FOR_MCP="$(command -v python3)"
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
plugin_install_output="$("${OPENCLAW_BIN}" plugins install "${PLUGIN_ID}" --marketplace "${MARKETPLACE_SOURCE}" --force 2>&1)" || {
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

config_hash_after="$(config_hash "${CONFIG_PATH}")"
if [[ "${config_hash_before}" != "${config_hash_after}" || "${patch_output}" == *"agent_config_changed=true"* ]]; then
  gateway_reload_needed="1"
fi

if [[ "${patch_output}" == *"global_deny_blockers="* ]]; then
  blockers="$(printf '%s\n' "${patch_output}" | awk -F= '/^global_deny_blockers=/{print $2}')"
  if [[ -n "${blockers}" ]]; then
    warn "OpenClaw global tools.deny blocks required local-agent capabilities: ${blockers}"
    warn "Factor Mining work needs local read/write/edit/apply_patch/exec/process/web_fetch capability. This installer does not change global deny policy."
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

verify_mcp_tools
verify_skills
verify_nodes
verify_model_auth

printf '\n%s\n' "OpenClaw Factor Mining Batch Test is installed."
printf '\n%s\n' "Next commands:"
printf '%s\n' 'openclaw agent --agent factormining --message "Use Factor Mining Batch Test. Open the local browser setup page for my Factor Mining Agent API Key, then verify status. Do not ask me to paste the key into chat."'
printf '%s\n' 'openclaw agent --agent factormining --message "Use Factor Mining Batch Test. Verify status, then show me the Factor Mining public task list. Do not create a session until I choose a public task or provide a custom idea."'
printf '%s\n' 'openclaw agent --agent factormining --message "Use Factor Mining Batch Test to mine 5 distinct factors from the public task list."'
