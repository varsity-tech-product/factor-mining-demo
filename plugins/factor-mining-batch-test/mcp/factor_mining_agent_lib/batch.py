from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .api import normalize_submission_position_mode
from .config import ensure_agent_home
from .redaction import redact_text


BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ATTEMPT_ID_RE = re.compile(r"^[0-9]{3}$")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
ABSOLUTE_PATH_RE = re.compile(r"(?<!:)\/(?:[A-Za-z0-9._ -]+\/)+[A-Za-z0-9._ -]*")
TERMINAL_ATTEMPT_STATUSES = {"succeeded", "failed", "cancelled"}
BLOCKED_BATCH_STATUSES = {"blocked", "system_error"}
PUBLIC_DROP_KEYS = {
    "attempt_dir",
    "authorization",
    "client_run_id",
    "credential",
    "job_id",
    "job_ids",
    "local_path",
    "output_dir",
    "password",
    "plugin_id",
    "plugin_path",
    "presigned",
    "secret",
    "session_id",
    "source",
    "token",
    "url",
}
RANK_METRICS = (
    "sharpe",
    "sortino",
    "fitness",
    "score",
    "annualized_return",
    "annual_return",
    "total_return",
    "mean_return",
    "ic",
)
RESULT_TOP_LEVEL_KEYS = ("ok", "status", "terminal_status")
SUMMARY_TEXT_KEYS = ("factor_name", "factor_type", "artifact_status")
JOB_PUBLIC_KEYS = (
    "status",
    "position_mode",
    "progress",
    "failed_step",
    "failure_diagnostics",
    "requested_fwd_period",
    "actual_fwd_period",
    "error",
    "reason",
    "message",
)
ARTIFACT_PUBLIC_KEYS = ("status", "name", "kind", "content_type", "size_bytes", "sha256")
FAMILY_KEYWORDS = (
    ("mean_reversion", ("mean_reversion", "mean reversion", "reversal", "contrarian", "zscore", "z-score")),
    ("momentum", ("momentum", "trend", "breakout", "relative_strength")),
    ("volatility", ("volatility", "vol", "variance", "atr", "range")),
    ("volume", ("volume", "vwap", "flow", "turnover")),
    ("liquidity", ("liquidity", "spread", "depth", "slippage")),
    ("funding", ("funding", "carry", "basis")),
    ("open_interest", ("open_interest", "open interest", "oi")),
    ("seasonality", ("seasonality", "calendar", "weekday", "hour")),
    ("quality", ("quality", "stability", "efficiency")),
)


class BatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedAttempt:
    batch_id: str
    attempt_id: str
    client_run_id: str
    plugin_path: Path
    output_dir: Path
    fwd_period: int
    position_mode: str


