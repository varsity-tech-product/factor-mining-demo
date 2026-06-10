#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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


def _s(*parts: str) -> str:
    return "".join(parts)


def _literal_ci(*parts: str) -> re.Pattern[str]:
    return re.compile(re.escape(_s(*parts)), re.IGNORECASE)


def _literal_cs(*parts: str) -> re.Pattern[str]:
    return re.compile(re.escape(_s(*parts)))


FORBIDDEN_ANYWHERE_PATTERNS = {
    _s("/bin/", "z", "sh"): _literal_ci("/bin/", "z", "sh"),
    _s("z", "sh"): re.compile(r"\b" + re.escape(_s("z", "sh")) + r"\b", re.IGNORECASE),
    _s("sh", " -lc"): re.compile(r"\b" + re.escape("sh") + r"\s+-lc\b", re.IGNORECASE),
    _s("cmd", ".exe"): re.compile(r"\b" + re.escape(_s("cmd", ".exe")) + r"\b", re.IGNORECASE),
    _s("power", "shell"): re.compile(r"\b" + re.escape(_s("power", "shell")) + r"\b", re.IGNORECASE),
    _s("wrap", "per"): re.compile(r"\b" + re.escape(_s("wrap", "per")) + r"\b", re.IGNORECASE),
    _s("python3 ", "scripts"): re.compile(r"python3\s+" + re.escape("scripts"), re.IGNORECASE),
    _s("scripts/", "factor"): _literal_ci("scripts/", "factor"),
    _s("factor-mining-demo-", "status"): _literal_ci("factor-mining-demo-", "status"),
    _s("factor-mining-demo-", "api"): _literal_ci("factor-mining-demo-", "api"),
    _s("factor-mining-demo-upload-", "backtest"): _literal_ci("factor-mining-demo-upload-", "backtest"),
    _s("helper ", "scripts"): _literal_ci("helper ", "scripts"),
    _s("Local Agent ", "Connect"): _literal_ci("Local Agent ", "Connect"),
    _s("Bud", "dy"): _literal_ci("Bud", "dy"),
    _s("P", "KCE"): _literal_ci("P", "KCE"),
    _s("quandora", "_connect"): _literal_ci("quandora", "_connect"),
    _s("T", "ODO"): _literal_ci("T", "ODO"),
    _s("FIX", "ME"): _literal_ci("FIX", "ME"),
    _s("M", "VP"): _literal_ci("M", "VP"),
    _s("private ", "repo"): _literal_ci("private ", "repo"),
    _s("return to ", "Codex"): _literal_cs("return to ", "Codex"),
    _s("Codex ", "plugin"): _literal_cs("Codex ", "plugin"),
    _s("local setup ", "helper"): _literal_cs("local setup ", "helper"),
}
FORBIDDEN_PACKAGE_DOC_PATTERNS = {
    _s("ba", "sh"): re.compile(r"\b" + re.escape(_s("ba", "sh")) + r"\b", re.IGNORECASE),
}
PRODUCT_FACING_FILES = [
    ROOT / "README.md",
    ROOT / "install-openclaw.sh",
    PLUGIN / "README.md",
    PLUGIN / ".mcp.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / ".claude-plugin" / "plugin.json",
    PLUGIN / "skills" / "factor-mining-demo" / "SKILL.md",
    PLUGIN / "skills" / "factor-mining-demo" / "agents" / "openai.yaml",
    MCP_ROOT / "factor_mining_agent_lib" / "browser_setup.py",
    MCP_ROOT / "factor_mining_agent_lib" / "__init__.py",
]
PACKAGE_DOC_FILES = [
    PLUGIN / "README.md",
    PLUGIN / ".mcp.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / ".claude-plugin" / "plugin.json",
    PLUGIN / "skills" / "factor-mining-demo" / "SKILL.md",
    MCP_ROOT / "factor_mining_agent_lib" / "browser_setup.py",
    MCP_ROOT / "factor_mining_agent_lib" / "__init__.py",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_openai_skill_dependency(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    required_lines = {
        "type": '    - type: "mcp"',
        "value": '      value: "fm-demo"',
        "transport": '      transport: "stdio"',
    }
    missing = [key for key, line in required_lines.items() if line not in text]
    if missing:
        raise AssertionError(f"{path.relative_to(ROOT)} missing OpenAI MCP dependency fields: {missing}")
    return {"type": "mcp", "value": "fm-demo", "transport": "stdio"}


def require(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing required path: {path.relative_to(ROOT)}")


def require_absent(path: Path) -> None:
    if path.exists():
        raise AssertionError(f"unexpected path: {path.relative_to(ROOT)}")


def require_no_product_forbidden_text() -> None:
    failures: list[str] = []
    for path in PRODUCT_FACING_FILES:
        require(path)
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_ANYWHERE_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)} contains forbidden product-facing text: {label}")
    for path in PACKAGE_DOC_FILES:
        require(path)
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PACKAGE_DOC_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)} contains forbidden product-facing text: {label}")
    if failures:
        raise AssertionError("\n".join(failures))


def main() -> None:
    require(ROOT / ".agents" / "plugins" / "marketplace.json")
    require(ROOT / ".claude-plugin" / "marketplace.json")
    require(PLUGIN / ".codex-plugin" / "plugin.json")
    require(PLUGIN / ".claude-plugin" / "plugin.json")
    require(PLUGIN / ".mcp.json")
    require(PLUGIN / "skills" / "factor-mining-demo" / "SKILL.md")
    require(PLUGIN / "skills" / "factor-mining-demo" / "agents" / "openai.yaml")
    require(MCP_ROOT / "launch.py")
    require(MCP_ROOT / "server.py")
    require_no_product_forbidden_text()

    require_absent(ROOT / ".codex-plugin")
    require_absent(ROOT / _s("install-", "codex.sh"))
    require_absent(ROOT / _s("install-", "codex-", "desktop.sh"))
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
    assert server["command"] == "python"
    assert server["cwd"] == "."
    assert server["args"] == ["./mcp/launch.py"]
    openai_dependency = load_openai_skill_dependency(
        PLUGIN / "skills" / "factor-mining-demo" / "agents" / "openai.yaml"
    )
    assert openai_dependency["value"] in mcp["mcpServers"]

    sys.path.insert(0, str(MCP_ROOT))
    import server as mcp_server

    missing = REQUIRED_TOOLS.difference(mcp_server.list_tool_names())
    if missing:
        raise AssertionError(f"missing MCP tools: {sorted(missing)}")

    print("packaging validation passed")


if __name__ == "__main__":
    main()
