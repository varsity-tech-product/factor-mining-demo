# Factor Mining Batch Test Plugin

Factor Mining Batch Test is a bundled local-MCP test build for direct vt_ Agent
API Key workflows. It preserves the single-factor flow and adds serial batch
factor mining through the same MCP server. The final remote-MCP production
package will come later.

Key entry happens through a local browser setup page opened by
`factor_mining_batch_test_setup_browser`. Do not paste the key into chat.

MCP startup requires Python. Codex and Claude Code use the bundled manifests;
the OpenClaw installer configures an absolute `python3` path at install time so
the gateway/node host does not depend on shell startup files.

## MCP Tools

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

OpenClaw may display provider-prefixed tool names such as
`fmbt__factor_mining_batch_test_status`; those are the same bundled tools.

## Serial Batch Mode

Batch mode mines multiple factors serially through MCP tools. Each attempt gets
its own local state and artifact area, `factor_mining_batch_test_batch_next` returns
only the current attempt packet, and final summaries are sanitized through
`factor_mining_batch_test_batch_results`.

Batch mode provides MCP state, file, and information-flow isolation between
attempts. It does not guarantee host-level isolated model context.
