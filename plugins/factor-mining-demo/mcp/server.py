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

from factor_mining_agent_lib.api import ApiClient, ApiError, ArtifactDownload
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
from factor_mining_agent_lib.metadata import parse_plugin_metadata
from factor_mining_agent_lib.redaction import redact_text
from factor_mining_agent_lib.run_state import RunState, load_run_state, save_run_state
from factor_mining_agent_lib.workflow import is_workflow_terminal, summarize_factor_card, terminal_outcome


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "factor-mining-demo"
SERVER_VERSION = "0.2.5"
MISSING_CREDENTIAL_MESSAGE = (
    "Factor Mining Demo setup is required. Call factor_mining_demo_setup_browser and enter the vt_ Agent API Key "
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
IMAGE_ARTIFACT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
DEFAULT_IMAGE_ARTIFACT_NAMES = (
    "default_cs_nav_curves.png",
    "default_cs_profile_4panel.png",
    "default_group_return_plot.png",
)


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
        "name": "factor_mining_demo_status",
        "description": "Validate the local direct vt_ Factor Mining Agent API Key configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {"home": {"type": "string"}, "live_check": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_demo_setup_browser",
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
        "name": "factor_mining_demo_list_public_tasks",
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
        "name": "factor_mining_demo_create_task_session",
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
        "name": "factor_mining_demo_create_custom_session",
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
        "name": "factor_mining_demo_parse_plugin_metadata",
        "description": "Parse plugin.py metadata statically without importing or executing generated code.",
        "inputSchema": {
            "type": "object",
            "required": ["plugin_path"],
            "properties": {"plugin_path": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "factor_mining_demo_request_dedup_context",
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
        "name": "factor_mining_demo_upload_backtest_wait",
        "description": "Parse metadata, upload plugin.py, submit a backtest, wait for terminal state, and save the default factor card plus image artifacts.",
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
        "name": "factor_mining_demo_resume_run",
        "description": "Resume a persisted Factor Mining Demo run by client_run_id, optionally waiting for terminal result.",
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
        "name": "factor_mining_demo_get_workflow",
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
        "name": "factor_mining_demo_get_job",
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
        "name": "factor_mining_demo_get_artifact",
        "description": "Fetch a Factor Mining job artifact such as the default factor card or a backtest image.",
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
        "name": "factor_mining_demo_clear_config",
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
    if name == "factor_mining_demo_status":
        return _status(args, opener=opener, env=env)
    if name == "factor_mining_demo_setup_browser":
        return _setup_browser(args, env=env)
    if name == "factor_mining_demo_list_public_tasks":
        return _list_public_tasks(args, opener=opener, env=env)
    if name == "factor_mining_demo_create_task_session":
        return _create_task_session(args, opener=opener, env=env)
    if name == "factor_mining_demo_create_custom_session":
        return _create_custom_session(args, opener=opener, env=env)
    if name == "factor_mining_demo_parse_plugin_metadata":
        return _parse_plugin_metadata(args)
    if name == "factor_mining_demo_request_dedup_context":
        return _request_dedup_context(args, opener=opener, env=env)
    if name == "factor_mining_demo_upload_backtest_wait":
        return _upload_backtest_wait(args, opener=opener, env=env)
    if name == "factor_mining_demo_resume_run":
        return _resume_run(args, opener=opener, env=env)
    if name == "factor_mining_demo_get_workflow":
        return _get_workflow(args, opener=opener, env=env)
    if name == "factor_mining_demo_get_job":
        return _get_job(args, opener=opener, env=env)
    if name == "factor_mining_demo_get_artifact":
        return _get_artifact(args, opener=opener, env=env)
    if name == "factor_mining_demo_clear_config":
        return _clear_config(args, env=env)
    raise ToolInputError(f"Unknown Factor Mining Demo MCP tool: {name}")


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
        "message": "Enter the Factor Mining Agent API Key in the local browser page, then call factor_mining_demo_status.",
    }


def _clear_config(args: Mapping[str, Any], *, env: Mapping[str, str] | None) -> dict[str, Any]:
    path = config_path(_configured_home(args, env))
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise McpServerError(f"Could not remove local Factor Mining Demo key config: {exc}") from exc
    return {
        "ok": True,
        "configured": False,
        "setup_required": True,
        "message": "Local Factor Mining Demo key config was removed.",
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
    output_dir = _default_output_dir(_optional_string(args, "output_dir"), plugin_path=plugin_path)
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
    output_dir = _default_output_dir(_optional_string(args, "output_dir"), state=state)
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
    download = client.artifact_download(_required_string(args, "job_id"), name)
    saved_path = _save_downloaded_artifact(output_dir, name, download)
    artifact = _artifact_value_for_mcp(download, name)
    result: dict[str, Any] = {
        "name": name,
        "status": "available",
        **_download_metadata(download),
    }
    if isinstance(artifact, bytes):
        result["binary"] = True
    else:
        result["artifact"] = artifact
    if saved_path:
        result["path"] = saved_path
    return _redact_payload(result)


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


def _default_output_dir(
    output_dir: str | None,
    *,
    plugin_path: Path | None = None,
    state: RunState | None = None,
) -> str | None:
    if output_dir:
        return output_dir
    source_path = plugin_path
    if source_path is None and state and state.plugin_path:
        source_path = Path(state.plugin_path)
    if source_path is None:
        return None
    return str(source_path.parent / "factor_mining_demo_artifacts")


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
                f"Use factor_mining_demo_resume_run with client_run_id {state.client_run_id}. "
                f"Latest state: {json.dumps(latest, separators=(',', ':'), sort_keys=True)}"
            )
        if poll_interval > 0:
            time.sleep(poll_interval)

    card, artifact = _fetch_optional_artifact(client, state.job_ids, artifact_name, output_dir)
    artifact_paths = dict(state.artifact_paths)
    for artifact_path_name, artifact_path in _artifact_paths_from_result(artifact).items():
        artifact_paths[artifact_path_name] = artifact_path
    if artifact_paths != state.artifact_paths:
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


def _artifact_paths_from_result(artifact: Mapping[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    if artifact.get("name") and artifact.get("path"):
        paths[str(artifact["name"])] = str(artifact["path"])
    for item in artifact.get("image_artifacts") or []:
        if isinstance(item, Mapping) and item.get("name") and item.get("path"):
            paths[str(item["name"])] = str(item["path"])
    return paths


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
            download = client.artifact_download(job_id, artifact_name)
            card = _artifact_value_for_mcp(download, artifact_name)
            artifact: dict[str, Any] = {
                "name": artifact_name,
                "job_id": job_id,
                "status": "available",
                **_download_metadata(download),
            }
            saved_path = _save_downloaded_artifact(output_dir, artifact_name, download)
            if saved_path:
                artifact["path"] = saved_path
            if isinstance(card, Mapping):
                image_artifacts, image_errors = _fetch_card_image_artifacts(client, job_id, card, output_dir)
                if image_artifacts:
                    artifact["image_artifacts"] = image_artifacts
                if image_errors:
                    artifact["image_errors"] = image_errors
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


def _fetch_card_image_artifacts(
    client: ApiClient,
    job_id: str,
    card: Mapping[str, Any],
    output_dir: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not output_dir:
        return [], []
    artifacts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for image_name in _candidate_image_artifact_names(card):
        try:
            download = client.artifact_download(job_id, image_name)
            saved_path = _save_downloaded_artifact(output_dir, image_name, download)
            item = {
                "name": image_name,
                "job_id": job_id,
                "status": "available",
                **_download_metadata(download),
            }
            if saved_path:
                item["path"] = saved_path
            artifacts.append(item)
        except ApiError as exc:
            errors.append(
                {
                    "job_id": job_id,
                    "name": image_name,
                    "status": exc.status,
                    "message": "Image artifact could not be saved.",
                    "detail": str(exc),
                }
            )
    return artifacts, errors


def _candidate_image_artifact_names(card: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for image_name in [*_extract_image_artifact_names(card), *DEFAULT_IMAGE_ARTIFACT_NAMES]:
        if image_name not in seen:
            seen.add(image_name)
            names.append(image_name)
    return names


def _extract_image_artifact_names(payload: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def consider(value: Any) -> None:
        if not isinstance(value, str):
            return
        parsed = urlsplit(value)
        candidate = Path(parsed.path).name if parsed.path else value.strip()
        if not candidate:
            return
        if Path(candidate).suffix.lower() not in IMAGE_ARTIFACT_EXTENSIONS:
            return
        try:
            _validate_artifact_name(candidate)
        except ToolInputError:
            return
        if candidate not in seen:
            seen.add(candidate)
            names.append(candidate)

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                consider(key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            consider(value)

    walk(payload)
    return names


def _download_metadata(download: ArtifactDownload) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "bytes": download.size,
        "sha256": download.sha256,
    }
    if download.content_type:
        metadata["content_type"] = download.content_type
    return metadata


def _artifact_value_for_mcp(download: ArtifactDownload, name: str) -> Any:
    try:
        return download.json_or_text(name)
    except UnicodeDecodeError:
        return download.body


def _save_downloaded_artifact(output_dir: str | None, name: str, download: ArtifactDownload) -> str | None:
    if not output_dir:
        return None
    _validate_artifact_name(name)
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    artifact_path = path / name
    artifact_path.write_bytes(download.body)
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