def create_batch(
    *,
    count: int,
    mode: str,
    task_id: str | None = None,
    idea: str | None = None,
    task_payload: Mapping[str, Any] | None = None,
    fwd_period: int = 7,
    position_mode: str = "both",
    diversity_goal: str | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    count = _validate_count(count)
    mode = _validate_mode(mode)
    fwd_period = int(fwd_period or 7)
    try:
        position_mode = normalize_submission_position_mode(position_mode)
    except ValueError as exc:
        raise BatchError(str(exc)) from exc
    task_id = _clean_optional_string(task_id)
    idea = _clean_optional_string(idea)
    diversity_goal = _clean_optional_string(diversity_goal)

    if mode == "public_task" and not task_id:
        raise BatchError("task_id is required for public_task batch mode")
    if mode == "custom_idea" and not idea:
        raise BatchError("idea is required for custom_idea batch mode")
    if task_payload is not None and not isinstance(task_payload, Mapping):
        raise BatchError("task_payload must be a JSON object when provided")

    batch_id = f"batch-{uuid.uuid4().hex}"
    root = _batch_dir(batch_id, home=home, create=True)
    attempts_dir = root / "attempts"
    _ensure_private_dir(attempts_dir)

    now = _now()
    attempts: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        attempt_id = f"{index:03d}"
        attempt_dir = attempts_dir / attempt_id
        output_dir = attempt_dir / "artifacts"
        _ensure_private_dir(attempt_dir)
        _ensure_private_dir(output_dir)
        attempts.append(
            {
                "attempt_id": attempt_id,
                "index": index,
                "status": "pending",
                "client_run_id": f"fmb-{batch_id}-{attempt_id}",
                "attempt_dir": str(attempt_dir),
                "plugin_path": str(attempt_dir / "plugin.py"),
                "output_dir": str(output_dir),
                "started_at": None,
                "completed_at": None,
            }
        )

    state: dict[str, Any] = {
        "batch_id": batch_id,
        "created_at": now,
        "updated_at": now,
        "status": "pending",
        "count": count,
        "mode": mode,
        "fwd_period": fwd_period,
        "position_mode": position_mode,
        "current_attempt_index": None,
        "attempts": attempts,
    }
    if task_id:
        state["task_id"] = task_id
    if idea:
        state["idea"] = idea
    if task_payload is not None:
        state["task_payload"] = dict(task_payload)
    if diversity_goal:
        state["diversity_goal"] = diversity_goal

    save_batch_state(state, home=home)
    return {
        "ok": True,
        "batch_id": batch_id,
        "status": state["status"],
        "count": count,
        "mode": mode,
        "next_action": "Call factor_mining_batch_test_batch_next to start attempt 1.",
        "isolation": _isolation_statement(),
    }


def next_attempt_packet(batch_id: str, *, home: str | Path | None = None) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    if state.get("status") == "cancelled":
        return {
            "ok": True,
            "done": True,
            "batch_id": state["batch_id"],
            "status": "cancelled",
            "next_action": "Call factor_mining_batch_test_batch_results for the sanitized summary.",
        }

    active = _first_attempt_with_status(state, "active") or _first_attempt_with_status(state, "submitted")
    if active is None:
        active = _first_attempt_with_status(state, "pending")
        if active is not None:
            now = _now()
            active["status"] = "active"
            active["started_at"] = active.get("started_at") or now
            state["status"] = "running"
            state["current_attempt_index"] = active["index"]
            state["updated_at"] = now
            save_batch_state(state, home=home)

    if active is None:
        _refresh_batch_status(state)
        save_batch_state(state, home=home)
        return {
            "ok": True,
            "done": True,
            "batch_id": state["batch_id"],
            "status": state["status"],
            "next_action": "Call factor_mining_batch_test_batch_results for the sanitized summary.",
        }

    return _attempt_packet(state, active)


def prepare_attempt_upload(
    *,
    batch_id: str,
    attempt_id: str,
    session_id: str,
    plugin_path: str | Path,
    home: str | Path | None = None,
) -> PreparedAttempt:
    state = load_batch_state(batch_id, home=home)
    attempt = _find_attempt(state, attempt_id)
    if attempt.get("status") not in {"pending", "active"}:
        raise BatchError("attempt must be pending or active before upload")

    resolved_plugin = _resolve_current_plugin_path(attempt, plugin_path)
    output_dir = _resolve_output_dir(attempt)

    now = _now()
    _clear_system_error(state)
    attempt["status"] = "submitted"
    attempt["session_id"] = session_id
    attempt["started_at"] = attempt.get("started_at") or now
    state["status"] = "running"
    state["current_attempt_index"] = attempt["index"]
    state["updated_at"] = now
    save_batch_state(state, home=home)
    try:
        prepared_position_mode = normalize_submission_position_mode(state.get("position_mode"))
    except ValueError as exc:
        raise BatchError(str(exc)) from exc
    return PreparedAttempt(
        batch_id=state["batch_id"],
        attempt_id=str(attempt["attempt_id"]),
        client_run_id=str(attempt["client_run_id"]),
        plugin_path=resolved_plugin,
        output_dir=output_dir,
        fwd_period=int(state.get("fwd_period") or 7),
        position_mode=prepared_position_mode,
    )


def record_attempt_result(
    *,
    batch_id: str,
    attempt_id: str,
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
    home: str | Path | None = None,
) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    attempt = _find_attempt(state, attempt_id)
    _clear_system_error(state)
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    public_result = _public_result_summary(result, state=state)
    public_summary = public_result.get("summary") if isinstance(public_result.get("summary"), Mapping) else {}
    status = _attempt_status_from_result(result)
    metrics = public_summary.get("metrics") if isinstance(public_summary.get("metrics"), Mapping) else {}
    factor_name = _clean_optional_string(public_summary.get("factor_name")) or _clean_optional_string(
        summary.get("factor_name")
    ) or _clean_optional_string(metadata.get("factor_name"))
    factor_type = _clean_optional_string(metadata.get("factor_type"))
    family = _derive_factor_family(factor_type=factor_type, factor_name=factor_name)

    attempt.update(
        {
            "status": status,
            "factor_name": _sanitize_text(factor_name, state=state) if factor_name else None,
            "factor_type": _sanitize_text(factor_type, state=state) if factor_type else None,
            "factor_family": family,
            "formula_fingerprint": _fingerprint_metadata(metadata),
            "metrics": _sanitize_public_value(metrics, state=state),
            "result": public_result,
            "display_images": _private_display_images(result),
            "error": None,
            "completed_at": _now(),
        }
    )
    _refresh_batch_status(state)
    state["updated_at"] = _now()
    save_batch_state(state, home=home)
    return compact_attempt_result(state, attempt)


def record_attempt_error(
    *,
    batch_id: str,
    attempt_id: str,
    error: str,
    metadata: Mapping[str, Any] | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    attempt = _find_attempt(state, attempt_id)
    _clear_system_error(state)
    metadata = metadata or {}
    factor_name = _clean_optional_string(metadata.get("factor_name"))
    factor_type = _clean_optional_string(metadata.get("factor_type"))
    attempt.update(
        {
            "status": "failed",
            "factor_name": _sanitize_text(factor_name, state=state) if factor_name else attempt.get("factor_name"),
            "factor_type": _sanitize_text(factor_type, state=state) if factor_type else attempt.get("factor_type"),
            "factor_family": _derive_factor_family(factor_type=factor_type, factor_name=factor_name)
            or attempt.get("factor_family"),
            "formula_fingerprint": _fingerprint_metadata(metadata) if metadata else attempt.get("formula_fingerprint"),
            "metrics": _sanitize_public_value(attempt.get("metrics") or {}, state=state),
            "error": _sanitize_error(error, state=state),
            "completed_at": _now(),
        }
    )
    _refresh_batch_status(state)
    state["updated_at"] = _now()
    save_batch_state(state, home=home)
    return compact_attempt_result(state, attempt)


def mark_attempt_system_error(
    *,
    batch_id: str,
    attempt_id: str,
    error: str,
    home: str | Path | None = None,
) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    attempt = _find_attempt(state, attempt_id)
    sanitized = _sanitize_error(error, state=state)
    if attempt.get("status") in {"submitted", "blocked", "system_error"}:
        attempt["status"] = "active"
    elif attempt.get("status") == "pending":
        attempt["status"] = "active"
        attempt["started_at"] = attempt.get("started_at") or _now()
    attempt["system_error"] = sanitized
    attempt["completed_at"] = None
    state["status"] = "blocked"
    state["system_error"] = sanitized
    state["current_attempt_index"] = attempt.get("index")
    state["updated_at"] = _now()
    save_batch_state(state, home=home)
    return {
        "ok": False,
        "batch_id": state["batch_id"],
        "attempt_id": attempt["attempt_id"],
        "index": attempt.get("index"),
        "count": state.get("count"),
        "status": "blocked",
        "error": sanitized,
        "next_action": _blocked_next_action(state),
    }


def batch_status(batch_id: str, *, home: str | Path | None = None) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    _refresh_batch_status(state)
    save_batch_state(state, home=home)
    counts = _counts(state)
    active = _first_attempt_with_status(state, "active") or _first_attempt_with_status(state, "submitted")
    result: dict[str, Any] = {
        "ok": True,
        "batch_id": state["batch_id"],
        "status": state["status"],
        "count": state["count"],
        "counts": counts,
        "next_action": _next_action(state),
    }
    if active is not None:
        result["active_attempt"] = {"index": active["index"], "status": active["status"]}
    if state.get("system_error"):
        result["system_error"] = _sanitize_error(str(state["system_error"]), state=state)
    return result


def batch_results(batch_id: str, *, home: str | Path | None = None) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    _refresh_batch_status(state)
    save_batch_state(state, home=home)
    attempts = [_public_attempt_summary(state, attempt) for attempt in _ordered_attempts(state)]
    return {
        "ok": True,
        "batch_id": state["batch_id"],
        "status": state["status"],
        "count": state["count"],
        "mode": state["mode"],
        "fwd_period": state.get("fwd_period"),
        "position_mode": state.get("position_mode"),
        "counts": _counts(state),
        "attempts": attempts,
        "comparison_rows": _comparison_rows(attempts),
        "best_attempts": _best_attempts(attempts),
        "isolation": _isolation_statement(),
    }


def cancel_batch(batch_id: str, *, home: str | Path | None = None) -> dict[str, Any]:
    state = load_batch_state(batch_id, home=home)
    now = _now()
    for attempt in state.get("attempts") or []:
        if attempt.get("status") in {"pending", "active", "submitted"}:
            attempt["status"] = "cancelled"
            attempt["completed_at"] = now
    state["status"] = "cancelled"
    state["updated_at"] = now
    save_batch_state(state, home=home)
    return batch_status(batch_id, home=home)


def load_batch_state(batch_id: str, *, home: str | Path | None = None) -> dict[str, Any]:
    _validate_batch_id(batch_id)
    path = _batch_state_path(batch_id, home=home)
    if not path.exists():
        raise BatchError(f"No batch state found for batch_id {batch_id}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("batch_id") != batch_id:
        raise BatchError("batch state id does not match requested batch_id")
    return payload


def save_batch_state(state: Mapping[str, Any], *, home: str | Path | None = None) -> Path:
    batch_id = str(state.get("batch_id") or "")
    _validate_batch_id(batch_id)
    path = _batch_state_path(batch_id, home=home)
    _ensure_private_dir(path.parent)
    payload = _redact_state_value(dict(state))
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
    finally:
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    return path


def compact_attempt_result(state: Mapping[str, Any], attempt: Mapping[str, Any]) -> dict[str, Any]:
    result = _public_attempt_summary(state, attempt)
    result.update(
        {
            "ok": attempt.get("status") == "succeeded",
            "batch_id": state["batch_id"],
            "attempt_id": attempt["attempt_id"],
            "count": state["count"],
            "next_action": _next_action(state),
        }
    )
    return result


def _attempt_packet(state: Mapping[str, Any], attempt: Mapping[str, Any]) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "ok": True,
        "done": False,
        "batch_id": state["batch_id"],
        "attempt_id": attempt["attempt_id"],
        "index": attempt["index"],
        "count": state["count"],
        "plugin_path": attempt["plugin_path"],
        "output_dir": attempt["output_dir"],
        "mode": state["mode"],
        "fwd_period": state.get("fwd_period"),
        "position_mode": state.get("position_mode"),
        "diversity_hints": _diversity_hints(state),
        "next_action": (
            "Write only this attempt's plugin.py, then call "
            "factor_mining_batch_test_batch_upload_backtest_wait with batch_id, attempt_id, and plugin_path. "
            "Do not pass batch_id, attempt_id, or any local run id as session_id; omit session_id unless a "
            "backend session_id was returned by a create-session MCP tool."
        ),
    }
    if state.get("status") in BLOCKED_BATCH_STATUSES:
        packet["status"] = state.get("status")
        packet["system_error"] = _sanitize_error(str(state.get("system_error") or ""), state=state)
        packet["next_action"] = _blocked_next_action(state)
    if state["mode"] == "public_task":
        packet["task_id"] = state.get("task_id")
    else:
        packet["idea"] = state.get("idea")
        if state.get("task_payload") is not None:
            packet["task_payload"] = state.get("task_payload")
    return packet


def _public_attempt_summary(state: Mapping[str, Any], attempt: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "index": attempt.get("index"),
        "status": attempt.get("status"),
    }
    for key in ("factor_name", "factor_type", "factor_family"):
        if attempt.get(key):
            summary[key] = _sanitize_text(str(attempt[key]), state=state)
    metrics = _sanitize_public_value(attempt.get("metrics") or {}, state=state)
    if metrics:
        summary["metrics"] = metrics
    result = _sanitize_public_value(attempt.get("result") or {}, state=state)
    if result:
        summary["result"] = result
    if attempt.get("error"):
        summary["error"] = _sanitize_error(str(attempt["error"]), state=state)
    return summary


def _private_display_images(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return []
    images = artifacts.get("images")
    if not isinstance(images, list):
        return []
    private_images: list[dict[str, Any]] = []
    for image in images:
        if not isinstance(image, Mapping):
            continue
        name = image.get("name")
        path = image.get("path")
        if not isinstance(name, str) or not isinstance(path, str):
            continue
        item = {
            "name": name,
            "path": path,
            "kind": "image",
            "status": str(image.get("status") or "available"),
        }
        content_type = image.get("content_type")
        if isinstance(content_type, str):
            item["content_type"] = content_type
        private_images.append(item)
    return private_images


def _public_result_summary(result: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key in RESULT_TOP_LEVEL_KEYS:
        if key in result:
            value = _sanitize_public_value(result.get(key), state=state)
            if value not in (None, "", [], {}):
                public[key] = value

    summary = result.get("summary")
    if isinstance(summary, Mapping):
        public_summary = _public_factor_summary(summary, state=state)
        if public_summary:
            public["summary"] = public_summary

    jobs = result.get("jobs")
    if isinstance(jobs, list):
        public_jobs = [
            item
            for item in (_public_job_summary(job, state=state) for job in jobs if isinstance(job, Mapping))
            if item
        ]
        if public_jobs:
            public["jobs"] = public_jobs

    artifact = result.get("artifact")
    if isinstance(artifact, Mapping):
        public_artifact = _public_artifact_summary(artifact, state=state)
        if public_artifact:
            public["artifact"] = public_artifact

    factor_card = result.get("factor_card")
    if isinstance(factor_card, Mapping):
        public_factor_card = _sanitize_public_value(factor_card, state=state)
        if public_factor_card:
            public["factor_card"] = public_factor_card

    artifacts = result.get("artifacts")
    if isinstance(artifacts, Mapping):
        public_artifacts = _public_artifacts_summary(artifacts, state=state)
        if public_artifacts:
            public["artifacts"] = public_artifacts

    return public


def _public_factor_summary(summary: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key in SUMMARY_TEXT_KEYS:
        if summary.get(key):
            public[key] = _sanitize_text(str(summary[key]), state=state)

    metrics = _sanitize_public_value(summary.get("metrics") or {}, state=state)
    if metrics:
        public["metrics"] = metrics

    artifacts = _sanitize_public_value(summary.get("artifacts") or {}, state=state)
    if artifacts:
        public["artifacts"] = artifacts

    fish = _sanitize_public_value(summary.get("fish") or {}, state=state)
    if fish:
        public["fish"] = fish

    artifact_errors = _sanitize_public_value(summary.get("artifact_errors") or [], state=state)
    if artifact_errors:
        public["artifact_errors"] = artifact_errors

    jobs = summary.get("jobs")
    if isinstance(jobs, list):
        public_jobs = [
            item
            for item in (_public_job_summary(job, state=state) for job in jobs if isinstance(job, Mapping))
            if item
        ]
        if public_jobs:
            public["jobs"] = public_jobs

    failures = summary.get("failures")
    if isinstance(failures, list):
        public_failures = [
            item
            for item in (_public_job_summary(job, state=state) for job in failures if isinstance(job, Mapping))
            if item
        ]
        if public_failures:
            public["failures"] = public_failures

    return public


def _public_job_summary(job: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key in JOB_PUBLIC_KEYS:
        if key not in job:
            continue
        value = _sanitize_public_value(job.get(key), state=state)
        if value not in (None, "", [], {}):
            public[key] = value
    summary = job.get("summary")
    if isinstance(summary, Mapping):
        clean_summary = _sanitize_public_value(summary, state=state)
        if clean_summary:
            public["summary"] = clean_summary
    return public


def _public_artifact_summary(artifact: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key in ARTIFACT_PUBLIC_KEYS:
        if key not in artifact:
            continue
        value = _sanitize_public_value(artifact.get(key), state=state)
        if value not in (None, "", [], {}):
            public[key] = value
    if _is_public_image_artifact(artifact):
        path = artifact.get("path")
        if isinstance(path, str) and path:
            public["path"] = path
    image_artifacts = artifact.get("image_artifacts")
    if isinstance(image_artifacts, list):
        public_images = [
            item
            for item in (_public_artifact_summary(value, state=state) for value in image_artifacts if isinstance(value, Mapping))
            if item
        ]
        if public_images:
            public["image_artifacts"] = public_images
    return public


def _is_public_image_artifact(artifact: Mapping[str, Any]) -> bool:
    name = artifact.get("name")
    if artifact.get("kind") == "image":
        return True
    return isinstance(name, str) and name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"))


def _public_artifacts_summary(artifacts: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    if artifacts.get("status"):
        public["status"] = _sanitize_text(str(artifacts["status"]), state=state)
    for key in ("files", "images"):
        values = artifacts.get(key)
        if not isinstance(values, list):
            continue
        public_values = [
            item
            for item in (_public_artifact_summary(value, state=state) for value in values if isinstance(value, Mapping))
            if item
        ]
        if public_values:
            public[key] = public_values
    errors = _sanitize_public_value(artifacts.get("errors") or [], state=state)
    if errors:
        public["errors"] = errors
    return public


def _comparison_rows(attempts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_comparison_row(attempt) for attempt in attempts]


def _comparison_row(attempt: Mapping[str, Any]) -> dict[str, Any]:
    result = attempt.get("result") if isinstance(attempt.get("result"), Mapping) else {}
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else attempt.get("metrics") or {}
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), Mapping) else {}
    images = artifacts.get("images") if isinstance(artifacts.get("images"), list) else []
    fish = summary.get("fish") if isinstance(summary.get("fish"), Mapping) else {}
    artifact = result.get("artifact") if isinstance(result.get("artifact"), Mapping) else {}
    artifact_status = artifacts.get("status") or artifact.get("status")
    row: dict[str, Any] = {
        "index": attempt.get("index"),
        "status": attempt.get("status"),
        "factor_name": attempt.get("factor_name"),
        "factor_type": attempt.get("factor_type"),
        "factor_family": attempt.get("factor_family"),
        "artifact_status": artifact_status,
        "image_artifacts": [
            str(item["name"])
            for item in images
            if isinstance(item, Mapping) and item.get("status") == "available" and item.get("name")
        ],
    }
    for key in ("rank_ic", "rank_icir", "composite_sharpe", "sharpe", "annual_return", "annualized_return"):
        value = _metric_value(metrics, key)
        if value is not None:
            row[key] = value
    if fish.get("level"):
        row["fish_level"] = fish.get("level")
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _metric_value(metrics: Mapping[str, Any], key: str) -> Any:
    normalized = {_normalize_metric_key(name): value for name, value in metrics.items()}
    return normalized.get(_normalize_metric_key(key))


def _best_attempts(attempts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for attempt in attempts:
        metric = _rank_metric(attempt.get("metrics") if isinstance(attempt.get("metrics"), Mapping) else {})
        if metric is None:
            continue
        metric_name, metric_value = metric
        ranked.append(
            {
                "index": attempt.get("index"),
                "status": attempt.get("status"),
                "factor_name": attempt.get("factor_name"),
                "factor_type": attempt.get("factor_type"),
                "factor_family": attempt.get("factor_family"),
                "rank_metric": metric_name,
                "rank_value": metric_value,
            }
        )
    ranked.sort(key=lambda item: float(item["rank_value"]), reverse=True)
    return ranked[:3]


def _rank_metric(metrics: Mapping[str, Any]) -> tuple[str, float] | None:
    normalized = {_normalize_metric_key(key): value for key, value in metrics.items()}
    for name in RANK_METRICS:
        value = normalized.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return name, float(value)
    for key, value in normalized.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return key, float(value)
    return None


def _normalize_metric_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")


def _diversity_hints(state: Mapping[str, Any]) -> dict[str, Any]:
    families = sorted(
        {
            str(attempt.get("factor_family"))
            for attempt in state.get("attempts") or []
            if attempt.get("factor_family") and attempt.get("status") in TERMINAL_ATTEMPT_STATUSES
        }
    )
    hints: dict[str, Any] = {
        "avoid_factor_families": families[:8],
        "do_not_reuse_previous_attempt_details": True,
    }
    if state.get("diversity_goal"):
        hints["goal"] = _sanitize_text(str(state["diversity_goal"]), state=state)
    return hints


def _attempt_status_from_result(result: Mapping[str, Any]) -> str:
    status = str(result.get("status") or result.get("terminal_status") or "").lower()
    if status == "succeeded" and result.get("ok") is True:
        return "succeeded"
    if status in {"cancelled", "canceled"}:
        return "cancelled"
    if status == "succeeded":
        return "succeeded"
    return "failed"


def _fingerprint_metadata(metadata: Mapping[str, Any]) -> str | None:
    if not metadata:
        return None
    data = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def _derive_factor_family(*, factor_type: str | None, factor_name: str | None) -> str | None:
    text = f"{factor_type or ''} {factor_name or ''}".lower()
    for family, keywords in FAMILY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return family
    token = re.sub(r"[^a-z0-9_]+", "_", text).strip("_").split("_")[0]
    return token or None


def _sanitize_public_value(value: Any, *, state: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value, state=state)
    if isinstance(value, list):
        return [_sanitize_public_value(item, state=state) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_public_value(item, state=state) for item in value]
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            normalized_key = key_str.lower()
            if any(drop_key in normalized_key for drop_key in PUBLIC_DROP_KEYS):
                continue
            if key_str == "path" and _is_public_image_artifact(value) and isinstance(item, str):
                clean_item = item
            else:
                clean_item = _sanitize_public_value(item, state=state)
            if clean_item not in (None, "", [], {}):
                sanitized[key_str] = clean_item
        return sanitized
    return value


def _sanitize_error(error: str, *, state: Mapping[str, Any]) -> str:
    first_line = error.replace("\r", "\n").split("\n", 1)[0]
    return _sanitize_text(first_line[:500], state=state)


def _sanitize_text(text: str | None, *, state: Mapping[str, Any]) -> str:
    if not text:
        return ""
    redacted = redact_text(str(text))
    redacted = URL_RE.sub("[url]", redacted)
    for raw_path in _local_paths(state):
        if raw_path:
            redacted = redacted.replace(raw_path, "[local path]")
    redacted = ABSOLUTE_PATH_RE.sub("[local path]", redacted)
    return redacted


def _local_paths(state: Mapping[str, Any]) -> list[str]:
    paths = []
    for attempt in state.get("attempts") or []:
        for key in ("attempt_dir", "plugin_path", "output_dir"):
            if attempt.get(key):
                path = Path(str(attempt[key]))
                paths.append(str(path))
                paths.extend(str(parent) for parent in path.parents[:3])
    return sorted(set(paths), key=len, reverse=True)


def _redact_state_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_state_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_state_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _redact_state_value(item) for key, item in value.items()}
    return value


def _refresh_batch_status(state: dict[str, Any]) -> None:
    if state.get("status") == "cancelled":
        return
    if state.get("status") in BLOCKED_BATCH_STATUSES and state.get("system_error"):
        return
    attempts = list(state.get("attempts") or [])
    statuses = {str(attempt.get("status")) for attempt in attempts}
    if statuses & {"active", "submitted"}:
        state["status"] = "running"
    elif statuses == {"pending"} or not attempts:
        state["status"] = "pending"
    elif statuses <= {"succeeded"}:
        state["status"] = "succeeded"
    elif statuses <= TERMINAL_ATTEMPT_STATUSES:
        state["status"] = "failed" if "failed" in statuses else "cancelled"
    else:
        state["status"] = "running"


def _counts(state: Mapping[str, Any]) -> dict[str, int]:
    counts = {"pending": 0, "active": 0, "succeeded": 0, "failed": 0, "cancelled": 0}
    for attempt in state.get("attempts") or []:
        status = str(attempt.get("status") or "pending")
        if status == "submitted":
            counts["active"] += 1
        elif status in counts:
            counts[status] += 1
    return counts


def _next_action(state: Mapping[str, Any]) -> str:
    if state.get("status") == "cancelled":
        return "Call factor_mining_batch_test_batch_results for the sanitized summary."
    if state.get("status") in BLOCKED_BATCH_STATUSES and state.get("system_error"):
        return _blocked_next_action(state)
    if _first_attempt_with_status(state, "active") or _first_attempt_with_status(state, "submitted"):
        return "Complete the active attempt with factor_mining_batch_test_batch_upload_backtest_wait."
    if _first_attempt_with_status(state, "pending"):
        return "Call factor_mining_batch_test_batch_next for the next isolated attempt packet."
    return "Call factor_mining_batch_test_batch_results for the sanitized summary."


def _blocked_next_action(state: Mapping[str, Any]) -> str:
    return "Retry the current attempt after fixing setup, authentication, network, or backend availability."


def _clear_system_error(state: dict[str, Any]) -> None:
    state.pop("system_error", None)
    if state.get("status") in BLOCKED_BATCH_STATUSES:
        state["status"] = "running"
    for attempt in state.get("attempts") or []:
        if isinstance(attempt, dict):
            attempt.pop("system_error", None)


def _ordered_attempts(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted([dict(attempt) for attempt in state.get("attempts") or []], key=lambda item: int(item.get("index") or 0))


def _first_attempt_with_status(state: Mapping[str, Any], status: str) -> dict[str, Any] | None:
    for attempt in _ordered_attempts(state):
        if attempt.get("status") == status:
            original = _find_attempt(state, str(attempt["attempt_id"]))
            return original
    return None


def _find_attempt(state: Mapping[str, Any], attempt_id: str) -> dict[str, Any]:
    _validate_attempt_id(attempt_id)
    for attempt in state.get("attempts") or []:
        if attempt.get("attempt_id") == attempt_id:
            return attempt
    raise BatchError(f"No attempt {attempt_id} found for this batch")


def _resolve_current_plugin_path(attempt: Mapping[str, Any], plugin_path: str | Path) -> Path:
    path = Path(plugin_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BatchError(f"Cannot read current attempt plugin.py: {exc}") from exc

    attempt_dir = Path(str(attempt["attempt_dir"])).expanduser().resolve(strict=True)
    try:
        resolved.relative_to(attempt_dir)
    except ValueError as exc:
        raise BatchError("plugin_path must be inside the current attempt directory") from exc
    expected = attempt_dir / "plugin.py"
    if resolved != expected:
        raise BatchError("plugin_path must be the current attempt plugin.py")
    return resolved


def _resolve_output_dir(attempt: Mapping[str, Any]) -> Path:
    attempt_dir = Path(str(attempt["attempt_dir"])).expanduser().resolve(strict=True)
    output_dir = Path(str(attempt["output_dir"])).expanduser()
    resolved = output_dir.resolve(strict=False)
    expected = attempt_dir / "artifacts"
    try:
        resolved.relative_to(expected)
    except ValueError as exc:
        raise BatchError("output_dir must be inside the current attempt artifacts directory") from exc
    _ensure_private_dir(resolved)
    return resolved


def _batch_state_path(batch_id: str, *, home: str | Path | None = None) -> Path:
    return _batch_dir(batch_id, home=home, create=False) / "batch.json"


def _batch_dir(batch_id: str, *, home: str | Path | None = None, create: bool) -> Path:
    _validate_batch_id(batch_id)
    root = batches_dir(home=home)
    path = root / batch_id
    if create:
        _ensure_private_dir(path)
    return path


def batches_dir(*, home: str | Path | None = None) -> Path:
    root = ensure_agent_home(home)
    path = root / "batches"
    _ensure_private_dir(path)
    return path


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        pass


def _validate_count(count: int) -> int:
    if isinstance(count, bool):
        raise BatchError("count must be an integer from 1 to 50")
    count = int(count)
    if count < 1 or count > 50:
        raise BatchError("count must be an integer from 1 to 50")
    return count


def _validate_mode(mode: str) -> str:
    mode = str(mode or "").strip()
    if mode not in {"public_task", "custom_idea"}:
        raise BatchError("mode must be public_task or custom_idea")
    return mode


def _validate_batch_id(batch_id: str) -> None:
    if not BATCH_ID_RE.match(str(batch_id or "")):
        raise BatchError("batch_id may contain only letters, numbers, '.', '_', and '-'")


def _validate_attempt_id(attempt_id: str) -> None:
    if not ATTEMPT_ID_RE.match(str(attempt_id or "")):
        raise BatchError("attempt_id must be a three-digit attempt identifier")


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _isolation_statement() -> str:
    return (
        "Batch mode provides MCP state, file, and information-flow isolation between attempts; "
        "it does not guarantee host-level isolated model context."
    )
