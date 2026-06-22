# Remote MCP Plugin Phase 01 Production Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production Remote MCP Factor Mining plugin package without requiring Product Backend secrets, a staging OAuth acceptance token, or a canonical Factor Mining plugin.

**Architecture:** Keep the existing `factor-mining-batch-test` local-MCP package as a demo/reference package. Add a separate production package that declares Remote MCP and contains one first-release Factor Mining skill. The production package must not run local Python MCP servers and must not expose direct `vt_` key setup.

**Tech Stack:** Codex plugin manifests, Claude Code plugin manifests, OpenClaw bundle/plugin metadata, Markdown skills, JSON validation, shell install/update docs.

---

## Start Condition

This phase can start now.

It does not require:

- `PRODUCT_BACKEND_FACTOR_MINING_AUTH`
- Remote MCP OAuth acceptance token
- Product Backend live deployment switch
- canonical Factor Mining `plugin.py`

Use the latest integration branch in this repository. If the owner has not named a target branch, start from the current branch that contains this plan and create:

```bash
git switch -c feat/remote-mcp-production-plugin-phase-01
```

If the worktree is dirty, stop and report the dirty files. Do not stash, reset, or overwrite user work.

## Non-Negotiable Boundaries

- Do not delete `plugins/factor-mining-batch-test` in this phase.
- Do not make `factor-mining-batch-test` the default production install path.
- Do not add bundled local Python MCP servers to the production package.
- Do not add `python`, `python3`, local script, or PATH troubleshooting to the production flow.
- Do not ask users to paste or configure `vt_` keys.
- Do not call Product Backend or Factor Mining directly from plugin docs or skills.
- Do not claim live Product Backend or Factor Mining readiness.
- Do not modify `quandora-auth-service` or `factor_mining`.

## Naming Boundaries

- The public repository target name is `varsity-tech-product/quandora-plugins`.
- The marketplace id is `quandora`.
- The first production plugin package is `factor-mining`.
- The first service/skill is `factor-mining`.
- Keep `factor-mining-batch-test` only as a demo/reference package.
- Do not introduce new user-facing references to the old repository name
  `factor-mining-agent-plugins`.
- Do not rename the service, skill, or tool namespace to `quandora` in this
  phase. The broader `quandora` plugin name is reserved for a later
  multi-service release.

## Target Package Shape

Create or normalize the production package under:

```text
plugins/factor-mining/
  README.md
  .codex-plugin/plugin.json
  .claude-plugin/plugin.json
  remote-mcp.json or platform-supported MCP declaration files
  skills/
    factor-mining/
      SKILL.md
      agents/
        openai.yaml
```

If the current platform requires a different file name for Remote MCP declaration, use the platform-supported name and document it in the package README. Do not invent an unsupported manifest field. Validate with the installed platform CLI whenever possible.

## Remote MCP Contract

Production resource:

```text
https://mcp.quandora.ai/factor-mining
```

Staging resource for smoke tests:

```text
https://mcp-staging.varsity.lol/factor-mining
```

Production plugin work should default to the production resource, while README/testing docs may show a staging override for internal validation.

Expected Remote MCP tools:

```text
factor_mining_status
factor_mining_list_public_tasks
factor_mining_create_task_session
factor_mining_create_custom_session
factor_mining_validate_plugin_source
factor_mining_request_dedup_context
factor_mining_upload_backtest_wait
factor_mining_resume_run
factor_mining_get_artifact
```

Do not expose first-release batch tools in the production package. Batch remains demo/reference only.

## Task 1: Add Production Package Skeleton

**Files:**

- Create: `plugins/factor-mining/README.md`
- Create: `plugins/factor-mining/.codex-plugin/plugin.json`
- Create: `plugins/factor-mining/.claude-plugin/plugin.json`
- Create: `plugins/factor-mining/skills/factor-mining/SKILL.md`
- Create: `plugins/factor-mining/skills/factor-mining/agents/openai.yaml`
- Create: platform-supported Remote MCP declaration file(s)

Steps:

- [ ] Create the package directory.
- [ ] Add a professional product README that describes the Remote MCP flow only.
- [ ] Add a Codex manifest named `factor-mining` with a production product description.
- [ ] Add a Claude Code manifest named `factor-mining` with the same product positioning.
- [ ] Add OpenClaw-compatible metadata only if the installed OpenClaw CLI can validate it.
- [ ] Add Remote MCP declaration for the Factor Mining protected resource.
- [ ] Confirm there is no local Python MCP server in the production package.

