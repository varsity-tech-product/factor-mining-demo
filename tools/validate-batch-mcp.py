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
MCP_ROOT = ROOT / "plugins" / "factor-mining-batch-test" / "mcp"
sys.path.insert(0, str(MCP_ROOT))

import server as mcp_server
from factor_mining_agent_lib.batch import record_attempt_result
from factor_mining_agent_lib.config import AgentConfig, save_config


SKILL_PATH = ROOT / "plugins" / "factor-mining-batch-test" / "skills" / "factor-mining-batch-test-batch" / "SKILL.md"
OLD_TOOLS = {
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
SUBMISSION_POSITION_MODES = ["sigmoid_continuous", "quantile_discrete", "both"]
TASK_PAYLOAD = {
    "task_id": "validation-custom-task",
    "title": "Validation factor idea",
    "category": "validation",
    "description": "Validate batch state isolation.",
    "allowed_data": ["close", "volume"],
    "fwd_period": 7,
}
VALIDATION_KEY = "vt_" "validation_secret_123456789"


class FakeApiClient:
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def agent_status(self) -> dict[str, str]:
        return {"status": "ok", "agent_key": "valid"}


class NetworkFailingApiClient(FakeApiClient):
    def upload_plugin(self, **kwargs: Any) -> dict[str, Any]:
        raise mcp_server.ApiError(
            "Factor Mining API request could not connect: validation network failure",
            method="POST",
            url="https://example.invalid/sessions/session-1/plugins/upload?token=secret",
            api_key=VALIDATION_KEY,
        )


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


def _save_validation_config(home: Path) -> None:
    save_config(
        AgentConfig(
            base_url="https://example.invalid",
            api_key=VALIDATION_KEY,
            agent_status={"status": "ok", "agent_key": "valid"},
        ),
        home=home,
    )


def _write_valid_plugin(path: str | Path) -> None:
    Path(path).write_text(
        "\n".join(
            [
                'FACTOR_TYPE = "validation_momentum"',
                'FACTOR_NAME = "Validation Momentum"',
                'FACTOR_DEFAULT_PARAMS = {"window": 7}',
                "",
            ]
        ),
        encoding="utf-8",
    )


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

    schema = _tool_schema("factor_mining_batch_test_upload_backtest_wait")
    assert schema["required"] == ["session_id", "plugin_path"]
    assert set(schema["properties"]) == GENERIC_UPLOAD_PROPERTIES
    assert schema["properties"]["position_mode"]["enum"] == SUBMISSION_POSITION_MODES

    batch_schema = _tool_schema("factor_mining_batch_test_batch_start")
    assert batch_schema["properties"]["position_mode"]["enum"] == SUBMISSION_POSITION_MODES


def test_status_without_config_returns_setup_required() -> None:
    with tempfile.TemporaryDirectory() as temp:
        result = mcp_server.call_tool("factor_mining_batch_test_status", {"home": temp})
    assert result["ok"] is True
    assert result["configured"] is False
    assert result["setup_required"] is True


def test_public_task_batch_start_requires_task_id_helpfully() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            try:
                mcp_server.call_tool(
                    "factor_mining_batch_test_batch_start",
                    {"count": 2, "mode": "public_task", "home": str(home)},
                )
            except Exception as exc:
                message = str(exc)
                assert "task_id" in message
                assert "public_task" in message
            else:
                raise AssertionError("public_task batch_start without task_id was accepted")
    finally:
        mcp_server.ApiClient = original_client


def test_batch_skill_public_task_flow_lists_tasks_before_start() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    public_section_start = text.index("For public task mode")
    public_section = text[public_section_start:]
    list_index = public_section.index("factor_mining_batch_test_list_public_tasks")
    start_index = public_section.index("factor_mining_batch_test_batch_start")
    assert list_index < start_index


def test_batch_start_normalizes_backend_cs_only_output_to_submission_default() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 1,
                    "mode": "custom_idea",
                    "idea": "Validate backend output mode normalization.",
                    "task_payload": TASK_PAYLOAD,
                    "position_mode": "cs_only",
                    "home": str(home),
                },
            )
            batch = _read_batch(home, start["batch_id"])
            assert batch["position_mode"] == "both"
    finally:
        mcp_server.ApiClient = original_client


