# Factor Mining Demo Plugin

Factor Mining Demo is a bundled MCP plugin for the direct vt_ Agent API Key
workflow. Codex, Claude Code, and OpenClaw all use this same package and the
same Factor Mining Demo MCP tool names.

Key entry happens through a local browser setup page opened by
`factor_mining_demo_setup_browser`. Do not paste the key into chat.

MCP startup requires a `python` executable available to the host process. The
committed launcher starts the bundled server with that interpreter.

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
- `factor_mining_demo_clear_config`

OpenClaw may display provider-prefixed tool names such as
`fm-demo__factor_mining_demo_status`; those are the same bundled tools.