## Task 2: Write The First-Release Skill

**Files:**

- Create/modify: `plugins/factor-mining/skills/factor-mining/SKILL.md`
- Create/modify: `plugins/factor-mining/skills/factor-mining/agents/openai.yaml`

The skill must instruct the agent to:

- call status first
- trigger Remote MCP OAuth when authorization is missing
- list public tasks when the user asks for tasks
- support public-task and custom-idea workflows
- create a session
- draft local `plugin.py` source only when the host workspace supports files
- submit inline `plugin_source` through Remote MCP tools
- request dedup context before final submission
- use `upload_backtest_wait`
- use `resume_run` when the backend returns a resumable/running status
- fetch `default_factor_card.json` or available factor-card artifact
- save outputs under `.quandora/factor-mining/runs/<run_id>/` when the host permits file writes
- summarize metrics, fish level, factor card, chart artifacts, and failure reasons

The skill must prohibit:

- raw HTTP fallback
- local scripts as production fallback
- direct Product Backend calls
- direct Factor Mining calls
- local `plugin_path` upload to Remote MCP
- user-pasted `vt_` keys
- bundled local Python MCP usage
- first-release batch mining claims

## Task 3: Update Marketplace Manifests

**Files:**

- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify or add OpenClaw marketplace/bundle metadata if supported

Requirements:

- Production package should be the default user-facing package.
- Keep `factor-mining-batch-test` only as a demo/reference package if it remains listed.
- If both packages are listed, descriptions must clearly distinguish:

```text
factor-mining            production Remote MCP plugin
factor-mining-batch-test local-MCP demo/reference package
```

- Do not use branch-specific install commands for stable user docs.
- Do not expose local-MCP demo as the recommended production install.

## Task 4: Update Root README

**Files:**

- Modify: `README.md`

README must include:

- concise production product description
- Codex install/update/verify commands
- Claude Code install/update/verify commands
- OpenClaw install/update/verify commands
- first prompt:

```text
Use Quandora Factor Mining to show me the public task list.
```

- explanation that authorization is handled through Remote MCP OAuth
- no `vt_` key setup path
- no local Python MCP production dependency
- local-MCP batch test clearly marked as demo/reference only
- clear note that live backtest acceptance depends on staging/prod backend configuration

## Task 5: Add Static Validation

**Files:**

- Create or update: `tools/validate-remote-mcp-product-package.py`

Validation must check:

- production package exists
- production package has exactly one first-release skill
- production package has no local MCP Python server files
- production package docs do not mention `vt_` key setup
- production package docs do not mention `python`/`python3` as production requirements
- production package docs do not instruct direct HTTP/PB/FM calls
- marketplace points to the production package
- batch package is not described as the production default
- JSON manifests parse

Suggested command:

```bash
python3 tools/validate-remote-mcp-product-package.py
```

## Task 6: Validate Platform Packages

Run the platform validation available on the machine:

```bash
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool plugins/factor-mining/.codex-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/factor-mining/.claude-plugin/plugin.json >/dev/null
python3 tools/validate-remote-mcp-product-package.py
```

If `claude` is installed:

```bash
claude plugin validate plugins/factor-mining
```

If `codex` is installed:

```bash
TMP_CODEX_HOME="$(mktemp -d)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin marketplace add "$(pwd)"
CODEX_HOME="$TMP_CODEX_HOME" codex plugin list --marketplace quandora
```

If `openclaw` is installed, validate the metadata using the installed CLI. Do not claim official OpenClaw support unless the installed CLI confirms the package loads and the skill is visible.

## Task 7: Commit And Report

Commit only Phase 01 files:

```bash
git status --short
git add README.md .agents/plugins/marketplace.json .claude-plugin/marketplace.json plugins/factor-mining tools/validate-remote-mcp-product-package.py docs/remote-mcp-plugin-phase-01-production-package.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add production Remote MCP Factor Mining plugin package"
git push origin HEAD
```

Do not merge to `main` without review.

Report:

- branch
- commit hash
- changed files
- validation commands and results
- whether Codex, Claude Code, and OpenClaw validation were available
- remaining blockers for live Remote MCP testing
