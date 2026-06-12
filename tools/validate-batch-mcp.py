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
from factor_mining_agent_lib.run_state import RunState


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
    created_sessions: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def agent_status(self) -> dict[str, str]:
        return {"status": "ok", "agent_key": "valid"}

    def create_session(
        self,
        *,
        idea: str | None = None,
        task_id: str | None = None,
        task_payload: dict[str, Any] | None = None,
        client_run_id: str | None = None,
    ) -> dict[str, str]:
        session = {
            "idea": idea,
            "task_id": task_id,
            "task_payload": dict(task_payload or {}),
            "client_run_id": client_run_id,
            "session_id": f"session-auto-{len(self.created_sessions) + 1}",
        }
        self.created_sessions.append(session)
        return {"session_id": session["session_id"]}


class NetworkFailingApiClient(FakeApiClient):
    def upload_plugin(self, **kwargs: Any) -> dict[str, Any]:
        raise mcp_server.ApiError(
            "Factor Mining API request could not connect: validation network failure",
            method="POST",
            url="https://example.invalid/sessions/session-1/plugins/upload?token=secret",
            api_key=VALIDATION_KEY,
        )


class ArtifactApiClient(FakeApiClient):
    def workflow(self, session_id: str) -> dict[str, Any]:
        return {"stage": "done", "session_id": session_id}

    def job(self, job_id: str) -> dict[str, Any]:
        return {"job_id": job_id, "status": "done", "position_mode": "cs_only"}

    def artifact(self, job_id: str, name: str = "default_factor_card.json") -> Any:
        artifacts: dict[str, Any] = {
            "default_factor_card.json": {
                "factor_name": "Artifact Bundle Momentum",
                "metrics": {"rank_ic": 0.041, "rank_icir": 0.51, "composite_sharpe": 1.9},
                "fish": {"level": "S"},
            },
            "default_factor_card.txt": "Artifact Bundle Momentum\\nRankIC 0.041\\n",
            "default_group_return_plot.png": b"\\x89PNG\\r\\n\\x1a\\nGROUP",
            "default_cs_profile_4panel.png": b"\\x89PNG\\r\\n\\x1a\\nPROFILE",
            "default_cs_nav_curves.png": b"\\x89PNG\\r\\n\\x1a\\nNAV",
        }
        if name not in artifacts:
            raise mcp_server.ApiError("missing artifact", status=404)
        return artifacts[name]


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
    batch_upload_schema = _tool_schema("factor_mining_batch_test_batch_upload_backtest_wait")
    assert batch_upload_schema["required"] == ["batch_id", "attempt_id", "plugin_path"]
    assert "session_id" in batch_upload_schema["properties"]


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


def test_custom_task_payload_rejects_unknown_allowed_data_before_backend() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            invalid_payload = dict(TASK_PAYLOAD)
            invalid_payload["allowed_data"] = ["close", "not_a_known_column"]
            for tool_name, args in (
                (
                    "factor_mining_batch_test_create_custom_session",
                    {"idea": "bad custom session", "task_payload": invalid_payload, "home": str(home)},
                ),
                (
                    "factor_mining_batch_test_batch_start",
                    {
                        "count": 1,
                        "mode": "custom_idea",
                        "idea": "bad batch",
                        "task_payload": invalid_payload,
                        "home": str(home),
                    },
                ),
            ):
                try:
                    mcp_server.call_tool(tool_name, args)
                except Exception as exc:
                    message = str(exc)
                    assert "allowed_data" in message
                    assert "not_a_known_column" in message
                    assert "close" in message
                else:
                    raise AssertionError(f"{tool_name} accepted unknown allowed_data")
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
            assert "client_run_id" not in first
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


