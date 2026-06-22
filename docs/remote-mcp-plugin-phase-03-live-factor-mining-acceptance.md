# Remote MCP Plugin Phase 03 Live Factor Mining Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the complete staging product path from local agent to Remote MCP to Product Backend to Factor Mining, then prepare release notes for production rollout.

**Architecture:** This phase is live acceptance only. It assumes the production plugin package exists, Remote MCP staging is deployed with Product Backend mode, and secure runtime inputs are available. The plugin still does not call Product Backend or Factor Mining directly; all calls go through Remote MCP tools.

**Tech Stack:** Codex/Claude/OpenClaw plugin installs, Remote MCP OAuth token/connect flow, Product Backend staging service token configured in Remote MCP ECS, Factor Mining canonical or candidate `plugin.py`, shell acceptance script.

---

## Start Condition

Do not start this phase until all of these are true:

- Phase 01 production package is complete.
- Phase 02 local agent connectivity smoke has passed or authenticated smoke is only blocked on token/connect flow.
- Remote MCP backend PR #44 or equivalent Product Backend client work is merged and deployed to staging.
- Remote MCP staging is configured with:

```text
REMOTE_MCP_FACTOR_MINING_BACKEND=product_backend
PRODUCT_BACKEND_FACTOR_MINING_BASE_URL=http://product-backend.quandora-staging.internal:8000
PRODUCT_BACKEND_FACTOR_MINING_AUTH=<secure staging token or ECS secret>
REMOTE_MCP_PRODUCT_BACKEND_FACTOR_MINING_TIMEOUT_SECONDS=55
```

- A staging Remote MCP OAuth acceptance token or repeatable connect flow is available.

For strict happy-path acceptance, a canonical valid Factor Mining `plugin.py` should be available. If it is not available, this phase may run a candidate `plugin.py` attempt, but failures must be classified as diagnostic rather than final product failure unless the failure clearly occurs before Factor Mining schema validation.

## Non-Negotiable Boundaries

- Do not put `PRODUCT_BACKEND_FACTOR_MINING_AUTH` in repo, docs, logs, PRs, or chat.
- Do not ask users for `vt_` keys.
- Do not call Product Backend directly from the plugin or local agent.
- Do not call Factor Mining directly from the plugin or local agent.
- Do not bypass Remote MCP OAuth.
- Do not return or print presigned artifact URLs as user-facing outputs.

## Naming Boundaries

- Repository target name: `varsity-tech-product/quandora-plugins`.
- Marketplace id: `quandora`.
- Production plugin package: `factor-mining`.
- Service/skill: `factor-mining`.
- Remote MCP protected resource: `https://mcp.quandora.ai/factor-mining`.
- Staging Remote MCP resource: `https://mcp-staging.varsity.lol/factor-mining`.
- Do not use the old repository name `factor-mining-agent-plugins` in release
  or install docs.

## Task 1: Add Live Acceptance Script

**Files:**

- Create: `tools/acceptance-remote-mcp-factor-mining.sh`

The script should:

- accept `--base-url`, defaulting to `https://mcp-staging.varsity.lol`
- require `REMOTE_MCP_ACCEPTANCE_TOKEN`
- accept `--plugin-source-file`
- call JSON-RPC `tools/list`
- call `factor_mining_status`
- call `factor_mining_list_public_tasks`
- create a task session from the first suitable public task unless `--task-id` is provided
- call `factor_mining_validate_plugin_source`
- call `factor_mining_request_dedup_context`
- call `factor_mining_upload_backtest_wait`
- if the result is running/resumable, call `factor_mining_resume_run`
- call `factor_mining_get_artifact` when an artifact id/name is available
- write sanitized response JSON under `.quandora/factor-mining/acceptance/<timestamp>/`
- never print token values

Suggested command:

```bash
REMOTE_MCP_ACCEPTANCE_TOKEN=<redacted> \
  bash tools/acceptance-remote-mcp-factor-mining.sh \
  --base-url https://mcp-staging.varsity.lol \
  --plugin-source-file ./fixtures/candidate-factor-plugin.py
```

## Task 2: Add Candidate Plugin Fixture

**Files:**

- Create: `fixtures/candidate-factor-plugin.py`

This fixture is for diagnostic attempts only if Factor Mining has not provided a canonical sample.

The fixture must include the fields Product Backend/FM said are required:

- `FACTOR_TYPE`
- `FACTOR_DEFAULT_PARAMS`
- `FACTOR_SECTIONS`
- `build_signal`

The fixture must reference only conservative common price columns such as `close` unless FM documentation confirms additional available columns. If FM rejects this candidate, record the validation result and request a canonical sample from FM.

Do not present the candidate fixture as canonical or guaranteed-valid unless a live staging run succeeds.

## Task 3: Run Layered Live Tests

Run in order:

1. `tools/list`
2. `factor_mining_status`
3. `factor_mining_list_public_tasks`
4. `factor_mining_create_task_session`
5. `factor_mining_validate_plugin_source`
6. `factor_mining_request_dedup_context`
7. `factor_mining_upload_backtest_wait`
8. `factor_mining_resume_run` if needed
9. `factor_mining_get_artifact` if available

Stop at the first failure and classify:

- Remote MCP OAuth failure
- Remote MCP tool/schema failure
- Remote MCP -> Product Backend service auth failure
- Product Backend action error
- Product Backend -> Factor Mining error
- Factor Mining plugin schema error
- Factor Mining backtest runtime error
- artifact safety/availability issue

## Task 4: Run Platform End-To-End Tests

For each platform available locally:

- Codex CLI
- Codex Desktop
- Claude Code
- OpenClaw

Install the production plugin and run:

```text
Use Quandora Factor Mining to show me the public task list.
```

Then, if authenticated and safe:

```text
Use Quandora Factor Mining to create a session from a public task and validate this plugin source.
```

Only run full upload/backtest from one platform first. After one full run succeeds, repeat a lighter end-to-end check on the other platforms.

## Task 5: Update Release Docs

**Files:**

- Modify: `README.md`
- Modify: `plugins/factor-mining/README.md`
- Create or modify: `docs/remote-mcp-plugin-release-checklist.md`

Document:

- exact platform install commands
- update commands
- OAuth authorization behavior
- first prompt
- expected output directory `.quandora/factor-mining/runs/<run_id>/`
- live acceptance result summary
- known limitations
- no `vt_` key path
- no local MCP fallback

## Task 6: Commit And Report

Commit only acceptance tooling/docs:

```bash
git status --short
git add README.md plugins/factor-mining/README.md tools/acceptance-remote-mcp-factor-mining.sh fixtures/candidate-factor-plugin.py docs/remote-mcp-plugin-phase-03-live-factor-mining-acceptance.md docs/remote-mcp-plugin-release-checklist.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add Remote MCP Factor Mining live acceptance workflow"
git push origin HEAD
```

Report:

- Remote MCP staging URL
- whether Remote MCP backend mode was `product_backend`
- whether `list_public_tasks` reached Product Backend/FM
- whether session creation reached Product Backend/FM
- whether plugin validation reached Product Backend/FM
- whether upload/backtest completed, returned running, or failed
- whether artifact retrieval returned a safe content envelope
- which platform(s) completed local agent end-to-end tests
- any request IDs or run IDs, without secrets
