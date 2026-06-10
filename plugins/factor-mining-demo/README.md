# Factor Mining Demo Plugin

Factor Mining Demo is a bundled MCP plugin for the direct vt_ Agent API Key
workflow. Codex, Claude Code, and OpenClaw all use this same package and the
same Factor Mining Demo MCP tool names.

Key entry happens through a local browser setup page opened by
`factor_mining_demo_setup_browser`. Do not paste the key into chat.

MCP startup requires Python. Codex and Claude Code use the bundled plugin
manifests; the OpenClaw installer configures an absolute `python3` path so the
gateway/node host does not depend on shell startup files.

## MCP Tools

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

OpenClaw may display provider-prefixed tool names such as
`fm-demo__factor_mining_demo_status`; those are the same bundled tools.

## Serial Batch Mode

Batch mode mines multiple factors serially through MCP tools. Each attempt gets
its own local state and artifact area, `factor_mining_demo_batch_next` returns
only the current attempt packet, and final summaries are sanitized through
`factor_mining_demo_batch_results`.

Batch mode provides MCP state, file, and information-flow isolation between
attempts. It does not guarantee host-level isolated model context.
