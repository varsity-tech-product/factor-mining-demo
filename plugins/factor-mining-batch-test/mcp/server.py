#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from urllib.parse import parse_qs, urlsplit


MCP_ROOT = Path(__file__).resolve().parent
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

from factor_mining_agent_lib.api import AgentStatusError, ApiClient, ApiError
from factor_mining_agent_lib.batch import (
    BatchError,
    batch_results,
    batch_status,
    cancel_batch,
    create_batch,
    mark_attempt_system_error,
    next_attempt_packet,
    prepare_attempt_upload,
    record_attempt_error,
    record_attempt_result,
)
from factor_mining_agent_lib.browser_setup import _setup_page, _success_page
from factor_mining_agent_lib.config import (
    AgentConfig,
    ConfigError,
    DEFAULT_BASE_URL,
    HOME_ENV,
    config_path,
    load_config,
    save_config,
)
from factor_mining_agent_lib.metadata import MetadataError, parse_plugin_metadata
from factor_mining_agent_lib.redaction import redact_text
from factor_mining_agent_lib.run_state import RunState, load_run_state, save_run_state
from factor_mining_agent_lib.workflow import is_workflow_terminal, summarize_factor_card, terminal_outcome


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "fmbt"
SERVER_VERSION = "0.2.4"
MISSING_CREDENTIAL_MESSAGE = (
    "Factor Mining Batch Test setup is required. Call factor_mining_batch_test_setup_browser and enter the vt_ Agent API Key "
    "in the local browser page, not in chat."
)
TASK_PAYLOAD_REQUIRED_FIELDS = {
    "task_id",
    "title",
    "category",
    "description",
    "allowed_data",
    "fwd_period",
}


class McpServerError(RuntimeError):
    pass


class MissingCredentialError(McpServerError):
    pass


class ToolInputError(McpServerError):
    pass


class SetupBrowserServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], *, token: str, base_url: str, home: str | None):
        super().__init__(server_address, SetupBrowserHandler)
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.home = home
        self.done = threading.Event()
        self.result: dict[str, Any] = {"configured": False}


