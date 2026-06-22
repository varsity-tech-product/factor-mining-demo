# Remote MCP Plugin Codex Prompts

Use one prompt per new Codex window. Start with Phase 01. Do not run Phase 03 before the backend runtime inputs are available.

## Phase 01 Prompt — Production Remote MCP Plugin Package

```text
You are working in /Users/richsion/Desktop/quandora/quandora-plugins.

Objective: implement Phase 01 of the production Remote MCP Factor Mining plugin package.

Read these files first:
- docs/remote-mcp-product-plan.md
- docs/remote-mcp-plugin-phase-01-production-package.md

Scope:
- Build the first production Remote MCP Factor Mining plugin package.
- Treat the public repository target name as varsity-tech-product/quandora-plugins.
- Treat the marketplace id as quandora.
- Treat factor-mining as the first production plugin package and service skill.
- Keep plugins/factor-mining-batch-test as demo/reference only.
- Add a separate production package, preferably plugins/factor-mining.
- Production package must declare Remote MCP and must not run a bundled local Python MCP server.
- Production package must expose only the first-release single-factor Factor Mining skill.

Hard boundaries:
- Do not delete plugins/factor-mining-batch-test.
- Do not make factor-mining-batch-test the default production path.
- Do not add local Python MCP server files to the production package.
- Do not add python/python3/PATH troubleshooting to production docs.
- Do not ask users to paste or configure vt_ keys.
- Do not add direct Product Backend or direct Factor Mining calls.
- Do not claim live Product Backend or Factor Mining readiness.
- Do not modify /Users/richsion/Desktop/quandora/quandora-auth-service.
- Do not modify /Users/richsion/Desktop/quandora/factor_mining.
- Do not introduce new user-facing references to the old repository name factor-mining-agent-plugins.
- Do not rename the Factor Mining service/tool namespace to Quandora in this phase.

Prepare:
cd /Users/richsion/Desktop/quandora/quandora-plugins
git status --short

If the worktree is not clean except for known docs added by the owner, stop and report the dirty files. Do not stash, reset, or overwrite user changes.

Create a new branch if not already on a dedicated feature branch:
git switch -c feat/remote-mcp-production-plugin-phase-01

Implement the exact tasks in docs/remote-mcp-plugin-phase-01-production-package.md:
- Add production package skeleton under plugins/factor-mining.
- Add product-neutral Codex, Claude Code, and supported OpenClaw metadata.
- Add Remote MCP declaration for https://mcp.quandora.ai/factor-mining and staging testing guidance for https://mcp-staging.varsity.lol/factor-mining.
- Add the first-release Factor Mining skill.
- Update marketplace manifests.
- Update README so production Remote MCP package is the default user-facing path.
- Add tools/validate-remote-mcp-product-package.py.

Validation:
- python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
- python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
- python3 -m json.tool plugins/factor-mining/.codex-plugin/plugin.json >/dev/null
- python3 -m json.tool plugins/factor-mining/.claude-plugin/plugin.json >/dev/null
- python3 tools/validate-remote-mcp-product-package.py
- claude plugin validate plugins/factor-mining, if claude is installed
- Codex plugin marketplace/install smoke with a temporary CODEX_HOME, if codex is installed. Use `codex plugin marketplace add "$(pwd)"` for a local-path smoke; use `codex plugin marketplace add varsity-tech-product/quandora-plugins --ref "$(git branch --show-current)"` only for a GitHub-source smoke.
- OpenClaw package validation, if openclaw is installed
- git diff --check

Run a product pollution scan over the production package and README:
rg -n "factor-mining-agent-plugins|vt_|python3|python|plugin_path|local MCP|local-MCP|direct Product Backend|direct Factor Mining|d25q1jf66e8y4g|CloudFront|/api/cast" README.md plugins/factor-mining .agents/plugins/marketplace.json .claude-plugin/marketplace.json

The scan may find intentional "no vt_ key" language only if it is written as a prohibition, not a setup path. Review every hit manually and remove anything product-inappropriate.

Commit and push:
git status --short
git add README.md .agents/plugins/marketplace.json .claude-plugin/marketplace.json plugins/factor-mining tools/validate-remote-mcp-product-package.py docs/remote-mcp-plugin-phase-01-production-package.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add production Remote MCP Factor Mining plugin package"
git push origin HEAD

Report branch, commit, changed files, validation output, unavailable platform validators, and remaining blockers for live Remote MCP testing.
```

