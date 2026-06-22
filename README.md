# Quandora Plugins

This repository is the public Quandora plugin marketplace for local-agent
platforms. It is intended to carry multiple Quandora plugins over time, with
Factor Mining as the first supported service.

The current branch contains the Factor Mining Batch Test package, a downloadable
local-MCP batch test build for Codex, Codex Desktop, Claude Code, and OpenClaw.
It supports the currently working single-factor workflow and adds serial batch
factor mining in the same bundled plugin package.

This is not the final remote-MCP production package. Remote MCP production
packaging will come later.

The bundled MCP server lives at `plugins/factor-mining-batch-test` and exposes
these tools:

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
- `factor_mining_batch_test_batch_start`
- `factor_mining_batch_test_batch_next`
- `factor_mining_batch_test_batch_upload_backtest_wait`
- `factor_mining_batch_test_batch_status`
- `factor_mining_batch_test_batch_results`
- `factor_mining_batch_test_batch_cancel`
- `factor_mining_batch_test_clear_config`

Key entry happens through the local browser setup page returned by
`factor_mining_batch_test_setup_browser`. Do not paste the key into chat.

## Codex CLI

Install from the batch-test branch:

```bash
codex plugin marketplace add varsity-tech-product/quandora-plugins --ref feat/batch-test-local-mcp
codex plugin add factor-mining-batch-test@quandora
```

Update an existing installation:

```bash
codex plugin marketplace upgrade quandora
codex plugin remove factor-mining-batch-test@quandora
codex plugin add factor-mining-batch-test@quandora
```

## Codex Desktop

Add the marketplace in Codex Desktop with these fields:

```text
Source: varsity-tech-product/quandora-plugins
Git ref: feat/batch-test-local-mcp
Plugin: factor-mining-batch-test@quandora
```

After updating, fully quit and reopen Codex Desktop, then start a new chat. If
the MCP server cannot find Python, launch Codex Desktop from an environment
where `python3` is on `PATH` or configure the system PATH. Do not edit the repo
manifests to add a machine-specific Python path.

## Claude Code

Install from the batch-test branch:

```bash
claude plugin marketplace add varsity-tech-product/quandora-plugins@feat/batch-test-local-mcp
claude plugin install factor-mining-batch-test@quandora
claude plugin validate plugins/factor-mining-batch-test
```

Update an existing installation:

```bash
claude plugin marketplace update quandora
claude plugin update factor-mining-batch-test@quandora
claude mcp list
```

## OpenClaw

OpenClaw uses the same bundle package. The installer adds or updates the
`factormining` agent, installs `factor-mining-batch-test`, configures the
`fmbt` MCP server with an absolute `python3` path at install
time, verifies tool visibility, and restarts services when needed.

Recommended install or update:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/quandora-plugins/feat/batch-test-local-mcp/install-openclaw.sh | bash
```

Manual install:

```bash
openclaw plugins install factor-mining-batch-test --marketplace https://github.com/varsity-tech-product/quandora-plugins.git#feat/batch-test-local-mcp --force
PLUGIN_ROOT="$(openclaw plugins inspect factor-mining-batch-test --json --runtime | python3 -c 'import json,sys; p=json.load(sys.stdin); print((p.get("plugin") or {}).get("rootDir") or (p.get("plugin") or {}).get("source"))')"
openclaw mcp set fmbt "{\"command\":\"$(command -v python3)\",\"cwd\":\"${PLUGIN_ROOT}\",\"args\":[\"./mcp/launch.py\"]}"
openclaw gateway restart
openclaw node restart
```

OpenClaw may display provider-prefixed tool names such as
`fmbt__factor_mining_batch_test_status`. Use the
Factor Mining Batch Test MCP tools listed above.

## Single-Factor Flow

Use the `factor-mining-batch-test` skill for one factor at a time:

```text
Use Factor Mining Batch Test. Verify status, then show me the public task list.
Use Factor Mining Batch Test with my custom factor idea.
Use Factor Mining Batch Test to resume my run and summarize results.
```

The single-factor flow keeps the setup, task/session creation, static metadata
parse, dedup context, upload/backtest wait, resume, artifact retrieval, and
clear-config workflows behind MCP tools. When backtest images are available,
single-factor results include `display_markdown.images` with ready-to-render
Markdown image tags.

For custom ideas, use `allowed_data: ["close"]` by default and add only real
columns the generated `plugin.py` actually uses. The MCP tools reject unknown
columns before creating a backend session.

## Serial Batch Flow

Use the `factor-mining-batch-test-batch` skill for multiple factor attempts:

```text
Use Factor Mining Batch Test to mine 5 distinct factors from the public task list.
Use Factor Mining Batch Test to mine 4 custom factors from my idea.
```

Batch mode is serial and isolated. Each attempt gets its own MCP-managed local
state and artifact area. `factor_mining_batch_test_batch_next` returns only the
current attempt packet, and the batch skill instructs the agent not to inspect
sibling attempt directories. Setup, auth, network, backend, and config errors
block or retry the current attempt instead of silently advancing.
`factor_mining_batch_test_batch_upload_backtest_wait` creates the correct
backend session from batch state when `session_id` is omitted. Agents should omit
`session_id` in normal batch submissions and must never use local batch,
attempt, or client-run identifiers as backend session identifiers.

Each completed batch attempt returns the same kind of sanitized result summary as
a single-factor run, including status, factor-card metrics, artifact status, and
failure details when available. Batch mode only adds local state and context
isolation between attempts.

Batch attempts also fetch the default factor card plus standard CS backtest image
artifacts when available. Supported MCP hosts receive those images as renderable
image content and single-run-compatible saved image artifact paths, not only as
artifact names. Batch results also include `display_markdown.images` with
ready-to-render Markdown image tags. Agents should copy those image tags into
the user-visible response and avoid printing local absolute paths as plain text.
Final batch results include `comparison_rows` so agents can produce a table
comparing every factor attempt.

## Local State

Configuration is stored under `~/.factor-mining-batch-test/`. Run state is
stored under `~/.factor-mining-batch-test/runs/`. Batch state is stored under
`~/.factor-mining-batch-test/batches/`.

## License

Apache License 2.0.