class SetupBrowserHandler(BaseHTTPRequestHandler):
    server: SetupBrowserServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if not self._is_setup_path():
            self._send_text(404, "Not found")
            return
        self._send_html(200, _setup_page(error=None))

    def do_POST(self) -> None:
        if not self._is_setup_path():
            self._send_text(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._send_html(400, _setup_page(error="Enter a Factor Mining Agent API Key."))
            return
        if length > 8192:
            self._send_html(413, _setup_page(error="The submitted value is too large."))
            return

        payload = self.rfile.read(length).decode("utf-8", errors="replace")
        fields = parse_qs(payload, keep_blank_values=True)
        key = (fields.get("api_key") or [""])[0].strip()
        if not key:
            self._send_html(400, _setup_page(error="Enter a Factor Mining Agent API Key."))
            return

        try:
            client = ApiClient(self.server.base_url, key)
            health = client.health()
            status = dict(client.agent_status())
            status["health"] = health
            save_config(
                AgentConfig(base_url=self.server.base_url, api_key=key, agent_status=status),
                home=self.server.home,
            )
        except Exception as exc:
            message = redact_text(str(exc), extra_secrets=[key])
            self.server.result = {"configured": False, "error": message}
            self._send_html(400, _setup_page(error=message))
            return

        self.server.result = {
            "configured": True,
            "base_url": self.server.base_url,
            "agent_status": _redact_payload(status),
        }
        self.server.done.set()
        self._send_html(200, _success_page())
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _is_setup_path(self) -> bool:
        return urlsplit(self.path).path == f"/{self.server.token}"

    def _send_text(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(encoded)


PENDING_SETUP: dict[str, dict[str, Any]] = {}


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "factor_mining_batch_test_status",
        "description": "Validate the local direct vt_ Factor Mining Agent API Key configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {"home": {"type": "string"}, "live_check": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_setup_browser",
        "description": "Open or return a local 127.0.0.1 setup page for secure vt_ Agent API Key entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_url": {"type": "string"},
                "open_browser": {"type": "boolean"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_list_public_tasks",
        "description": "List open public Factor Mining tasks through direct Agent API Key authentication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "status": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_create_task_session",
        "description": "Create a task-backed Factor Mining session from a published task id.",
        "inputSchema": {
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string"},
                "client_run_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_create_custom_session",
        "description": "Create a task-backed session from a custom factor idea and explicit task payload.",
        "inputSchema": {
            "type": "object",
            "required": ["idea", "task_payload"],
            "properties": {
                "idea": {"type": "string"},
                "task_payload": {"type": "object"},
                "client_run_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_parse_plugin_metadata",
        "description": "Parse plugin.py metadata statically without importing or executing generated code.",
        "inputSchema": {
            "type": "object",
            "required": ["plugin_path"],
            "properties": {"plugin_path": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_request_dedup_context",
        "description": "Request similar-factor context for a draft description and formula.",
        "inputSchema": {
            "type": "object",
            "required": ["session_id", "description", "formula"],
            "properties": {
                "session_id": {"type": "string"},
                "description": {"type": "string"},
                "formula": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_upload_backtest_wait",
        "description": "Parse metadata, upload plugin.py, submit a backtest, wait for terminal state, and fetch the default factor card.",
        "inputSchema": {
            "type": "object",
            "required": ["session_id", "plugin_path"],
            "properties": {
                "session_id": {"type": "string"},
                "plugin_path": {"type": "string"},
                "client_run_id": {"type": "string"},
                "parent_client_run_id": {"type": "string"},
                "position_mode": {"type": "string"},
                "fwd_period": {"type": "integer"},
                "decision_summary": {"type": "string"},
                "wait": {"type": "boolean"},
                "poll_interval": {"type": "number"},
                "timeout": {"type": "number"},
                "artifact_name": {"type": "string"},
                "output_dir": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_resume_run",
        "description": "Resume a persisted Factor Mining Batch Test run by client_run_id, optionally waiting for terminal result.",
        "inputSchema": {
            "type": "object",
            "required": ["client_run_id"],
            "properties": {
                "client_run_id": {"type": "string"},
                "wait": {"type": "boolean"},
                "poll_interval": {"type": "number"},
                "timeout": {"type": "number"},
                "artifact_name": {"type": "string"},
                "output_dir": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_get_workflow",
        "description": "Fetch Factor Mining workflow state for a session.",
        "inputSchema": {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_get_job",
        "description": "Fetch Factor Mining job state.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_get_artifact",
        "description": "Fetch a Factor Mining job artifact such as the default factor card.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string"},
                "name": {"type": "string"},
                "output_dir": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_start",
        "description": "Start a serial Factor Mining batch with isolated local attempt state.",
        "inputSchema": {
            "type": "object",
            "required": ["count", "mode"],
            "properties": {
                "count": {"type": "integer", "minimum": 1, "maximum": 50},
                "mode": {"type": "string", "enum": ["public_task", "custom_idea"]},
                "task_id": {"type": "string"},
                "idea": {"type": "string"},
                "task_payload": {"type": "object"},
                "fwd_period": {"type": "integer"},
                "position_mode": {"type": "string"},
                "diversity_goal": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_next",
        "description": "Return the next isolated attempt packet for a serial Factor Mining batch.",
        "inputSchema": {
            "type": "object",
            "required": ["batch_id"],
            "properties": {
                "batch_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_upload_backtest_wait",
        "description": "Submit the current batch attempt plugin.py through the guarded serial batch workflow.",
        "inputSchema": {
            "type": "object",
            "required": ["batch_id", "attempt_id", "session_id", "plugin_path"],
            "properties": {
                "batch_id": {"type": "string"},
                "attempt_id": {"type": "string"},
                "session_id": {"type": "string"},
                "plugin_path": {"type": "string"},
                "poll_interval": {"type": "number"},
                "timeout": {"type": "number"},
                "artifact_name": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_status",
        "description": "Return sanitized local status counts for a serial Factor Mining batch.",
        "inputSchema": {
            "type": "object",
            "required": ["batch_id"],
            "properties": {
                "batch_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_results",
        "description": "Return a sanitized final summary for a serial Factor Mining batch.",
        "inputSchema": {
            "type": "object",
            "required": ["batch_id"],
            "properties": {
                "batch_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_batch_cancel",
        "description": "Mark pending and active local attempts in a serial Factor Mining batch as cancelled.",
        "inputSchema": {
            "type": "object",
            "required": ["batch_id"],
            "properties": {
                "batch_id": {"type": "string"},
                "home": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_batch_test_clear_config",
        "description": "Remove the local direct vt_ Agent API Key configuration so the user can switch keys.",
        "inputSchema": {
            "type": "object",
            "properties": {"home": {"type": "string"}},
            "additionalProperties": False,
        },
    },
)


def list_tool_names() -> list[str]:
    return [tool["name"] for tool in TOOL_DEFINITIONS]


def call_tool(name: str, arguments: Mapping[str, Any] | None = None, *, opener: Any = None, env: Mapping[str, str] | None = None) -> Any:
    args = dict(arguments or {})
    if name == "factor_mining_batch_test_status":
        return _status(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_setup_browser":
        return _setup_browser(args, env=env)
    if name == "factor_mining_batch_test_list_public_tasks":
        return _list_public_tasks(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_create_task_session":
        return _create_task_session(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_create_custom_session":
        return _create_custom_session(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_parse_plugin_metadata":
        return _parse_plugin_metadata(args)
    if name == "factor_mining_batch_test_request_dedup_context":
        return _request_dedup_context(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_upload_backtest_wait":
        return _upload_backtest_wait(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_resume_run":
        return _resume_run(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_get_workflow":
        return _get_workflow(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_get_job":
        return _get_job(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_get_artifact":
        return _get_artifact(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_batch_start":
        return _batch_start(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_batch_next":
        return _batch_next(args, env=env)
    if name == "factor_mining_batch_test_batch_upload_backtest_wait":
        return _batch_upload_backtest_wait(args, opener=opener, env=env)
    if name == "factor_mining_batch_test_batch_status":
        return _batch_status(args, env=env)
    if name == "factor_mining_batch_test_batch_results":
        return _batch_results(args, env=env)
    if name == "factor_mining_batch_test_batch_cancel":
        return _batch_cancel(args, env=env)
    if name == "factor_mining_batch_test_clear_config":
        return _clear_config(args, env=env)
    raise ToolInputError(f"Unknown Factor Mining Batch Test MCP tool: {name}")


def _status(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> dict[str, Any]:
    home = _configured_home(args, env)
    try:
        config = load_config(home=home)
    except ConfigError as exc:
        return {
            "ok": True,
            "configured": False,
            "setup_required": True,
            "message": MISSING_CREDENTIAL_MESSAGE,
            "detail": redact_text(str(exc)),
        }

    result: dict[str, Any] = {
        "ok": True,
        "configured": True,
        "setup_required": False,
        "base_url": config.base_url,
    }
    try:
        client = ApiClient(config.base_url, config.api_key, opener=opener)
        health = client.health()
        agent_status = client.agent_status()
        result["health"] = _redact_payload(health)
        result["agent_status"] = _redact_payload(agent_status)
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "setup_required": True,
            "base_url": config.base_url,
            "error": redact_text(str(exc), extra_secrets=[config.api_key]),
        }
    return result


def _setup_browser(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> dict[str, Any]:
    base_url = str(args.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    home = _configured_home(args, env)
    token = secrets.token_urlsafe(24)
    handle = f"setup-{uuid.uuid4().hex}"
    server = SetupBrowserServer(("127.0.0.1", 0), token=token, base_url=base_url, home=home)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    setup_url = f"http://{host}:{port}/{token}"
    PENDING_SETUP[handle] = {"server": server, "thread": thread, "url": setup_url, "started_at": time.time()}

    opened = False
    if args.get("open_browser", True) is not False:
        try:
            opened = bool(webbrowser.open(setup_url))
        except Exception:
            opened = False

    return {
        "ok": True,
        "configured": False,
        "setup_required": True,
        "setup_handle": handle,
        "setup_url": setup_url,
        "opened_browser": opened,
        "base_url": base_url,
        "message": "Enter the Factor Mining Agent API Key in the local browser page, then call factor_mining_batch_test_status.",
    }


def _clear_config(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> dict[str, Any]:
    path = config_path(_configured_home(args, env))
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise McpServerError(f"Could not remove local Factor Mining Batch Test key config: {exc}") from exc
    return {
        "ok": True,
        "configured": False,
        "setup_required": True,
        "message": "Local Factor Mining Batch Test key config was removed.",
    }


def _list_public_tasks(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    limit = int(args.get("limit") or 20)
    status = args.get("status") if args.get("status") is not None else "open"
    return _redact_payload(client.list_tasks(limit=limit, status=str(status) if status else None))


def _create_task_session(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    task_id = _required_string(args, "task_id")
    client_run_id = _optional_string(args, "client_run_id")
    _config, client = _client_from_config(args, opener=opener, env=env)
    response = client.create_session(task_id=task_id, client_run_id=client_run_id)
    if client_run_id:
        save_run_state(
            RunState(client_run_id=client_run_id, session_id=_session_id(response)),
            home=_configured_home(args, env),
        )
    return _redact_payload(response)


def _create_custom_session(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    idea = _required_string(args, "idea")
    task_payload = args.get("task_payload")
    if not isinstance(task_payload, Mapping):
        raise ToolInputError("task_payload must be a JSON object")
    _validate_task_payload(task_payload)
    client_run_id = _optional_string(args, "client_run_id")
    _config, client = _client_from_config(args, opener=opener, env=env)
    response = client.create_session(
        idea=idea,
        task_payload=task_payload,
        client_run_id=client_run_id,
    )
    if client_run_id:
        save_run_state(
            RunState(client_run_id=client_run_id, session_id=_session_id(response)),
            home=_configured_home(args, env),
        )
    return _redact_payload(response)


def _parse_plugin_metadata(args: Mapping[str, Any]) -> dict[str, Any]:
    return parse_plugin_metadata(_required_string(args, "plugin_path")).to_dict()


def _request_dedup_context(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    return _redact_payload(
        client.dedup_context(
            session_id=_required_string(args, "session_id"),
            description=_required_string(args, "description"),
            formula=_required_string(args, "formula"),
            limit=int(args.get("limit") or 8),
        )
    )


def _upload_backtest_wait(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    home = _configured_home(args, env)
    session_id = _required_string(args, "session_id")
    plugin_path = Path(_required_string(args, "plugin_path"))
    client_run_id = _optional_string(args, "client_run_id") or f"fm-{uuid.uuid4().hex}"
    artifact_name = _optional_string(args, "artifact_name") or "default_factor_card.json"
    output_dir = _optional_string(args, "output_dir")
    if output_dir:
        _validate_artifact_name(artifact_name)

    metadata = parse_plugin_metadata(plugin_path)
    upload_response = client.upload_plugin(
        session_id=session_id,
        plugin_path=plugin_path,
        metadata=metadata,
        client_run_id=client_run_id,
        parent_client_run_id=_optional_string(args, "parent_client_run_id"),
        fwd_period=int(args.get("fwd_period") or 7),
        decision_summary=_optional_string(args, "decision_summary"),
    )
    plugin_id = _plugin_id(upload_response)
    if not plugin_id:
        raise McpServerError("Upload response did not include plugin_id")
    backtest_response = client.submit_backtest(
        session_id,
        plugin_id,
        position_mode=str(args.get("position_mode") or "both"),
        client_run_id=client_run_id,
    )
    state = RunState(
        client_run_id=client_run_id,
        session_id=session_id,
        plugin_id=plugin_id,
        job_ids=_job_ids(backtest_response),
        plugin_path=str(plugin_path),
        workflow_stage="submitted",
        artifact_paths={},
    )
    save_run_state(state, home=home)
    if args.get("wait", True) is False:
        return _redact_payload(
            {
                "client_run_id": client_run_id,
                "upload": upload_response,
                "backtest": backtest_response,
                "run_state": state.to_dict(),
            }
        )
    return _redact_payload(
        _run_wait_flow(
            client=client,
            state=state,
            artifact_name=artifact_name,
            output_dir=output_dir,
            poll_interval=float(args.get("poll_interval") or 10.0),
            timeout=float(args.get("timeout") or 900.0),
            home=home,
        )
    )


def _resume_run(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    home = _configured_home(args, env)
    state = load_run_state(_required_string(args, "client_run_id"), home=home)
    artifact_name = _optional_string(args, "artifact_name") or "default_factor_card.json"
    output_dir = _optional_string(args, "output_dir")
    if output_dir:
        _validate_artifact_name(artifact_name)
    if args.get("wait") is True:
        return _redact_payload(
            _run_wait_flow(
                client=client,
                state=state,
                artifact_name=artifact_name,
                output_dir=output_dir,
                poll_interval=float(args.get("poll_interval") or 10.0),
                timeout=float(args.get("timeout") or 900.0),
                home=home,
            )
        )

    workflow = client.workflow(state.session_id) if state.session_id else None
    jobs = [client.job(job_id) for job_id in state.job_ids]
    card, artifact = _fetch_optional_artifact(client, state.job_ids, artifact_name, output_dir)
    summary = summarize_factor_card(card or {}, jobs=jobs)
    if artifact["status"] == "unavailable":
        summary["artifact_status"] = "unavailable"
        if artifact.get("errors"):
            summary["artifact_errors"] = artifact["errors"]
    outcome = (
        terminal_outcome(workflow or {}, jobs)
        if is_workflow_terminal(workflow or {}, jobs)
        else {"ok": False, "status": "running", "terminal_status": None}
    )
    result = {
        **outcome,
        "run_state": state.to_dict(),
        "workflow": workflow,
        "jobs": jobs,
        "artifact": artifact,
        "summary": summary,
    }
    return _redact_payload(result)


def _get_workflow(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    return _redact_payload(client.workflow(_required_string(args, "session_id")))


def _get_job(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    return _redact_payload(client.job(_required_string(args, "job_id")))


def _get_artifact(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    _config, client = _client_from_config(args, opener=opener, env=env)
    name = _optional_string(args, "name") or "default_factor_card.json"
    output_dir = _optional_string(args, "output_dir")
    if output_dir:
        _validate_artifact_name(name)
    artifact = client.artifact(_required_string(args, "job_id"), name)
    saved_path = _save_json_artifact(output_dir, name, artifact)
    result: dict[str, Any] = {"name": name, "status": "available", "artifact": artifact}
    if saved_path:
        result["path"] = saved_path
    return _redact_payload(result)


def _batch_start(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    if "count" not in args:
        raise ToolInputError("count is required")
    task_payload = args.get("task_payload")
    if task_payload is not None and not isinstance(task_payload, Mapping):
        raise ToolInputError("task_payload must be a JSON object")
    _client_from_config(args, opener=opener, env=env)
    return create_batch(
        count=args["count"],
        mode=_required_string(args, "mode"),
        task_id=_optional_string(args, "task_id"),
        idea=_optional_string(args, "idea"),
        task_payload=task_payload,
        fwd_period=int(args.get("fwd_period") or 7),
        position_mode=str(args.get("position_mode") or "both"),
        diversity_goal=_optional_string(args, "diversity_goal"),
        home=_configured_home(args, env),
    )


def _batch_next(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> Any:
    return next_attempt_packet(_required_string(args, "batch_id"), home=_configured_home(args, env))


def _batch_upload_backtest_wait(args: Mapping[str, Any], *, opener: Any, env: Mapping[str, str] | None) -> Any:
    home = _configured_home(args, env)
    batch_id = _required_string(args, "batch_id")
    attempt_id = _required_string(args, "attempt_id")
    session_id = _required_string(args, "session_id")
    artifact_name = _optional_string(args, "artifact_name") or "default_factor_card.json"
    _validate_artifact_name(artifact_name)

    metadata_dict: dict[str, Any] = {}
    try:
        prepared = prepare_attempt_upload(
            batch_id=batch_id,
            attempt_id=attempt_id,
            session_id=session_id,
            plugin_path=_required_string(args, "plugin_path"),
            home=home,
        )
        metadata = parse_plugin_metadata(prepared.plugin_path)
        metadata_dict = metadata.to_dict()
        result = _upload_backtest_wait(
            {
                "session_id": session_id,
                "plugin_path": str(prepared.plugin_path),
                "client_run_id": prepared.client_run_id,
                "position_mode": prepared.position_mode,
                "fwd_period": prepared.fwd_period,
                "wait": True,
                "poll_interval": args.get("poll_interval"),
                "timeout": args.get("timeout"),
                "artifact_name": artifact_name,
                "output_dir": str(prepared.output_dir),
                "home": home,
            },
            opener=opener,
            env=env,
        )
    except (BatchError, MetadataError) as exc:
        return record_attempt_error(
            batch_id=batch_id,
            attempt_id=attempt_id,
            error=redact_text(str(exc)),
            metadata=metadata_dict,
            home=home,
        )
    except (MissingCredentialError, ConfigError, AgentStatusError, ApiError, McpServerError) as exc:
        return mark_attempt_system_error(
            batch_id=batch_id,
            attempt_id=attempt_id,
            error=redact_text(str(exc)),
            home=home,
        )
    except Exception as exc:
        return mark_attempt_system_error(
            batch_id=batch_id,
            attempt_id=attempt_id,
            error=redact_text(str(exc)),
            home=home,
        )

    return record_attempt_result(
        batch_id=batch_id,
        attempt_id=attempt_id,
        result=result,
        metadata=metadata_dict,
        home=home,
    )


def _batch_status(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> Any:
    return batch_status(_required_string(args, "batch_id"), home=_configured_home(args, env))


def _batch_results(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> Any:
    return batch_results(_required_string(args, "batch_id"), home=_configured_home(args, env))


def _batch_cancel(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> Any:
    return cancel_batch(_required_string(args, "batch_id"), home=_configured_home(args, env))


def _client_from_config(
    args: Mapping[str, Any],
    *,
    opener: Any,
    env: Mapping[str, str] | None,
    verify_live: bool = True,
) -> tuple[AgentConfig, ApiClient]:
    try:
        config = load_config(home=_configured_home(args, env))
    except ConfigError as exc:
        raise MissingCredentialError(MISSING_CREDENTIAL_MESSAGE) from exc
    client = ApiClient(config.base_url, config.api_key, opener=opener)
    if verify_live:
        client.agent_status()
    return config, client


def _configured_home(args: Mapping[str, Any], env: Mapping[str, str] | None) -> str | None:
    if args.get("home"):
        return str(args["home"])
    active_env = env if env is not None else os.environ
    return active_env.get(HOME_ENV)


def _run_wait_flow(
    *,
    client: ApiClient,
    state: RunState,
    artifact_name: str,
    output_dir: str | None,
    poll_interval: float,
    timeout: float,
    home: str | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest_workflow: Any = None
    latest_jobs: list[dict[str, Any]] = []

    while True:
        latest_workflow = client.workflow(state.session_id) if state.session_id else {}
        latest_jobs = [client.job(job_id) for job_id in state.job_ids]
        stage = latest_workflow.get("stage") if isinstance(latest_workflow, dict) else None
        save_run_state(
            RunState(
                client_run_id=state.client_run_id,
                session_id=state.session_id,
                plugin_id=state.plugin_id,
                job_ids=state.job_ids,
                plugin_path=state.plugin_path,
                workflow_stage=stage,
                artifact_paths=state.artifact_paths,
            ),
            home=home,
        )
        if is_workflow_terminal(latest_workflow or {}, latest_jobs):
            break
        if time.monotonic() >= deadline:
            latest = {
                "workflow": _compact_workflow(latest_workflow),
                "jobs": [
                    {
                        "job_id": job.get("job_id") or job.get("id"),
                        "status": job.get("status"),
                        "position_mode": job.get("position_mode"),
                    }
                    for job in latest_jobs
                ],
            }
            raise McpServerError(
                "Backtest timed out before completion. "
                f"Use factor_mining_batch_test_resume_run with client_run_id {state.client_run_id}. "
                f"Latest state: {json.dumps(latest, separators=(',', ':'), sort_keys=True)}"
            )
        if poll_interval > 0:
            time.sleep(poll_interval)

    card, artifact = _fetch_optional_artifact(client, state.job_ids, artifact_name, output_dir)
    artifact_paths = dict(state.artifact_paths)
    if artifact.get("path"):
        artifact_paths[str(artifact_name)] = str(artifact["path"])
        save_run_state(
            RunState(
                client_run_id=state.client_run_id,
                session_id=state.session_id,
                plugin_id=state.plugin_id,
                job_ids=state.job_ids,
                plugin_path=state.plugin_path,
                workflow_stage=stage,
                artifact_paths=artifact_paths,
            ),
            home=home,
        )
    summary = summarize_factor_card(card or {}, jobs=latest_jobs)
    if isinstance(card, dict) and isinstance(card.get("fish"), dict):
        summary["fish"] = dict(card["fish"])
    if artifact["status"] == "unavailable":
        summary["artifact_status"] = "unavailable"
        if artifact.get("errors"):
            summary["artifact_errors"] = artifact["errors"]
    outcome = terminal_outcome(latest_workflow or {}, latest_jobs)
    return {
        **outcome,
        "client_run_id": state.client_run_id,
        "session_id": state.session_id,
        "plugin_id": state.plugin_id,
        "job_ids": state.job_ids,
        "workflow": _compact_workflow(latest_workflow),
        "jobs": latest_jobs,
        "artifact": artifact,
        "summary": summary,
    }


def _fetch_optional_artifact(
    client: ApiClient,
    job_ids: list[str],
    artifact_name: str,
    output_dir: str | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    if output_dir:
        _validate_artifact_name(artifact_name)
    errors = []
    for job_id in job_ids:
        try:
            card = client.artifact(job_id, artifact_name)
            artifact: dict[str, Any] = {
                "name": artifact_name,
                "job_id": job_id,
                "status": "available",
            }
            saved_path = _save_json_artifact(output_dir, artifact_name, card)
            if saved_path:
                artifact["path"] = saved_path
            return card, artifact
        except ApiError as exc:
            if exc.status not in (404, 410):
                raise
            errors.append(
                {
                    "job_id": job_id,
                    "name": artifact_name,
                    "status": exc.status,
                    "message": "Artifact is unavailable.",
                }
            )
    artifact = {"name": artifact_name, "status": "unavailable"}
    if errors:
        artifact["errors"] = errors
    return None, artifact


def _save_json_artifact(output_dir: str | None, name: str, payload: Any) -> str | None:
    if not output_dir:
        return None
    _validate_artifact_name(name)
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    artifact_path = path / name
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(artifact_path)


def _validate_artifact_name(name: str) -> None:
    if not name or name in {".", ".."}:
        raise ToolInputError("artifact name must be a single file name")
    path = Path(name)
    if path.is_absolute() or "/" in name or "\\" in name or ".." in path.parts:
        raise ToolInputError("artifact name must be a single file name")


def _validate_task_payload(payload: Mapping[str, Any]) -> None:
    missing = sorted(field for field in TASK_PAYLOAD_REQUIRED_FIELDS if field not in payload)
    allowed_data = payload.get("allowed_data")
    if not isinstance(allowed_data, list) or not all(str(item).strip() for item in allowed_data):
        missing.append("allowed_data")
    if missing:
        fields = ", ".join(dict.fromkeys(missing))
        raise ToolInputError(f"task_payload is missing required fields: {fields}")


def _compact_workflow(workflow: Any) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        return {}
    return {
        key: workflow.get(key)
        for key in ("stage", "status", "stage_label", "next_action", "progress")
        if key in workflow
    }


def _job_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("job_ids"), list):
        return [str(job_id) for job_id in payload["job_ids"]]
    jobs = payload.get("jobs")
    if isinstance(jobs, list):
        ids = []
        for job in jobs:
            if isinstance(job, dict) and job.get("job_id"):
                ids.append(str(job["job_id"]))
            elif isinstance(job, str):
                ids.append(job)
        return ids
    if payload.get("job_id"):
        return [str(payload["job_id"])]
    return []


def _session_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("session_id", "id"):
            if payload.get(key):
                return str(payload[key])
    return None


def _plugin_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("plugin_id", "id"):
            if payload.get(key):
                return str(payload[key])
    return None


def _required_string(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} is required")
    return value.strip()


def _optional_string(args: Mapping[str, Any], key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} must be a non-empty string when provided")
    return value.strip()


def _redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.lower() in {"api_key", "authorization", "token", "credential", "secret", "password"}:
                continue
            redacted[key_str] = _redact_payload(item)
        return redacted
    return value


def handle_request(message: Mapping[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "tools/list":
            result = {"tools": list(TOOL_DEFINITIONS)}
        elif method == "tools/call":
            params = message.get("params") if isinstance(message.get("params"), Mapping) else {}
            tool_name = params.get("name")
            if not isinstance(tool_name, str):
                raise ToolInputError("tools/call requires params.name")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), Mapping) else {}
            result = _mcp_tool_result(call_tool(tool_name, arguments))
        elif method == "ping":
            result = {}
        else:
            raise ToolInputError(f"Unsupported MCP method: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        if method == "tools/call":
            return {"jsonrpc": "2.0", "id": request_id, "result": _mcp_tool_error(exc)}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": redact_text(str(exc))},
        }


def _mcp_tool_result(payload: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(_redact_payload(payload), separators=(",", ":"), sort_keys=True),
            }
        ]
    }


def _mcp_tool_error(exc: Exception) -> dict[str, Any]:
    return {
        "isError": True,
        "content": [
            {
                "type": "text",
                "text": json.dumps({"ok": False, "error": redact_text(str(exc))}, separators=(",", ":"), sort_keys=True),
            }
        ],
    }


def read_message(stream: BinaryIO) -> tuple[dict[str, Any], str] | None:
    first = stream.readline()
    if not first:
        return None
    if first.lstrip().startswith(b"{"):
        return json.loads(first.decode("utf-8")), "json-line"

    headers = [first]
    while True:
        line = stream.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        if not line:
            return None
        headers.append(line)
    length: int | None = None
    for header in headers:
        name, sep, value = header.partition(b":")
        if sep and name.strip().lower() == b"content-length":
            length = int(value.strip())
            break
    if length is not None:
        raw = stream.read(length)
        return json.loads(raw.decode("utf-8")), "content-length"
    raise ValueError("MCP message missing Content-Length header")


def write_message(stream: BinaryIO, message: Mapping[str, Any], framing: str) -> None:
    body = json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if framing == "content-length":
        stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    else:
        stream.write(body + b"\n")
    stream.flush()


def run_stdio() -> int:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        incoming = read_message(stdin)
        if incoming is None:
            return 0
        message, framing = incoming
        response = handle_request(message)
        if response is not None:
            write_message(stdout, response, framing)


if __name__ == "__main__":
    raise SystemExit(run_stdio())
