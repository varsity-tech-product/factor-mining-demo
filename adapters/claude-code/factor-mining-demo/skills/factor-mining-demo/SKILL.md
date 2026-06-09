---
name: factor-mining-demo
description: "Use when Claude Code should demonstrate the direct vt_ Agent API Key Factor Mining flow: create or submit a plugin.py, run a user-scoped backtest, wait for workflow and job results, fetch artifacts, summarize outcomes, or resume a local-agent run through the bundled helper scripts."
---

# Factor Mining Demo

Use this skill for the Factor Mining Demo flow. Claude Code writes or
locates one local `plugin.py`. Factor Mining validates, stores, backtests, and
returns workflow, job, artifact, and factor result data through orchestrator
APIs. This demo uses a direct `vt_` Factor Mining Agent API Key entered locally.

Claude Code runs the helper commands from the plugin directory and summarizes
the result for the user. The user does not need to run the command sequence
manually.

## Setup And Status

Setup uses the production Factor Mining API URL by default:

```text
https://d25q1jf66e8y4g.cloudfront.net
```

If setup is missing, run setup from the plugin directory. Never ask the user to
paste the Factor Mining Agent API Key into chat.

```bash
factor-mining-demo-setup
```

When Claude Code is already running and the user wants to add or switch Agent
API Keys, use the local browser setup page:

```bash
factor-mining-demo-browser-setup
```

The browser setup page opens on `127.0.0.1`, accepts the Agent API Key in a
password field, validates it with Factor Mining, saves the local config, and
then exits. The key must never be pasted into chat.

The plain setup script collects the Agent API Key through a hidden terminal
prompt. For non-interactive automation, it can read the key from non-echo stdin:

```bash
factor-mining-demo-setup --api-key-stdin
```

Use `--base-url` only when the user explicitly provides a staging or private
Factor Mining API environment:

```bash
factor-mining-demo-setup --base-url <staging-or-private-api-url>
```

Setup and status must call `/agent/status`. Continue only when `/health` is
healthy and `/agent/status` accepts the delegated Agent API Key. The current
success response is `status: ok` and `agent_key: valid`. If `/agent/status`
returns `403`, tell the user the key is not an external-agent credential.

```bash
factor-mining-demo-status
```

Configuration is stored outside project repositories at:

```text
~/.factor-mining-demo/config.json
```

Run state is stored at:

```text
~/.factor-mining-demo/runs/<client_run_id>.json
```

## Hard Security Rules

- Use only a delegated Factor Mining Agent API Key accepted by `/agent/status`.
- Never ask for OpenAI API keys, platform auth files, BYOK secrets, or frontend
  user credentials.
- Never print, persist in logs, or summarize full API keys.
- Do not call QuantAI service endpoints directly.
- Do not call hosted generation endpoints such as `/brainstorm`, `/generate`,
  or `/regenerate`; the adapter generates code inside Claude Code.
- Do not call `/models`, `/prompts/preview`, `/llm-credentials/*`,
  `/codex-profiles/*`, or `/me/external-agent-key`.
- Do not create, update, or patch tasks; delegated external-agent keys are
  read-only for task publication surfaces.
- Do not import, exec, eval, or otherwise execute generated `plugin.py`.
- Use `factor-mining-demo-api metadata` or the same `ast` plus
  `ast.literal_eval` approach for static metadata extraction.
- Do not print generated `plugin.py` source in summaries.
- Use only user-visible orchestrator IDs in reports: `session_id`, `plugin_id`,
  `job_id`, `factor_id`, and `strategy_run_id`.
- Treat downstream IDs, presigned URLs, and service metadata as internal fields.

## Acceptance Flow

1. Confirm setup.
   - If config is missing or invalid, run setup.
   - If Claude Code is already running and the user needs to use a different key, run
     `factor-mining-demo-browser-setup`.
   - If setup rejects the key, tell the user to provide a Factor Mining Agent
     API Key, not a frontend user key.

2. Determine whether the user is starting from a public task or a custom idea.
   - For a public task flow, read open tasks, show concise choices, and ask the
     user to pick one unless they explicitly ask Claude Code to choose.
   - For a custom idea flow, use the user's factor idea to create a direct
     `task_payload` before session creation.

```bash
factor-mining-demo-api tasks --limit 20 --status open
```

