---
name: factor-mining-batch-test-batch
description: "Use when a user asks an agent to mine multiple Factor Mining Batch Test factors automatically, such as a serial batch of several factor attempts through bundled MCP tools."
---

# Factor Mining Batch Test Batch

Use this skill for serial batch factor mining. A batch is one user-requested
job, such as "mine 10 factors." An attempt is one factor inside that batch.
Use only the bundled Factor Mining Batch Test MCP tools for product actions.

Some hosts display bundled MCP tool names with a provider prefix, such as
`factor-mining-batch-test__factor_mining_batch_test_batch_start`. Treat those as the same tools.

## Required Flow

1. Call `factor_mining_batch_test_status`.
2. If setup is required, call `factor_mining_batch_test_setup_browser` and tell the
   user to enter the direct vt_ Agent API Key in the local browser page.
3. Determine whether the user wants a public task batch or a custom idea batch.
4. For public task mode, call `factor_mining_batch_test_list_public_tasks` before
   `factor_mining_batch_test_batch_start` unless the user already provided a
   `task_id`. Show concise task choices and ask the user to choose unless they
   explicitly authorize the agent to choose. Call
   `factor_mining_batch_test_batch_start` with the selected `task_id`.
5. For custom idea mode, build an explicit `task_payload` before
   `factor_mining_batch_test_batch_start`. The payload must include `task_id`,
   `title`, `category`, `description`, non-empty `allowed_data`, and
   `fwd_period`. Call `factor_mining_batch_test_batch_start` with `idea` and
   `task_payload`.
6. Call `factor_mining_batch_test_batch_next` to get the next isolated attempt
   packet.
7. For that attempt, write only the current attempt's `plugin.py` at the
   `plugin_path` returned by the MCP tool.
8. Do not read sibling attempt directories. Do not reuse previous attempt
   implementation details.
9. Use existing single-factor MCP tools for task/session/dedup/metadata
   actions as needed.
10. Submit with `factor_mining_batch_test_batch_upload_backtest_wait`, not the generic
   upload tool.
11. Record and summarize each attempt only through batch MCP results.
12. Repeat `factor_mining_batch_test_batch_next` until it returns `done=true`.
13. Finish with `factor_mining_batch_test_batch_results`.

## Isolation Rules

- `factor_mining_batch_test_batch_next` returns only the current attempt packet.
- Treat `diversity_hints` as coarse guidance only.
- Never inspect sibling attempt directories or historical `plugin.py` files.
- Never carry forward previous attempt source, formulas, or implementation
  details.
- Batch mode provides MCP state, file, and information-flow isolation between
  attempts. It does not guarantee host-level isolated model context.

## User-Facing Summaries

Do not show direct vt_ keys, raw job IDs, presigned URLs, local absolute paths,
or `plugin.py` source. Describe each attempt by index, status, factor
name/type when available, sanitized metrics, and sanitized errors.