## Phase 02 Prompt — Local Agent To Remote MCP Connectivity

```text
You are working in /Users/richsion/Desktop/quandora/quandora-plugins.

Objective: implement Phase 02 local agent to Remote MCP connectivity smoke tests for the production plugin package.

Read these files first:
- docs/remote-mcp-product-plan.md
- docs/remote-mcp-plugin-phase-02-local-agent-connectivity.md
- docs/remote-mcp-plugin-phase-01-production-package.md

Start this phase only after Phase 01 production package exists. If plugins/factor-mining does not exist, stop and report that Phase 01 is not complete.

Hard boundaries:
- Do not ask users for vt_ keys.
- Do not use local Python MCP as a fallback for the production plugin.
- Do not call Product Backend directly.
- Do not call Factor Mining directly.
- Do not claim Product Backend or Factor Mining live readiness.
- Do not edit backend repos.
- Do not require PRODUCT_BACKEND_FACTOR_MINING_AUTH in this phase.
- Treat the public repository target name as varsity-tech-product/quandora-plugins.
- Treat the marketplace id as quandora.
- Do not introduce new user-facing references to the old repository name factor-mining-agent-plugins.

Prepare:
cd /Users/richsion/Desktop/quandora/quandora-plugins
git status --short

If the worktree is not clean except for known owner docs, stop and report the dirty files.

Create a new branch if needed:
git switch -c feat/remote-mcp-plugin-connectivity-smoke

Implement the exact tasks in docs/remote-mcp-plugin-phase-02-local-agent-connectivity.md:
- Add tools/smoke-remote-mcp-connectivity.sh.
- Add platform install smoke docs for Codex, Codex Desktop, Claude Code, and OpenClaw.
- Document unauthenticated expected behavior.
- Document authenticated behavior gated on REMOTE_MCP_ACCEPTANCE_TOKEN or a repeatable connect flow.

Run unauthenticated smoke:
bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol

If REMOTE_MCP_ACCEPTANCE_TOKEN is available in the environment, run authenticated smoke:
REMOTE_MCP_ACCEPTANCE_TOKEN="$REMOTE_MCP_ACCEPTANCE_TOKEN" bash tools/smoke-remote-mcp-connectivity.sh --base-url https://mcp-staging.varsity.lol

Do not print the token.

Platform validation:
- Codex CLI install smoke with temporary CODEX_HOME if codex is installed.
- Codex Desktop instructions must be manually checkable.
- claude plugin validate plugins/factor-mining if claude is installed.
- OpenClaw install/inspect/skills check if openclaw is installed.

Validation:
- bash -n tools/smoke-remote-mcp-connectivity.sh
- python3 tools/validate-remote-mcp-product-package.py
- git diff --check
- rg -n "factor-mining-agent-plugins|vt_|plugin_path|direct Product Backend|direct Factor Mining|d25q1jf66e8y4g|CloudFront|/api/cast" README.md plugins/factor-mining tools/smoke-remote-mcp-connectivity.sh

Review every grep hit. Prohibition language is allowed; setup or fallback language is not.

Commit and push:
git status --short
git add README.md plugins/factor-mining/README.md tools/smoke-remote-mcp-connectivity.sh docs/remote-mcp-plugin-phase-02-local-agent-connectivity.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add Remote MCP plugin connectivity smoke tests"
git push origin HEAD

Report branch, commit, changed files, unauthenticated smoke result, authenticated smoke result or blocker, platform validation status, and any remaining blockers.
```

## Phase 03 Prompt — Live Factor Mining Acceptance

