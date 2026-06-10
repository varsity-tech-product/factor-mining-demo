# Factor Mining Demo

Factor Mining Demo is a direct vt_ Agent API Key plugin for Codex, Claude Code,
and OpenClaw. All three platforms use the same bundled Factor Mining Demo MCP
server from `plugins/factor-mining-demo`.

The product surface is the MCP tool set:

- `factor_mining_demo_status`
- `factor_mining_demo_setup_browser`
- `factor_mining_demo_list_public_tasks`
- `factor_mining_demo_create_task_session`
- `factor_mining_demo_create_custom_session`
- `factor_mining_demo_parse_plugin_metadata`
- `factor_mining_demo_request_dedup_context`
- `factor_mining_demo_upload_backtest_wait`
- `factor_mining_demo_resume_run`
- `factor_mining_demo_get_workflow`
- `factor_mining_demo_get_job`
- `factor_mining_demo_get_artifact`
- `factor_mining_demo_batch_start`
- `factor_mining_demo_batch_next`
- `factor_mining_demo_batch_upload_backtest_wait`
- `factor_mining_demo_batch_status`
- `factor_mining_demo_batch_results`
- `factor_mining_demo_batch_cancel`
- `factor_mining_demo_clear_config`

Key entry happens through the local browser setup page returned by the MCP
tool. Never paste the key into chat.

MCP startup requires Python. Codex and Claude Code use the bundled plugin
manifests; the OpenClaw installer writes an absolute `python3` path into
OpenClaw's MCP config so the gateway/node host does not depend on shell startup
files.

## Codex CLI

```bash
codex plugin marketplace add varsity-tech-product/factor-mining-demo --ref main
codex plugin add factor-mining-demo@factor-mining-demo-marketplace
```

## Codex Desktop

Use these fields in Codex Desktop:

```text
Source: varsity-tech-product/factor-mining-demo
Git ref: main
Plugin: factor-mining-demo@factor-mining-demo-marketplace
```

## Claude Code

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@main
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

## OpenClaw

OpenClaw uses the same bundle package. OpenClaw CLI, model settings, and auth
must already be configured.

Recommended install:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-openclaw.sh | bash
```

The installer adds or updates the `factormining` agent, configures the bundled
`fm-demo` MCP server with an absolute `python3` path, verifies the tools, and
restarts the gateway when needed.

Manual bundle install:

```bash
openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo --force
PLUGIN_ROOT="$(openclaw plugins inspect factor-mining-demo --json --runtime | python3 -c 'import json,sys; p=json.load(sys.stdin); print((p.get("plugin") or {}).get("rootDir") or (p.get("plugin") or {}).get("source"))')"
openclaw mcp set fm-demo "{\"command\":\"$(command -v python3)\",\"cwd\":\"${PLUGIN_ROOT}\",\"args\":[\"./mcp/launch.py\"]}"
openclaw gateway restart
```

OpenClaw may display provider-prefixed tool names such as
`fm-demo__factor_mining_demo_status`; use the Factor Mining Demo MCP tools shown
above.

## Update Existing Installations

Codex CLI and Codex Desktop:

```bash
codex plugin marketplace upgrade factor-mining-demo-marketplace
codex plugin remove factor-mining-demo@factor-mining-demo-marketplace
codex plugin add factor-mining-demo@factor-mining-demo-marketplace
```

For Codex Desktop, fully quit and reopen the app after running the update
commands, then start a new chat.

Claude Code:

```bash
claude plugin marketplace update factor-mining-demo-marketplace
claude plugin update factor-mining-demo@factor-mining-demo-marketplace
claude mcp list
```

OpenClaw:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-openclaw.sh | bash
openclaw gateway restart
openclaw node restart
```

Use a fresh agent session after updating. Existing Factor Mining configuration
under `~/.factor-mining-demo/` is preserved.

## First Prompts

```text
Use Factor Mining Demo. Verify status, then show me the public task list.
Use Factor Mining Demo with my custom factor idea.
Use Factor Mining Demo to mine 5 distinct factors for one public task.
Use Factor Mining Demo to resume my run and summarize results.
```

## Batch Mode

Batch mode mines multiple factors serially. Each attempt gets its own MCP-managed
state and file area, and the batch MCP tools return only the current attempt
packet plus coarse diversity hints.

```text
Use Factor Mining Demo to mine 10 distinct factors for a public task.
Use Factor Mining Demo to mine 4 custom factors from my idea.
```

Batch mode provides MCP state, file, and information-flow isolation between
attempts. It does not guarantee host-level isolated model context.

## Local State

Configuration is stored under `~/.factor-mining-demo/`. Run state is stored
under `~/.factor-mining-demo/runs/`. Batch state is stored under
`~/.factor-mining-demo/batches/`.

## License

Apache License 2.0.