def test_batch_isolation_and_sanitization() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
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
            assert VALIDATION_KEY not in json.dumps(batch)

            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            assert first["done"] is False
            assert first["index"] == 1
            assert first["count"] == 2
            assert first["plugin_path"] == attempts[0]["plugin_path"]
            assert first["output_dir"] == attempts[0]["output_dir"]
            assert "attempts" not in first
            assert "formula" not in json.dumps(first).lower()

            outside = home / "outside.py"
            outside.write_text("FACTOR_TYPE='x'\nFACTOR_NAME='x'\nFACTOR_DEFAULT_PARAMS={}\n", encoding="utf-8")
            outside_result = mcp_server.call_tool(
                "factor_mining_batch_test_batch_upload_backtest_wait",
                {
                    "batch_id": batch_id,
                    "attempt_id": first["attempt_id"],
                    "session_id": "session-1",
                    "plugin_path": str(outside),
                    "home": str(home),
                },
            )
            assert outside_result["ok"] is False
            assert outside_result["status"] == "failed"
            assert "current attempt" in json.dumps(outside_result) or "attempt directory" in json.dumps(outside_result)

            submitted = _read_batch(home, batch_id)
            submitted["status"] = "running"
            submitted["attempts"][0]["status"] = "submitted"
            submitted["attempts"][1]["status"] = "pending"
            _write_batch(home, batch_id, submitted)
            still_current = mcp_server.call_tool(
                "factor_mining_batch_test_batch_next",
                {"batch_id": batch_id, "home": str(home)},
            )
            assert still_current["index"] == 1
            after_submitted_next = _read_batch(home, batch_id)
            assert after_submitted_next["attempts"][1]["status"] == "pending"

            polluted = _read_batch(home, batch_id)
            polluted["attempts"][0].update(
                {
                    "status": "failed",
                    "factor_name": f"Leaky {VALIDATION_KEY}",
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

            results = mcp_server.call_tool("factor_mining_batch_test_batch_results", {"batch_id": batch_id, "home": str(home)})
            rendered = json.dumps(results, sort_keys=True)
            assert results["ok"] is True
            assert "plugin_path" not in rendered
            assert "attempt_dir" not in rendered
            assert "output_dir" not in rendered
            assert VALIDATION_KEY not in rendered
            assert "X-Amz-Signature" not in rendered
            assert str(home) not in rendered
    finally:
        mcp_server.ApiClient = original_client


def test_batch_upload_network_failure_blocks_without_failed_attempt_or_advancing() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = NetworkFailingApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 2,
                    "mode": "custom_idea",
                    "idea": "Validate network blocker handling.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            batch_id = start["batch_id"]
            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            _write_valid_plugin(first["plugin_path"])

            result = mcp_server.call_tool(
                "factor_mining_batch_test_batch_upload_backtest_wait",
                {
                    "batch_id": batch_id,
                    "attempt_id": first["attempt_id"],
                    "session_id": "session-1",
                    "plugin_path": first["plugin_path"],
                    "home": str(home),
                },
            )
            assert result["ok"] is False
            assert result["status"] in {"blocked", "system_error"}
            assert "retry" in result["next_action"].lower() or "setup" in result["next_action"].lower()

            state = _read_batch(home, batch_id)
            assert state["status"] in {"blocked", "system_error"}
            assert state["attempts"][0]["status"] in {"active", "blocked", "system_error"}
            assert state["attempts"][0]["status"] != "failed"
            assert state["attempts"][1]["status"] == "pending"

            status = mcp_server.call_tool("factor_mining_batch_test_batch_status", {"batch_id": batch_id, "home": str(home)})
            status_rendered = json.dumps(status).lower()
            assert status["status"] in {"blocked", "system_error"}
            assert "retry" in status_rendered or "setup" in status_rendered
            assert "next isolated attempt" not in status_rendered

            still_current = mcp_server.call_tool(
                "factor_mining_batch_test_batch_next",
                {"batch_id": batch_id, "home": str(home)},
            )
            assert still_current["index"] == 1
            after_next = _read_batch(home, batch_id)
            assert after_next["attempts"][1]["status"] == "pending"
    finally:
        mcp_server.ApiClient = original_client


def test_batch_attempts_preserve_single_run_result_summary() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 1,
                    "mode": "custom_idea",
                    "idea": "Validate result summary preservation.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            batch_id = start["batch_id"]
            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            single_result = {
                "ok": True,
                "status": "succeeded",
                "terminal_status": "succeeded",
                "client_run_id": first["client_run_id"],
                "session_id": "session-secret",
                "plugin_id": "plugin-secret",
                "job_ids": ["job-secret"],
                "jobs": [
                    {
                        "job_id": "job-secret",
                        "id": "job-secret",
                        "status": "done",
                        "position_mode": "cs_only",
                        "failure_diagnostics": "",
                    }
                ],
                "artifact": {
                    "status": "available",
                    "name": "default_factor_card.json",
                    "path": str(home / "attempts" / "001" / "artifacts" / "default_factor_card.json"),
                },
                "summary": {
                    "factor_name": "Validation Result Momentum",
                    "metrics": {
                        "rank_ic": 0.031,
                        "rank_icir": 0.42,
                        "composite_sharpe": 1.7,
                    },
                    "jobs": [
                        {
                            "job_id": "job-secret",
                            "status": "done",
                            "position_mode": "cs_only",
                        }
                    ],
                    "fish": {"level": "A"},
                },
            }

            attempt_result = record_attempt_result(
                batch_id=batch_id,
                attempt_id=first["attempt_id"],
                result=single_result,
                metadata={"factor_name": "Validation Result Momentum", "factor_type": "validation_result_momentum"},
                home=home,
            )
            results = mcp_server.call_tool("factor_mining_batch_test_batch_results", {"batch_id": batch_id, "home": str(home)})

            for payload in (attempt_result, results["attempts"][0]):
                assert payload["status"] == "succeeded"
                assert payload["result"]["status"] == "succeeded"
                assert payload["result"]["terminal_status"] == "succeeded"
                assert payload["result"]["summary"]["metrics"]["rank_ic"] == 0.031
                assert payload["result"]["summary"]["metrics"]["rank_icir"] == 0.42
                assert payload["result"]["summary"]["metrics"]["composite_sharpe"] == 1.7
                assert payload["result"]["summary"]["fish"]["level"] == "A"
                assert payload["result"]["artifact"]["status"] == "available"
                assert payload["result"]["jobs"][0]["status"] == "done"
                assert payload["result"]["jobs"][0]["position_mode"] == "cs_only"

            rendered = json.dumps(results, sort_keys=True)
            assert "job-secret" not in rendered
            assert "plugin-secret" not in rendered
            assert "session-secret" not in rendered
            assert str(home) not in rendered
    finally:
        mcp_server.ApiClient = original_client


def main() -> int:
    test_tools_and_existing_schema()
    test_status_without_config_returns_setup_required()
    test_public_task_batch_start_requires_task_id_helpfully()
    test_batch_skill_public_task_flow_lists_tasks_before_start()
    test_batch_start_normalizes_backend_cs_only_output_to_submission_default()
    test_batch_isolation_and_sanitization()
    test_batch_upload_network_failure_blocks_without_failed_attempt_or_advancing()
    test_batch_attempts_preserve_single_run_result_summary()
    print("batch MCP validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