3. Create or reuse a task-backed session.

For worker mode, a published `task_id` is enough:

```bash
factor-mining-demo-api create-session --task-id <task_id> --client-run-id <client_run_id>
```

For free mode, create a direct `task_payload` before upload. It must include at
minimum:

- `task_id`
- `title`
- `category`
- `description`
- `allowed_data`
- `fwd_period`

`allowed_data` must include every input column the generated `plugin.py` needs,
such as `close`, `volume`, `funding_rate_close`, or `open_interest_close`.
Include useful hints, economic mechanisms, regime considerations, risk sources,
and target behavior when they are available.

```bash
factor-mining-demo-api create-session --idea "<research idea>" --task-payload-file task_payload.json --client-run-id <client_run_id>
```

4. Request dedup context when you have a draft description and formula. Use the
   returned similar factors and duplicate-risk guidance to avoid
   near-duplicates.

```bash
factor-mining-demo-api dedup-context --session-id <session_id> --description "<draft description>" --formula "<draft formula>"
```

5. Write or locate one `plugin.py`.
   - Return a `pd.DataFrame` aligned with `close`.
   - Use only current and historical data.
   - Keep Python `build_signal` and `FACTOR_SECTIONS` C# compute logic aligned.
   - Keep the data columns within the session `allowed_data` contract.

6. Inspect metadata statically before upload.

```bash
factor-mining-demo-api metadata --plugin-path plugin.py
```

7. Run one waitable upload and backtest command. Use `fwd_period=7` when neither
   the task nor user specifies a horizon.

```bash
factor-mining-demo-upload-backtest --session-id <session_id> --plugin-path plugin.py --client-run-id <client_run_id> --position-mode both --fwd-period 7 --wait
```

The upload helper intentionally omits optional `submitter_label` and `agent_id`
fields. Factor Mining applies its external-agent provenance defaults from the
delegated API key.

8. Summarize the compact JSON returned by the wait command. Always inspect
   `ok`, `status`, `terminal_status`, and `failures`. If `ok` is false or
   `failures` is present, report the failed or cancelled job clearly instead of
   presenting the run as successful.

## plugin.py Contract

Use this minimum shape when the user has not supplied an existing plugin. The
metadata values must be static top-level literals so the helper can parse them
without executing source code.

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

Factor Mining backend validation is the authority for runtime contract details.
If upload returns validation `errors` or `warnings`, read them, edit
`plugin.py`, and retry upload. Do not call platform regenerate.

## Backtest And Artifacts

For asynchronous POST endpoints, HTTP `202 Accepted` is expected success.
Treat either `200` or `202` as success for session creation, plugin upload, and
backtest submission.

Short-term deployments may return one job with `position_mode: "cs_only"`.
Do not expect separate TS and CS jobs unless the configured Factor Mining API
environment explicitly returns them.

The wait command fetches `default_factor_card.json` when available. It reports
artifact `404` and `410` as unavailable and continues with the core job result.
Authentication, authorization, network, malformed response, and server errors
must fail clearly with redacted stderr.

After a successful backtest, fetch the default-parameter backtest
visualizations from the completed job and save them inside the current
workspace so Claude Code can render them in the reply. Use the first
successful `job_id` unless the user asks to inspect every job.