def test_batch_upload_auto_creates_backend_session_when_session_id_omitted_or_local() -> None:
    original_client = mcp_server.ApiClient
    original_upload = mcp_server._upload_backtest_wait
    mcp_server.ApiClient = FakeApiClient
    FakeApiClient.created_sessions = []
    captured_uploads: list[dict[str, Any]] = []

    def fake_upload(args: dict[str, Any], *, opener: Any, env: dict[str, str] | None) -> dict[str, Any]:
        captured_uploads.append(dict(args))
        return {
            "ok": True,
            "status": "succeeded",
            "terminal_status": "succeeded",
            "summary": {
                "factor_name": "Auto Session Momentum",
                "metrics": {"rank_ic": 0.03},
            },
        }

    mcp_server._upload_backtest_wait = fake_upload
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 1,
                    "mode": "custom_idea",
                    "idea": "Validate auto session creation.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            batch_id = start["batch_id"]
            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            state_before = _read_batch(home, batch_id)
            local_client_run_id = state_before["attempts"][0]["client_run_id"]
            _write_valid_plugin(first["plugin_path"])

            result = mcp_server.call_tool(
                "factor_mining_batch_test_batch_upload_backtest_wait",
                {
                    "batch_id": batch_id,
                    "attempt_id": first["attempt_id"],
                    "session_id": local_client_run_id,
                    "plugin_path": first["plugin_path"],
                    "home": str(home),
                },
            )
            assert result["ok"] is True
            assert FakeApiClient.created_sessions
            assert FakeApiClient.created_sessions[0]["client_run_id"] == local_client_run_id
            assert FakeApiClient.created_sessions[0]["idea"] == "Validate auto session creation."
            assert captured_uploads[0]["session_id"] == "session-auto-1"
            assert captured_uploads[0]["session_id"] != local_client_run_id
            state_after = _read_batch(home, batch_id)
            assert state_after["attempts"][0]["session_id"] == "session-auto-1"

            second_start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 1,
                    "mode": "custom_idea",
                    "idea": "Validate omitted session creation.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            second_batch_id = second_start["batch_id"]
            second = mcp_server.call_tool(
                "factor_mining_batch_test_batch_next",
                {"batch_id": second_batch_id, "home": str(home)},
            )
            _write_valid_plugin(second["plugin_path"])

            omitted_result = mcp_server.call_tool(
                "factor_mining_batch_test_batch_upload_backtest_wait",
                {
                    "batch_id": second_batch_id,
                    "attempt_id": second["attempt_id"],
                    "plugin_path": second["plugin_path"],
                    "home": str(home),
                },
            )
            assert omitted_result["ok"] is True
            assert FakeApiClient.created_sessions[1]["idea"] == "Validate omitted session creation."
            assert captured_uploads[1]["session_id"] == "session-auto-2"
            second_state = _read_batch(home, second_batch_id)
            assert second_state["attempts"][0]["session_id"] == "session-auto-2"
    finally:
        mcp_server.ApiClient = original_client
        mcp_server._upload_backtest_wait = original_upload


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
                "client_run_id": "private-client-run",
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


def test_run_wait_fetches_factor_card_and_default_backtest_images() -> None:
    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp) / "home"
        output_dir = Path(temp) / "artifacts"
        state = RunState(
            client_run_id="client-artifacts",
            session_id="session-artifacts",
            plugin_id="plugin-artifacts",
            job_ids=["job-artifacts"],
            plugin_path=str(Path(temp) / "plugin.py"),
        )
        result = mcp_server._run_wait_flow(
            client=ArtifactApiClient(),
            state=state,
            artifact_name="default_factor_card.json",
            output_dir=str(output_dir),
            poll_interval=0,
            timeout=1,
            home=str(home),
        )

        assert result["status"] == "succeeded"
        assert result["summary"]["metrics"]["rank_ic"] == 0.041
        assert result["factor_card"]["fish"]["level"] == "S"
        artifacts = result["artifacts"]
        assert artifacts["status"] == "available"
        assert {item["name"] for item in artifacts["images"]} == {
            "default_group_return_plot.png",
            "default_cs_profile_4panel.png",
            "default_cs_nav_curves.png",
        }
        for name in (
            "default_factor_card.json",
            "default_factor_card.txt",
            "default_group_return_plot.png",
            "default_cs_profile_4panel.png",
            "default_cs_nav_curves.png",
        ):
            assert (output_dir / name).exists(), name
        for name in (
            "default_group_return_plot.png",
            "default_cs_profile_4panel.png",
            "default_cs_nav_curves.png",
        ):
            assert f"![{name}](<{output_dir / name}>)" in result["display_markdown"]["images"]


