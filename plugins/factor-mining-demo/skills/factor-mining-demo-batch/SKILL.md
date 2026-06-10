---
name: factor-mining-demo-batch
description: "Use when a user asks an agent to mine multiple Factor Mining Demo factors automatically, such as a serial batch of several factor attempts through bundled MCP tools."
---

# Factor Mining Demo Batch

Use this skill for serial batch factor mining. A batch is one user-requested
job, such as "mine 10 factors." An attempt is one factor inside that batch.
Use only the bundled Factor Mining Demo MCP tools for product actions.

Some hosts display bundled MCP tool names with a provider prefix, such as
`fm-demo__factor_mining_demo_batch_start`. Treat those as the same tools.

## Required Flow

1. Call `factor_mining_demo_status`.
2. If setup is required, call `factor_mining_demo_setup_browser` and tell the
   user to enter the direct vt_ Agent API Key in the local browser page.
3. Start the serial batch with `factor_mining_demo_batch_start`.
4. Call `factor_mining_demo_batch_next` to get the next isolated attempt
   packet.
5. For that attempt, write only the current attempt's `plugin.py` at the
   `plugin_path` returned by the MCP tool.
6. Do not read sibling attempt directories. Do not reuse previous attempt
   implementation details.
7. Use existing single-factor MCP tools for task/session/dedup/metadata
   actions as needed.
8. Submit with `factor_mining_demo_batch_upload_backtest_wait`, not the generic
   upload tool.
9. Record and summarize each attempt only through batch MCP results.
10. Repeat `factor_mining_demo_batch_next` until it returns `done=true`.
11. Finish with `factor_mining_demo_batch_results`.

## Isolation Rules

- `factor_mining_demo_batch_next` returns only the current attempt packet.
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