```bash
JOB_ID="<job_id>"
CLIENT_RUN_ID="<client_run_id>"
JOB_DIR="factor_mining_results/${CLIENT_RUN_ID}/${JOB_ID}"
CONFIG_PATH="${FACTOR_MINING_DEMO_HOME:-$HOME/.factor-mining-demo}/config.json"
BASE_URL="$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["base_url"].rstrip("/"))
PY
)"
API_KEY="$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["api_key"])
PY
)"

fetch_artifact() {
  local job_id="$1" name="$2" out="$3"
  local code headers url
  mkdir -p "$(dirname "${out}")"
  headers="$(mktemp)"

  # Try the service file path first. Do not use -L here; if the service returns
  # a presigned Location, follow it separately without the local Bearer token.
  code=$(curl -sS -D "${headers}" -o "${out}" -w "%{http_code}" \
           -H "Authorization: Bearer ${API_KEY}" \
           "${BASE_URL}/jobs/${job_id}/files/${name}")
  if [ "${code}" = "200" ]; then
    rm -f "${headers}"
    return 0
  fi

  if [ "${code}" = "301" ] || [ "${code}" = "302" ] || [ "${code}" = "303" ] || [ "${code}" = "307" ] || [ "${code}" = "308" ]; then
    url=$(python3 - "${headers}" <<'PY'
import sys
from pathlib import Path
for line in Path(sys.argv[1]).read_text(errors="ignore").splitlines():
    if line.lower().startswith("location:"):
        print(line.split(":", 1)[1].strip())
        break
PY
)
    if [ -n "${url}" ]; then
      code=$(curl -sSL -o "${out}" -w "%{http_code}" "${url}")
      if [ "${code}" = "200" ]; then
        rm -f "${headers}"
        return 0
      fi
    fi
  fi

  if [ "${code}" = "404" ] || [ "${code}" = "410" ]; then
    # Fall back to a presigned URL. The Bearer token is used only to ask the
    # Factor Mining API for the URL; the presigned URL download has no auth header.
    url=$(curl -sS -H "Authorization: Bearer ${API_KEY}" \
            "${BASE_URL}/jobs/${job_id}/files/${name}?as=url" \
          | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))")
    if [ -n "${url}" ]; then
      code=$(curl -sSL -o "${out}" -w "%{http_code}" "${url}")
      if [ "${code}" = "200" ]; then
        rm -f "${headers}"
        return 0
      fi
    fi
  fi

  rm -f "${headers}" "${out}"
  echo "skip ${name} (http=${code})"
  return 1
}

mkdir -p "${JOB_DIR}/step4c"
fetch_artifact "${JOB_ID}" default_factor_card.json      "${JOB_DIR}/factor_card_default.json" || true
fetch_artifact "${JOB_ID}" default_factor_card.txt       "${JOB_DIR}/factor_card_default.txt" || true
fetch_artifact "${JOB_ID}" default_equity_curves.png     "${JOB_DIR}/step4c/equity_curves.png" || true
fetch_artifact "${JOB_ID}" default_ts_profile_4panel.png "${JOB_DIR}/step4c/ts_profile_4panel.png" || true
fetch_artifact "${JOB_ID}" default_trade_log.csv         "${JOB_DIR}/step4c/trade_log.csv" || true
fetch_artifact "${JOB_ID}" default_group_return_plot.png "${JOB_DIR}/step4c/group_return_plot.png" || true
fetch_artifact "${JOB_ID}" default_cs_profile_4panel.png "${JOB_DIR}/step4c/cs_profile_4panel.png" || true
fetch_artifact "${JOB_ID}" default_cs_nav_curves.png     "${JOB_DIR}/step4c/cs_nav_curves.png" || true
```

In the final Claude Code response, embed every available PNG directly with
Markdown image syntax, using the saved relative paths. Do not merely list the
paths. Example:

```markdown
![Equity curves](factor_mining_results/<client_run_id>/<job_id>/step4c/equity_curves.png)
![Time-series profile](factor_mining_results/<client_run_id>/<job_id>/step4c/ts_profile_4panel.png)
```

If a visualization is unavailable, omit that image and briefly say it was not
available. Report the trade log as a saved CSV path when present.

Use resume with waiting after an interrupted Claude Code session:

```bash
factor-mining-demo-api resume --client-run-id <client_run_id> --wait
```

## Result Report

Always include fields that are available in the factor card or job response:

- `ok`
- `status`
- `terminal_status`
- `failures`
- `position_mode`
- `cs_success` and `cs_fail_reasons` when present
- `ts_success` and `ts_fail_reasons` only when present
- `composite_sharpe`, `composite_annual_ret`, and `composite_max_dd`
- `cs_branch.simulation.{sharpe,return,max_drawdown,turnover,fitness}`
- `ts_branch.simulation.{sharpe,return,max_drawdown,turnover,fitness}` only
  when TS results are present
- `icir`, `win_rate`, and `rank_icir`
- `requested_fwd_period`, `actual_fwd_period`, and `horizon_warning`

## Advanced Surfaces

Retest, factor library, promotion, and strategy composition are outside the
normal helper flow. If the user explicitly asks for those operations, inspect
the current Factor Mining API docs, keep all calls user-scoped, and respect
feature gates returned by the API.