def test_batch_results_include_factor_card_images_and_comparison_rows() -> None:
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
                    "idea": "Validate comparison rows.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            batch_id = start["batch_id"]
            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            result = {
                "ok": True,
                "status": "succeeded",
                "terminal_status": "succeeded",
                "factor_card": {
                    "factor_name": "Comparison Momentum",
                    "metrics": {"rank_ic": 0.052, "rank_icir": 0.62, "composite_sharpe": 2.1},
                    "fish": {"level": "S"},
                    "download_url": "https://example.invalid/card?X-Amz-Signature=secret",
                },
                "summary": {
                    "factor_name": "Comparison Momentum",
                    "metrics": {"rank_ic": 0.052, "rank_icir": 0.62, "composite_sharpe": 2.1},
                    "fish": {"level": "S"},
                },
                "artifact": {
                    "name": "default_factor_card.json",
                    "kind": "factor_card",
                    "status": "available",
                    "path": str(home / "secret" / "default_factor_card.json"),
                    "image_artifacts": [
                        {
                            "name": "default_group_return_plot.png",
                            "kind": "image",
                            "status": "available",
                            "path": str(home / "secret" / "default_group_return_plot.png"),
                        }
                    ],
                },
                "artifacts": {
                    "status": "available",
                    "images": [
                        {
                            "name": "default_group_return_plot.png",
                            "kind": "image",
                            "status": "available",
                            "path": str(home / "secret" / "default_group_return_plot.png"),
                        }
                    ],
                    "files": [
                        {
                            "name": "default_factor_card.json",
                            "kind": "factor_card",
                            "status": "available",
                            "path": str(home / "secret" / "default_factor_card.json"),
                        }
                    ],
                },
            }
            record_attempt_result(
                batch_id=batch_id,
                attempt_id=first["attempt_id"],
                result=result,
                metadata={"factor_name": "Comparison Momentum", "factor_type": "comparison_momentum"},
                home=home,
            )
            results = mcp_server.call_tool("factor_mining_batch_test_batch_results", {"batch_id": batch_id, "home": str(home)})
            attempt = results["attempts"][0]
            row = results["comparison_rows"][0]
            assert attempt["result"]["factor_card"]["fish"]["level"] == "S"
            assert attempt["result"]["artifact"]["image_artifacts"][0]["path"] == str(
                home / "secret" / "default_group_return_plot.png"
            )
            assert attempt["result"]["artifacts"]["images"][0]["name"] == "default_group_return_plot.png"
            assert attempt["result"]["artifacts"]["images"][0]["path"] == str(home / "secret" / "default_group_return_plot.png")
            expected_markdown = f"![default_group_return_plot.png](<{home / 'secret' / 'default_group_return_plot.png'}>)"
            assert expected_markdown in attempt["result"]["display_markdown"]["images"]
            assert row["factor_name"] == "Comparison Momentum"
            assert row["rank_ic"] == 0.052
            assert row["rank_icir"] == 0.62
            assert row["composite_sharpe"] == 2.1
            assert row["fish_level"] == "S"
            assert row["image_artifacts"] == ["default_group_return_plot.png"]
            assert expected_markdown in row["display_markdown"]["images"]
            rendered = json.dumps(results, sort_keys=True)
            assert "X-Amz-Signature" not in rendered
            assert "plugin.py" not in rendered
    finally:
        mcp_server.ApiClient = original_client


