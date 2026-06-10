#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "plugins" / "factor-mining-demo" / "mcp"
sys.path.insert(0, str(MCP_ROOT))

import server as mcp_server
from factor_mining_agent_lib.config import AgentConfig, save_config


OLD_TOOLS = {
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
    "factor_mining_demo_clear_config",
}
BATCH_TOOLS = {
    "factor_mining_demo_batch_start",
    "factor_mining_demo_batch_next",
    "factor_mining_demo_batch_upload_backtest_wait",
    "factor_mining_demo_batch_status",
    "factor_mining_demo_batch_results",
    "factor_mining_demo_batch_cancel",
}
GENERIC_UPLOAD_PROPERTIES = {
    "session_id",
    "plugin_path",
    "client_run_id",
    "parent_client_run_id",
    "position_mode",
    "fwd_period",
    "decision_summary",
    "wait",
    "poll_interval",
    "timeout",
    "artifact_name",
    "output_dir",
    "home",
}
TASK_PAYLOAD = {
    "task_id": "validation-custom-task",
    "title": "Validation factor idea",
    "category": "validation",
    "description": "Validate batch state isolation.",
    "allowed_data": ["close", "volume"],
    "fwd_period": 7,
}


class FakeApiClient:
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def agent_status(self) -> dict[str, str]:
        return {"status": "ok", "agent_key": "valid"}


def _tool_schema(name: str) -> dict[str, Any]:
    for tool in mcp_server.TOOL_DEFINITIONS:
        if tool["name"] == name:
            return dict(tool["inputSchema"])
    raise AssertionError(f"missing tool schema: {name}")


def _read_batch(home: Path, batch_id: str) -> dict[str, Any]:
    with (home / "batches" / batch_id / "batch.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_batch(home: Path, batch_id: str, payload: dict[str, Any]) -> None:
    path = home / "batches" / batch_id / "batch.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _assert_private(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise AssertionError(f"{path.name} should be owner-only, got {oct(mode)}")


def test_tools_and_existing_schema() -> None:
    names = set(mcp_server.list_tool_names())
    tools_list = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    listed_names = {tool["name"] for tool in tools_list["result"]["tools"]}
    missing_old = OLD_TOOLS.difference(names)
    missing_batch = BATCH_TOOLS.difference(names)
    missing_listed_old = OLD_TOOLS.difference(listed_names)
    missing_listed_batch = BATCH_TOOLS.difference(listed_names)
    if missing_old or missing_batch or missing_listed_old or missing_listed_batch:
        raise AssertionError(
            "missing tools "
            f"helper_old={sorted(missing_old)} helper_batch={sorted(missing_batch)} "
            f"listed_old={sorted(missing_listed_old)} listed_batch={sorted(missing_listed_batch)}"
        )

    schema = _tool_schema("factor_mining_demo_upload_backtest_wait")
    assert schema["required"] == ["session_id", "plugin_path"]
    assert set(schema["properties"]) == GENERIC_UPLOAD_PROPERTIES


def test_status_without_config_returns_setup_required() -> None:
    with tempfile.TemporaryDirectory() as temp:
        result = mcp_server.call_tool("factor_mining_demo_status", {"home": temp})
    assert result["ok"] is True
    assert result["configured"] is False
    assert result["setup_required"] is True


def test_batch_isolation_and_sanitization() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            save_config(
                AgentConfig(
                    base_url="https://example.invalid",
                    api_key="vt_validation_secret_123456789",
                    agent_status={"status": "ok", "agent_key": "valid"},
                ),
                home=home,
            )
            start = mcp_server.call_tool(
                "factor_mining_demo_batch_start",
                {
                    "count": 2,
                    "mode": "custom_idea",
                    "idea": "Validate two isolated factor attempts.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            assert start["ok"] is True
            batch_id = start["batch_id"]

            batch_dir = home / "batches" / batch_id
            batch_json = batch_dir / "batch.json"
            _assert_private(batch_dir)
            _assert_private(batch_json)

            batch = _read_batch(home, batch_id)
            attempts = batch["attempts"]
            assert len(attempts) == 2
            assert Path(attempts[0]["plugin_path"]).parent != Path(attempts[1]["plugin_path"]).parent
            assert Path(attempts[0]["plugin_path"]).name == "plugin.py"
            assert "vt_validation_secret_123456789" not in json.dumps(batch)

            first = mcp_server.call_tool("factor_mining_demo_batch_next", {"batch_id": batch_id, "home": str(home)})
            assert first["done"] is False
            assert first["index"] == 1
            assert first["count"] == 2
            assert first["plugin_path"] == attempts[0]["plugin_path"]
            assert first["output_dir"] == attempts[0]["output_dir"]
            assert "attempts" not in first
            assert "formula" not in json.dumps(first).lower()

            outside = home / "outside.py"
            outside.write_text("FACTOR_TYPE='x'\nFACTOR_NAME='x'\nFACTOR_DEFAULT_PARAMS={}\n", encoding="utf-8")
            try:
                mcp_server.call_tool(
                    "factor_mining_demo_batch_upload_backtest_wait",
                    {
                        "batch_id": batch_id,
                        "attempt_id": first["attempt_id"],
                        "session_id": "session-1",
                        "plugin_path": str(outside),
                        "home": str(home),
                    },
                )
            except Exception as exc:
                assert "current attempt" in str(exc) or "attempt directory" in str(exc)
            else:
                raise AssertionError("outside plugin_path was accepted")

            submitted = _read_batch(home, batch_id)
            submitted["status"] = "running"
            submitted["attempts"][0]["status"] = "submitted"
            submitted["attempts"][1]["status"] = "pending"
            _write_batch(home, batch_id, submitted)
            still_current = mcp_server.call_tool(
                "factor_mining_demo_batch_next",
                {"batch_id": batch_id, "home": str(home)},
            )
            assert still_current["index"] == 1
            after_submitted_next = _read_batch(home, batch_id)
            assert after_submitted_next["attempts"][1]["status"] == "pending"

            polluted = _read_batch(home, batch_id)
            polluted["attempts"][0].update(
                {
                    "status": "failed",
                    "factor_name": "Leaky vt_validation_secret_123456789",
                    "factor_type": "validation",
                    "metrics": {
                        "sharpe": 1.23,
                        "artifact_url": "https://example.invalid/object?X-Amz-Signature=abc",
                        "local_path": str(home / "batches" / batch_id / "attempts" / "001" / "plugin.py"),
                    },
                    "error": f"failed near {home}/batches/{batch_id}/attempts/001/plugin.py",
                }
            )
            _write_batch(home, batch_id, polluted)

            results = mcp_server.call_tool("factor_mining_demo_batch_results", {"batch_id": batch_id, "home": str(home)})
            rendered = json.dumps(results, sort_keys=True)
            assert results["ok"] is True
            assert "plugin_path" not in rendered
            assert "attempt_dir" not in rendered
            assert "output_dir" not in rendered
            assert "vt_validation_secret_123456789" not in rendered
            assert "X-Amz-Signature" not in rendered
            assert str(home) not in rendered
    finally:
        mcp_server.ApiClient = original_client


def main() -> int:
    test_tools_and_existing_schema()
    test_status_without_config_returns_setup_required()
    test_batch_isolation_and_sanitization()
    print("batch MCP validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
