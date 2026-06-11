# Factor Mining Batch Test

Factor Mining Batch Test is a downloadable local-MCP batch test build for Codex,
Codex Desktop, Claude Code, and OpenClaw. It supports the currently working
single-factor workflow and adds serial batch factor mining in the same bundled
plugin package.

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
codex plugin marketplace add varsity-tech-product/factor-mining-agent-plugins --ref feat/batch-test-local-mcp
codex plugin add factor-mining-batch-test@factor-mining-batch-test-marketplace
```

Update an existing installation:

```bash
codex plugin marketplace upgrade factor-mining-batch-test-marketplace
codex plugin remove factor-mining-batch-test@factor-mining-batch-test-marketplace
codex plugin add factor-mining-batch-test@factor-mining-batch-test-marketplace
```

## Codex Desktop

Add the marketplace in Codex Desktop with these fields:

```text
Source: varsity-tech-product/factor-mining-agent-plugins
Git ref: feat/batch-test-local-mcp
Plugin: factor-mining-batch-test@factor-mining-batch-test-marketplace
```

After updating, fully quit and reopen Codex Desktop, then start a new chat. If
the MCP server cannot find Python, launch Codex Desktop from an environment
where `python3` is on `PATH` or configure the system PATH. Do not edit the repo
manifests to add a machine-specific Python path.

## Claude Code

Install from the batch-test branch:

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-agent-plugins@feat/batch-test-local-mcp
claude plugin install factor-mining-batch-test@factor-mining-batch-test-marketplace
claude plugin validate plugins/factor-mining-batch-test
```

Update an existing installation:

```bash
claude plugin marketplace update factor-mining-batch-test-marketplace
claude plugin update factor-mining-batch-test@factor-mining-batch-test-marketplace
claude mcp list
```

## OpenClaw

OpenClaw uses the same bundle package. The installer adds or updates the
`factormining` agent, installs `factor-mining-batch-test`, configures the
`factor-mining-batch-test` MCP server with an absolute `python3` path at install
time, verifies tool visibility, and restarts services when needed.

Recommended install or update:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-agent-plugins/feat/batch-test-local-mcp/install-openclaw.sh | bash
```

Manual install:

```bash
openclaw plugins install factor-mining-batch-test --marketplace https://github.com/varsity-tech-product/factor-mining-agent-plugins.git#feat/batch-test-local-mcp --force
PLUGIN_ROOT="$(openclaw plugins inspect factor-mining-batch-test --json --runtime | python3 -c 'import json,sys; p=json.load(sys.stdin); print((p.get("plugin") or {}).get("rootDir") or (p.get("plugin") or {}).get("source"))')"
openclaw mcp set factor-mining-batch-test "{\"command\":\"$(command -v python3)\",\"cwd\":\"${PLUGIN_ROOT}\",\"args\":[\"./mcp/launch.py\"]}"
openclaw gateway restart
openclaw node restart
```

OpenClaw may display provider-prefixed tool names such as
`factor-mining-batch-test__factor_mining_batch_test_status`. Use the
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
clear-config workflows behind MCP tools.

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

## Local State

Configuration is stored under `~/.factor-mining-batch-test/`. Run state is
stored under `~/.factor-mining-batch-test/runs/`. Batch state is stored under
`~/.factor-mining-batch-test/batches/`.

## License

Apache License 2.0.