def test_batch_results_mcp_response_embeds_images_and_single_run_image_paths() -> None:
    original_client = mcp_server.ApiClient
    mcp_server.ApiClient = FakeApiClient
    try:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            image_dir = home / "secret"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "default_group_return_plot.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nbatch-image")
            _save_validation_config(home)
            start = mcp_server.call_tool(
                "factor_mining_batch_test_batch_start",
                {
                    "count": 1,
                    "mode": "custom_idea",
                    "idea": "Validate GUI image rendering.",
                    "task_payload": TASK_PAYLOAD,
                    "home": str(home),
                },
            )
            batch_id = start["batch_id"]
            first = mcp_server.call_tool("factor_mining_batch_test_batch_next", {"batch_id": batch_id, "home": str(home)})
            record_attempt_result(
                batch_id=batch_id,
                attempt_id=first["attempt_id"],
                result={
                    "ok": True,
                    "status": "succeeded",
                    "terminal_status": "succeeded",
                    "summary": {"factor_name": "Renderable Momentum"},
                    "artifacts": {
                        "status": "available",
                        "images": [
                            {
                                "name": "default_group_return_plot.png",
                                "kind": "image",
                                "status": "available",
                                "path": str(image_path),
                            }
                        ],
                    },
                },
                metadata={"factor_name": "Renderable Momentum", "factor_type": "renderable_momentum"},
                home=home,
            )

            response = mcp_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "factor_mining_batch_test_batch_results",
                        "arguments": {"batch_id": batch_id, "home": str(home)},
                    },
                }
            )
            content = response["result"]["content"]
            text_blocks = [item for item in content if item.get("type") == "text"]
            image_blocks = [item for item in content if item.get("type") == "image"]
            assert image_blocks, content
            assert image_blocks[0]["mimeType"] == "image/png"
            assert image_blocks[0]["data"]
            rendered_text = "\n".join(block["text"] for block in text_blocks)
            assert str(image_path) in rendered_text
            assert f"![default_group_return_plot.png](<{image_path}>)" in rendered_text
            assert "default_group_return_plot.png" in rendered_text
    finally:
        mcp_server.ApiClient = original_client


def test_mcp_hidden_images_render_without_leaking_paths() -> None:
    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp)
        image_path = home / "default_cs_nav_curves.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nhidden-image")
        result = mcp_server._mcp_tool_result(
            {
                "ok": True,
                "image_artifacts": ["default_cs_nav_curves.png"],
                "_mcp_images": [
                    {
                        "name": "default_cs_nav_curves.png",
                        "kind": "image",
                        "status": "available",
                        "path": str(image_path),
                    }
                ],
            }
        )
        content = result["content"]
        text = "\n".join(item["text"] for item in content if item.get("type") == "text")
        images = [item for item in content if item.get("type") == "image"]
        assert images, content
        assert images[0]["mimeType"] == "image/png"
        assert images[0]["data"]
        assert str(home) not in text
        assert "_mcp_images" not in text
        assert "default_cs_nav_curves.png" in text


def main() -> int:
    test_tools_and_existing_schema()
    test_status_without_config_returns_setup_required()
    test_public_task_batch_start_requires_task_id_helpfully()
    test_batch_skill_public_task_flow_lists_tasks_before_start()
    test_batch_start_normalizes_backend_cs_only_output_to_submission_default()
    test_custom_task_payload_rejects_unknown_allowed_data_before_backend()
    test_batch_isolation_and_sanitization()
    test_batch_upload_auto_creates_backend_session_when_session_id_omitted_or_local()
    test_batch_upload_network_failure_blocks_without_failed_attempt_or_advancing()
    test_batch_attempts_preserve_single_run_result_summary()
    test_run_wait_fetches_factor_card_and_default_backtest_images()
    test_batch_results_include_factor_card_images_and_comparison_rows()
    test_batch_results_mcp_response_embeds_images_and_single_run_image_paths()
    test_mcp_hidden_images_render_without_leaking_paths()
    print("batch MCP validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