```text
You are working in /Users/richsion/Desktop/quandora/quandora-plugins.

Objective: implement Phase 03 live acceptance tooling and run the complete staging product path when runtime inputs are available.

Read these files first:
- docs/remote-mcp-product-plan.md
- docs/remote-mcp-plugin-phase-03-live-factor-mining-acceptance.md
- docs/remote-mcp-plugin-phase-02-local-agent-connectivity.md

Do not start live acceptance unless all required runtime inputs exist:
- Remote MCP staging has deployed the Product Backend client work.
- Remote MCP staging is configured with REMOTE_MCP_FACTOR_MINING_BACKEND=product_backend.
- Remote MCP staging has PRODUCT_BACKEND_FACTOR_MINING_BASE_URL=http://product-backend.quandora-staging.internal:8000.
- Remote MCP staging has PRODUCT_BACKEND_FACTOR_MINING_AUTH injected as a secure secret.
- A staging Remote MCP OAuth acceptance token or repeatable connect flow is available.

If those are not available, implement only acceptance tooling/docs and report live acceptance as blocked.

Hard boundaries:
- Do not put PRODUCT_BACKEND_FACTOR_MINING_AUTH in repo, docs, logs, PRs, or chat.
- Do not ask users for vt_ keys.
- Do not call Product Backend directly from the plugin or local agent.
- Do not call Factor Mining directly from the plugin or local agent.
- Do not bypass Remote MCP OAuth.
- Do not return or print presigned artifact URLs as user-facing outputs.
- Treat the public repository target name as varsity-tech-product/quandora-plugins.
- Treat the marketplace id as quandora.
- Do not introduce new user-facing references to the old repository name factor-mining-agent-plugins.

Prepare:
cd /Users/richsion/Desktop/quandora/quandora-plugins
git status --short

If the worktree is not clean except for known owner docs, stop and report the dirty files.

Create a new branch if needed:
git switch -c feat/remote-mcp-plugin-live-acceptance

Implement the exact tasks in docs/remote-mcp-plugin-phase-03-live-factor-mining-acceptance.md:
- Add tools/acceptance-remote-mcp-factor-mining.sh.
- Add fixtures/candidate-factor-plugin.py as a diagnostic candidate only.
- Add docs/remote-mcp-plugin-release-checklist.md.
- Update README and plugins/factor-mining/README.md with release acceptance notes.

Validation:
- bash -n tools/acceptance-remote-mcp-factor-mining.sh
- python3 tools/validate-remote-mcp-product-package.py
- git diff --check
- rg -n "factor-mining-agent-plugins|PRODUCT_BACKEND_FACTOR_MINING_AUTH=.*[^<]|vt_|plugin_path|direct Product Backend|direct Factor Mining|d25q1jf66e8y4g|CloudFront|/api/cast" README.md plugins/factor-mining tools docs fixtures

If REMOTE_MCP_ACCEPTANCE_TOKEN is available and staging is confirmed product_backend, run:
REMOTE_MCP_ACCEPTANCE_TOKEN="$REMOTE_MCP_ACCEPTANCE_TOKEN" \
  bash tools/acceptance-remote-mcp-factor-mining.sh \
  --base-url https://mcp-staging.varsity.lol \
  --plugin-source-file ./fixtures/candidate-factor-plugin.py

If a canonical plugin source is provided separately, use it instead of the candidate fixture and record that the run used canonical source. Do not commit canonical source if it is proprietary or marked non-public.

Commit and push:
git status --short
git add README.md plugins/factor-mining/README.md tools/acceptance-remote-mcp-factor-mining.sh fixtures/candidate-factor-plugin.py docs/remote-mcp-plugin-phase-03-live-factor-mining-acceptance.md docs/remote-mcp-plugin-release-checklist.md docs/remote-mcp-plugin-prompts.md
git commit -m "Add Remote MCP Factor Mining live acceptance workflow"
git push origin HEAD

Report branch, commit, changed files, live acceptance result or blocker, platform test status, request/run IDs without secrets, and whether artifact retrieval returned a safe content envelope.
```
