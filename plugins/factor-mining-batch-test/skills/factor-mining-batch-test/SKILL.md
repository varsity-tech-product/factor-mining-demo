---
name: factor-mining-batch-test
description: "Use when an agent should run the direct vt_ Agent API Key Factor Mining flow through bundled MCP tools: create or submit a plugin.py, run a user-scoped backtest, wait for workflow and job results, fetch artifacts, summarize outcomes, or resume a run."
---

# Factor Mining Batch Test

Use this skill for the Factor Mining Batch Test product flow. The agent writes or
locates one local `plugin.py`. Factor Mining validates, stores, backtests, and
returns workflow, job, artifact, and factor result data through the bundled
Factor Mining Batch Test MCP tools.

If the MCP tools are unavailable, stop and tell the user the Factor Mining Batch Test
plugin tools are not loaded. Do not use raw HTTP calls or local script
execution as a fallback.

Some hosts display bundled MCP tool names with a provider prefix, such as
`fmbt__factor_mining_batch_test_status`. Treat those as the
same Factor Mining Batch Test MCP tools.

## MCP Workflow

Use these tools for product actions:

- `factor_mining_batch_test_status`
- `factor_mining_batch_test_setup_browser`
- `factor_mining_batch_test_list_public_tasks`
- `factor_mining_batch_test_create_task_session`
- `factor_mining_batch_test_create_custom_session`
- `factor_mining_batch_test_parse_plugin_metadata`
- `factor_mining_batch_test_request_dedup_context`
- `factor_mining_batch_test_upload_backtest_wait`
- `factor_mining_batch_test_resume_run`
- `factor_mining_batch_test_get_workflow`
- `factor_mining_batch_test_get_job`
- `factor_mining_batch_test_get_artifact`
- `factor_mining_batch_test_clear_config`

Start with `factor_mining_batch_test_status`. Continue only when the local direct
Agent API Key validates through Factor Mining `/health` and `/agent/status`.
If status reports setup is required, call `factor_mining_batch_test_setup_browser`
and tell the user to enter the key in the local browser page. Never ask the
user to paste the key into chat.

Determine whether the user is starting from a public task or a custom idea.
For a public task flow, call `factor_mining_batch_test_list_public_tasks`, show
concise choices, and ask the user to pick one unless they explicitly ask the
agent to choose. Create the session with
`factor_mining_batch_test_create_task_session`.

For a custom idea, create a direct `task_payload` and call
`factor_mining_batch_test_create_custom_session`. The payload must include `task_id`,
`title`, `category`, `description`, non-empty `allowed_data`, and `fwd_period`.
`allowed_data` must include every input column the generated `plugin.py` needs,
such as `close`, `volume`, `funding_rate_close`, or `open_interest_close`.
Include useful hints, economic mechanisms, regime considerations, risk sources,
and target behavior when they are available.

When you have a draft description and formula, call
`factor_mining_batch_test_request_dedup_context` and use the returned similar-factor
guidance to avoid near-duplicates. This context informs local revision only.

Write or locate one `plugin.py`, then call
`factor_mining_batch_test_parse_plugin_metadata`. The parser is static and must not
import or execute generated code. When the metadata is valid and the user is
ready to submit, call `factor_mining_batch_test_upload_backtest_wait`. Use
`fwd_period=7` when neither the task nor user specifies a horizon.

After upload, inspect the returned `ok`, `status`, `terminal_status`,
`failures`, sanitized job statuses, artifact availability, and factor-card
metrics. Fetch the default factor card through
`factor_mining_batch_test_get_artifact` when it is not already present and the job
state says an artifact should be available. Use `factor_mining_batch_test_resume_run`
after an interrupted session.

Never show backend job IDs, presigned URLs, local absolute paths, raw
credentials, bearer tokens, or `plugin.py` source in user-facing summaries.

## plugin.py Contract

Use this minimum shape when the user has not supplied an existing plugin. The
metadata values must be static top-level literals so Factor Mining can parse
them without executing source code.

```python
from typing import Any, Dict

import pandas as pd

FACTOR_TYPE = "snake_case_unique_factor_type"
FACTOR_NAME = "human_readable_factor_name"
FACTOR_DEFAULT_PARAMS = {"window": 7}

FACTOR_SECTIONS = {
    "__FACTOR_DESCRIPTION__": "Trailing close-to-close momentum.",
    "__FACTOR_FORMULA__": "close / close[window bars ago] - 1",
    "__FACTOR_TYPE__": FACTOR_TYPE,
    "__FACTOR_PARAM_FIELDS__": "        private int _window;\n",
    "__FACTOR_INIT__": '            _window = GetIntParameter("window", 7);\n',
    "__FACTOR_LOG__": '            Log($"[INIT] window={_window}");\n',
    "__PRICE_WINDOW_EXPR__": "_window + 1",
    "__EXTRA_BUF_FIELDS__": "",
    "__EXTRA_BUF_ENQUEUE__": "",
    "__EXTRA_BUF_DEQUEUE__": "",
    "__EXTRA_BUF_TOARRAY__": "",
    "__FACTOR_COMPUTE_BODY__": """
            var n = prices.Length;
            if (n < _window + 1) return false;
            var past = prices[n - _window - 1];
            if (past == 0) return false;
            rawSignal = prices[n - 1] / past - 1.0;
            return true;
""",
}


def build_signal(close: pd.DataFrame, params: Dict[str, Any], **data: Any) -> pd.DataFrame:
    window = int(params.get("window", FACTOR_DEFAULT_PARAMS["window"]))
    signal = close.pct_change(window)
    return signal.reindex_like(close)
```

Keep Python `build_signal` and `FACTOR_SECTIONS` compute logic aligned. Return
a `pd.DataFrame` aligned with `close`, use only current and historical data,
and keep all data columns within the session `allowed_data` contract.

## Security

- Use only the bundled Factor Mining Batch Test MCP tools for formal product actions.
- Never ask for OpenAI API keys, Codex auth files, BYOK secrets, frontend user
  credentials, or raw Factor Mining credentials.
- Never print, persist in logs, or summarize full credential values.
- Do not call hosted generation endpoints; local-agent mode generates code
  inside the active coding agent.
- Do not call frontend-user credential management, BYOK, Codex profile, task
  publishing, or generic URL/API surfaces.
- Do not import, exec, eval, or otherwise execute generated `plugin.py`.
- Do not print generated `plugin.py` source in summaries.
- Treat downstream IDs, presigned URLs, and service metadata as internal.
- Artifact `404` and `410` responses mean unavailable. Authentication,
  authorization, network, malformed response, and server errors must fail
  clearly with redacted messages.
