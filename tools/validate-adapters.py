#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "factor-mining-demo"
MCP_ROOT = PLUGIN / "mcp"
REQUIRED_TOOLS = {
    "factor_mining_demo_status",
    "factor_mining_demo_setup_browser",
    "factor_mining_demo_list_public_tasks",
    "factor_mining_demo_create_task_session",
    "factor_mining_demo_create_custom_session",
    "factor_mining_demo_parse_plugin_metadata",
    "factor_mining_demo_request_dedup_context",
    "factor_mining_demo_upload_backtest_wait",
    "factor_mining_demo_resume_run",
    "factor_mining_demo_get_workflow",
    "factor_mining_demo_get_job",
    "factor_mining_demo_get_artifact",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing required path: {path.relative_to(ROOT)}")


def require_absent(path: Path) -> None:
    if path.exists():
        raise AssertionError(f"unexpected path: {path.relative_to(ROOT)}")


def main() -> None:
    require(ROOT / ".agents" / "plugins" / "marketplace.json")
    require(ROOT / ".claude-plugin" / "marketplace.json")
    require(PLUGIN / ".codex-plugin" / "plugin.json")
    require(PLUGIN / ".claude-plugin" / "plugin.json")
    require(PLUGIN / ".mcp.json")
    require(PLUGIN / "skills" / "factor-mining-demo" / "SKILL.md")
    require(MCP_ROOT / "server.py")

    require_absent(ROOT / ".codex-plugin")
    require_absent(ROOT / "scripts")
    require_absent(ROOT / "skills")
    require_absent(ROOT / "adapters" / "claude-code" / "factor-mining-demo" / "bin")
    require_absent(MCP_ROOT / "factor_mining_agent_lib" / "cli.py")

    codex_marketplace = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    codex_entry = codex_marketplace["plugins"][0]
    assert codex_entry["name"] == "factor-mining-demo"
    assert codex_entry["source"] == {"source": "local", "path": "./plugins/factor-mining-demo"}

    claude_marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    claude_entry = claude_marketplace["plugins"][0]
    assert claude_entry["name"] == "factor-mining-demo"
    assert claude_entry["source"] == "./plugins/factor-mining-demo"

    codex_plugin = load_json(PLUGIN / ".codex-plugin" / "plugin.json")
    assert codex_plugin["skills"] == "./skills/"
    assert codex_plugin["mcpServers"] == "./.mcp.json"

    mcp = load_json(PLUGIN / ".mcp.json")
    server = mcp["mcpServers"]["fm-demo"]
    assert server["command"] == "/bin/zsh"
    assert server["cwd"] == "."
    assert server["args"] == ["-lc", "exec python3 ./mcp/server.py"]

    sys.path.insert(0, str(MCP_ROOT))
    import server as mcp_server

    missing = REQUIRED_TOOLS.difference(mcp_server.list_tool_names())
    if missing:
        raise AssertionError(f"missing MCP tools: {sorted(missing)}")

    print("packaging validation passed")


if __name__ == "__main__":
    main()
