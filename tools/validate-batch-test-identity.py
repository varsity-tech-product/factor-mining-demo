#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "factor-mining-batch-test"
MCP_ROOT = PLUGIN / "mcp"

MARKETPLACE_NAME = "factor-mining-batch-test-marketplace"
PLUGIN_NAME = "factor-mining-batch-test"
DISPLAY_NAME = "Factor Mining Batch Test"
MCP_SERVER_ID = "fmbt"
OLD_MCP_SERVER_ID = "factor-mining-batch-test"
OPENCLAW_TOOL_NAME_LIMIT = 64
MAIN_SKILL = "factor-mining-batch-test"
BATCH_SKILL = "factor-mining-batch-test-batch"
STATE_DIR = ".factor-mining-batch-test"
HOME_ENV = "FACTOR_MINING_BATCH_TEST_HOME"

SINGLE_TOOLS = {
    "factor_mining_batch_test_status",
    "factor_mining_batch_test_setup_browser",
    "factor_mining_batch_test_list_public_tasks",
    "factor_mining_batch_test_create_task_session",
    "factor_mining_batch_test_create_custom_session",
    "factor_mining_batch_test_parse_plugin_metadata",
    "factor_mining_batch_test_request_dedup_context",
    "factor_mining_batch_test_upload_backtest_wait",
    "factor_mining_batch_test_resume_run",
    "factor_mining_batch_test_get_workflow",
    "factor_mining_batch_test_get_job",
    "factor_mining_batch_test_get_artifact",
    "factor_mining_batch_test_clear_config",
}
BATCH_TOOLS = {
    "factor_mining_batch_test_batch_start",
    "factor_mining_batch_test_batch_next",
    "factor_mining_batch_test_batch_upload_backtest_wait",
    "factor_mining_batch_test_batch_status",
    "factor_mining_batch_test_batch_results",
    "factor_mining_batch_test_batch_cancel",
}
PRODUCT_FACING_DOCS = [
    ROOT / "README.md",
    ROOT / "install-openclaw.sh",
    PLUGIN / "README.md",
    PLUGIN / "skills" / MAIN_SKILL / "SKILL.md",
    PLUGIN / "skills" / BATCH_SKILL / "SKILL.md",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_file(path: Path) -> None:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")


def require_no_old_openclaw_provider_prefix() -> None:
    old_prefix = f"{OLD_MCP_SERVER_ID}__"
    failures = []
    for path in PRODUCT_FACING_DOCS:
        text = path.read_text(encoding="utf-8")
        if old_prefix in text:
            failures.append(f"{path.relative_to(ROOT)} contains old OpenClaw provider prefix {old_prefix}")
    require(not failures, "\n".join(failures))


def require_openclaw_provider_safe_names(tool_names: set[str]) -> None:
    failures = []
    for tool_name in sorted(tool_names):
        provider_safe_name = f"{MCP_SERVER_ID}__{tool_name}"
        if len(provider_safe_name) > OPENCLAW_TOOL_NAME_LIMIT:
            failures.append(
                f"{provider_safe_name} is {len(provider_safe_name)} chars, "
                f"exceeding OpenClaw's {OPENCLAW_TOOL_NAME_LIMIT}-char limit"
            )
        if provider_safe_name[:OPENCLAW_TOOL_NAME_LIMIT] != provider_safe_name:
            failures.append(f"{provider_safe_name} would be truncated by OpenClaw")
    require(not failures, "\n".join(failures))


def require_openclaw_installer_probe_validation() -> None:
    text = (ROOT / "install-openclaw.sh").read_text(encoding="utf-8")
    require(f'MCP_SERVER_ID="{MCP_SERVER_ID}"' in text, "OpenClaw installer must set MCP_SERVER_ID to fmbt")
    require('required_agent_allow = [f"{mcp_server_id}__*"]' in text, "OpenClaw allowlist must use the short MCP server id")
    require('mcp set "${MCP_SERVER_ID}"' in text, "OpenClaw installer must configure MCP startup under fmbt")
    probe_lines = [line.strip() for line in text.splitlines() if "mcp probe" in line]
    require(probe_lines, "OpenClaw installer must probe the MCP server")
    for line in probe_lines:
        require('"${MCP_SERVER_ID}" --json' in line, "OpenClaw installer must probe fmbt with --json")
        require("2>&1" not in line, "OpenClaw MCP probe must not combine stdout and stderr")
    require("PROBE_JSON" in text, "OpenClaw tool visibility parser must read JSON stdout")
    require("json.loads(payload)" in text, "OpenClaw tool visibility parser must parse JSON stdout")
    require("parsed = payload" not in text, "OpenClaw tool visibility parser must not fall back to raw string search")
    require("probe_json_parse_error" in text, "OpenClaw installer must fail clearly when probe JSON parsing fails")
    require("provider[- ]?safe.*truncat|truncat.*provider[- ]?safe" in text, "OpenClaw installer must fail on provider-safe truncation warnings")
    require('tools_in_payload "${probe_stdout}" "${MCP_SERVER_ID}"' in text, "OpenClaw installer must validate only probe stdout")


def require_skill_mcp_dependency(skill_name: str) -> None:
    skill_root = PLUGIN / "skills" / skill_name
    require_file(skill_root / "SKILL.md")
    openai_yaml = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    require("type: mcp" in openai_yaml, f"{skill_name} openai.yaml must declare an MCP dependency")
    require(f"value: {MCP_SERVER_ID}" in openai_yaml, f"{skill_name} openai.yaml must use {MCP_SERVER_ID}")
    require("transport: stdio" in openai_yaml, f"{skill_name} openai.yaml must use stdio transport")


def load_server_module() -> Any:
    if str(MCP_ROOT) not in sys.path:
        sys.path.insert(0, str(MCP_ROOT))
    spec = importlib.util.spec_from_file_location("batch_test_server", MCP_ROOT / "server.py")
    require(spec is not None and spec.loader is not None, "could not create server module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    required_files = [
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / ".claude-plugin" / "marketplace.json",
        ROOT / "install-openclaw.sh",
        PLUGIN / ".codex-plugin" / "plugin.json",
        PLUGIN / ".claude-plugin" / "plugin.json",
        PLUGIN / ".mcp.json",
        PLUGIN / "README.md",
        MCP_ROOT / "launch.py",
        MCP_ROOT / "server.py",
    ]
    for path in required_files:
        require_file(path)
    for path in PRODUCT_FACING_DOCS:
        require_file(path)
    require_no_old_openclaw_provider_prefix()
    require_openclaw_installer_probe_validation()

    marketplace = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    require(marketplace.get("name") == MARKETPLACE_NAME, "Codex marketplace name is not batch-test")
    require(marketplace.get("interface", {}).get("displayName") == DISPLAY_NAME, "Codex display name is not batch-test")
    plugins = marketplace.get("plugins")
    require(isinstance(plugins, list) and len(plugins) == 1, "Codex marketplace must expose one plugin")
    require(plugins[0].get("name") == PLUGIN_NAME, "Codex marketplace plugin name is not batch-test")
    require(plugins[0].get("source", {}).get("path") == f"./plugins/{PLUGIN_NAME}", "Codex source path is wrong")

    claude_marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    require(claude_marketplace.get("name") == MARKETPLACE_NAME, "Claude marketplace name is not batch-test")
    claude_plugins = claude_marketplace.get("plugins")
    require(isinstance(claude_plugins, list) and len(claude_plugins) == 1, "Claude marketplace must expose one plugin")
    require(claude_plugins[0].get("name") == PLUGIN_NAME, "Claude marketplace plugin name is not batch-test")
    require(claude_plugins[0].get("source") == f"./plugins/{PLUGIN_NAME}", "Claude source path is wrong")

    codex_plugin = load_json(PLUGIN / ".codex-plugin" / "plugin.json")
    require(codex_plugin.get("name") == PLUGIN_NAME, "Codex plugin name is not batch-test")
    require(codex_plugin.get("skills") == "./skills/", "Codex plugin must expose skills")
    require(codex_plugin.get("mcpServers") == "./.mcp.json", "Codex plugin must expose .mcp.json")
    require(codex_plugin.get("interface", {}).get("displayName") == DISPLAY_NAME, "Codex plugin display name is wrong")

    claude_plugin = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    require(claude_plugin.get("name") == PLUGIN_NAME, "Claude plugin name is not batch-test")
    require(MCP_SERVER_ID in claude_plugin.get("mcpServers", {}), "Claude MCP server id is wrong")

    mcp_json = load_json(PLUGIN / ".mcp.json")
    require(MCP_SERVER_ID in mcp_json.get("mcpServers", {}), ".mcp.json server id is wrong")

    require_skill_mcp_dependency(MAIN_SKILL)
    require_skill_mcp_dependency(BATCH_SKILL)

    batch_skill = (PLUGIN / "skills" / BATCH_SKILL / "SKILL.md").read_text(encoding="utf-8")
    require("Do not read sibling attempt directories" in batch_skill, "batch skill must prohibit sibling inspection")

    server = load_server_module()
    names = set(server.list_tool_names())
    expected = SINGLE_TOOLS | BATCH_TOOLS
    require(names == expected, f"MCP tools mismatch: missing={sorted(expected - names)} extra={sorted(names - expected)}")
    require_openclaw_provider_safe_names(expected)
    require(server.SERVER_NAME == MCP_SERVER_ID, "MCP server name is wrong")
    require(
        "factor_mining_batch_test_setup_browser" in server.MISSING_CREDENTIAL_MESSAGE,
        "setup message must use batch-test tool names",
    )

    from factor_mining_agent_lib import config

    require(config.DEFAULT_HOME.name == STATE_DIR, "local state dir is wrong")
    require(config.HOME_ENV == HOME_ENV, "home environment variable is wrong")

    print("batch-test identity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
