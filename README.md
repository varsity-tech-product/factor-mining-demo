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

Or run:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-codex.sh | bash
```

## Codex Desktop

Use these fields in Codex Desktop:

```text
Source: varsity-tech-product/factor-mining-demo
Git ref: main
Plugin: factor-mining-demo@factor-mining-demo-marketplace
```

You can also run:

```bash
./install-codex-desktop.sh
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

## First Prompts

```text
Use Factor Mining Demo. Verify status, then show me the public task list.
Use Factor Mining Demo with my custom factor idea.
Use Factor Mining Demo to resume my run and summarize results.
```

## Local State

Configuration is stored under `~/.factor-mining-demo/`. Run state is stored
under `~/.factor-mining-demo/runs/`.

## License

Apache License 2.0.
