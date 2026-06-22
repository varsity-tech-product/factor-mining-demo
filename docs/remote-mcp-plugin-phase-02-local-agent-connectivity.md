# Remote MCP Plugin Phase 02 Local Agent Connectivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the production plugin package from local agent platforms to the Remote MCP surface without requiring Product Backend service tokens or a successful Factor Mining backtest.

**Architecture:** This phase tests installability, skill visibility, Remote MCP discovery, authorization behavior, and safe refusal/fallback behavior. It does not switch Remote MCP staging to `product_backend` and does not test the PB/FM happy path.

**Tech Stack:** Codex CLI/Desktop plugin install, Claude Code plugin install, OpenClaw plugin install, Remote MCP OAuth-protected resource metadata, JSON-RPC `tools/list`, shell smoke scripts.

---

## Start Condition

Start this phase only after Phase 01 production package work is merged or the feature branch is ready for testing.

This phase can run in two modes:

1. Unauthenticated smoke mode, available now.
2. Authenticated Remote MCP mode, only after a staging Remote MCP OAuth acceptance token or repeatable connect flow is available.

This phase does not require:

- `PRODUCT_BACKEND_FACTOR_MINING_AUTH`
- Remote MCP staging set to `product_backend`
- canonical Factor Mining `plugin.py`

## Non-Negotiable Boundaries

- Do not ask users to paste `vt_` keys.
- Do not use local Python MCP as a fallback for the production plugin.
- Do not call Product Backend directly.
- Do not call Factor Mining directly.
- Do not claim PB/FM live readiness.
- Do not edit backend repositories.

## Naming Boundaries

- Repository target name: `varsity-tech-product/quandora-plugins`.
- Marketplace id: `quandora`.
- Production plugin package: `factor-mining`.
- Service/skill: `factor-mining`.
- Do not use the old repository name `factor-mining-agent-plugins` in new
  install instructions.
- Do not make the demo/reference package `factor-mining-batch-test` the default
  production install target.

## Test Targets

Staging public Remote MCP surface:

```text
https://mcp-staging.varsity.lol/factor-mining
```

Metadata endpoints:

```text
https://mcp-staging.varsity.lol/.well-known/oauth-protected-resource/factor-mining
https://mcp-staging.varsity.lol/.well-known/oauth-authorization-server
```

## Task 1: Add Connectivity Smoke Script

**Files:**

- Create: `tools/smoke-remote-mcp-connectivity.sh`

The script should:

- accept `--base-url`, defaulting to `https://mcp-staging.varsity.lol`
- fetch protected-resource metadata
- fetch authorization-server metadata
- POST unauthenticated `tools/list` to `/factor-mining`
- assert unauthenticated call returns `401`
- assert `WWW-Authenticate` includes `resource_metadata`
- if `REMOTE_MCP_ACCEPTANCE_TOKEN` is present, POST authenticated `tools/list`
- if authenticated, call `factor_mining_status`
- if authenticated, call `factor_mining_list_public_tasks`
- never print token values

Suggested command:

```bash
bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol
```

Authenticated command:

```bash
REMOTE_MCP_ACCEPTANCE_TOKEN=<redacted> bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol
```

## Task 2: Add Platform Install Smoke Documentation

**Files:**

- Modify: `README.md`
- Modify: `plugins/factor-mining/README.md`

Document smoke commands for:

- Codex CLI
- Codex Desktop
- Claude Code
- OpenClaw

Each platform section must verify:

- marketplace added
- plugin installed
- skill visible
- Remote MCP tools or authorization requirement visible
- first prompt behavior

First prompt:

```text
Use Quandora Factor Mining to show me the public task list.
```

Expected unauthenticated behavior:

```text
The agent should trigger Remote MCP OAuth or explain that the user must connect Quandora before it can list tasks. It must not ask for a vt_ key and must not attempt raw HTTP fallback.
```

## Task 3: Validate Codex Install

Run from a temporary directory with a temporary Codex home when possible:

```bash
TMP_CODEX_HOME="$(mktemp -d)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin marketplace add "$(pwd)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin add factor-mining@quandora
CODEX_HOME="$TMP_CODEX_HOME" codex plugin list --marketplace quandora
```

For a GitHub-source smoke test against a branch, use the repository source and
`--ref`:

```bash
TMP_CODEX_HOME="$(mktemp -d)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin marketplace add varsity-tech-product/quandora-plugins --ref "$(git branch --show-current)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin add factor-mining@quandora
CODEX_HOME="$TMP_CODEX_HOME" codex plugin list --marketplace quandora
```

If Codex Desktop is available, test install through the Desktop marketplace UI using the repository source and current branch ref. Fully quit and reopen Codex Desktop before testing the first prompt.

## Task 4: Validate Claude Code Install

If `claude` is installed:

```bash
claude plugin validate plugins/factor-mining
claude plugin marketplace add "$(pwd)"
claude plugin install factor-mining@quandora
claude plugin list
```

If Claude Code requires a different marketplace command for local paths or branch refs, use the CLI-supported form and record it in the README.

## Task 5: Validate OpenClaw Install

If `openclaw` is installed:

```bash
openclaw plugins install factor-mining --marketplace "$(pwd)" --force
openclaw plugins inspect factor-mining --runtime
openclaw skills check
```

If OpenClaw only supports Claude bundle format for this package, document that explicitly. Do not publish an invented OpenClaw-native manifest.

## Task 6: Run Remote MCP Connectivity Smoke

Unauthenticated:

```bash
bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol
```

Authenticated, only if a token exists:

```bash
REMOTE_MCP_ACCEPTANCE_TOKEN=<redacted> bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol
```

If no token/connect flow exists, report authenticated tests as blocked, not failed.

## Task 7: Commit And Report

Commit Phase 02 docs/scripts only:

```bash
git status --short
git add README.md plugins/factor-mining/README.md tools/smoke-remote-mcp-connectivity.sh docs/remote-mcp-plugin-phase-02-local-agent-connectivity.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add Remote MCP plugin connectivity smoke tests"
git push origin HEAD
```

Report:

- installed platform versions
- install commands that worked
- unauthenticated smoke result
- authenticated smoke result or exact blocker
- whether any agent attempted prohibited fallback behavior
- whether plugin docs remain free of `vt_` setup instructions
