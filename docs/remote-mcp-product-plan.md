# Quandora Agent Plugin Remote MCP Product Plan

## 1. Product Direction

The public repository should be renamed to `quandora-plugins` and become the
official Quandora agent-plugin marketplace for supported local-agent platforms.
The repository name should describe the whole distribution surface, not only the
first Factor Mining service.

The long-term product shape is:

```text
Public Quandora plugin repository
  -> one primary Quandora plugin
      -> multiple workflow skills
      -> remote MCP tool surfaces
          -> Quandora Product Backend
              -> Factor Mining, Strategy Backtesting, and future platform services
```

Factor Mining is the first supported service. Future sibling services, such as
Strategy Backtesting, should be added as additional skills and MCP tool
namespaces inside the same primary Quandora plugin unless there is a clear
product reason to publish a separate higher-level plugin.

The product should not feel like a set of unrelated agent add-ons. Users should
install Quandora once, connect their Quandora account once, and then ask their
agent to use different Quandora capabilities through natural language.

Serial batch Factor Mining has already been validated in the demo plugin path as
a working concept. It should remain out of the first public production release.
The first release should focus on the single-factor workflow, Remote MCP OAuth,
artifact return, and local result persistence. Batch mining can be reintroduced
after the base Remote MCP product path is stable.

## 2. Repository, Marketplace, Plugin, And Service Names

Use these names consistently:

| Layer | Name | Why |
| --- | --- | --- |
| GitHub repository | `varsity-tech-product/quandora-plugins` | Contains marketplace manifests, plugin packages, skills, docs, validators, and future service plugins. |
| Marketplace id | `quandora` | Stable install namespace for agent platforms. |
| First production plugin package | `factor-mining` | First service-specific release while Factor Mining is the only exposed product surface. |
| Future primary product plugin | `quandora` or `quandora-research` | Broader plugin container once multiple sibling services ship together. |
| First service/skill | `factor-mining` | Business workflow name visible to the agent. |
| Remote MCP resource | `https://mcp.quandora.ai/factor-mining` | OAuth-protected runtime resource for Factor Mining tools. |
| Tool namespace | `factor_mining_*` | Stable MCP tool prefix. |

Do not use `factor-mining-agent-plugins` in new user-facing documentation. It is
the old repository name and makes the marketplace look service-specific.

Do not name the GitHub repository `quandora-marketplace`. The repository carries
more than marketplace metadata: it also carries plugin packages, skills,
platform manifests, validation tooling, and release documentation. Marketplace
is one layer inside the repository.

The public repository acts as a marketplace root. It may contain
platform-specific marketplace manifests because Codex, Claude Code, OpenClaw,
and future agent platforms can require different metadata formats.

Recommended repository structure:

```text
quandora-plugins/
  README.md
  LICENSE

  .agents/plugins/marketplace.json
  .claude-plugin/marketplace.json
  openclaw or bundle metadata

  plugins/
    quandora/
      README.md
      .codex-plugin/plugin.json
      .claude-plugin/plugin.json
      openclaw metadata
      remote-mcp.json or platform-specific MCP declarations
      skills/
        factor-mining/
          SKILL.md
        factor-mining-batch/        # demo-proven, deferred from first release
          SKILL.md
        strategy-backtesting/
          SKILL.md
```

Short-term compatibility may keep the installable plugin named `factor-mining`
while Factor Mining is the only product surface. Before adding sibling services,
the plugin should be renamed or superseded by a broader product plugin such as
`quandora` or `quandora-research`. A plugin named only `factor-mining` should not
become the permanent container for unrelated services.

## 3. Marketplace, Plugin, Skill, And MCP Responsibilities

The product layers have distinct responsibilities:

| Layer | Responsibility | Runtime role |
| --- | --- | --- |
| Marketplace | Lets the agent platform discover installable Quandora plugins. | Install-time only. |
| Plugin | Packages skills, MCP declarations, metadata, assets, and docs. | Installed product package. |
| Skill | Teaches the model how and when to use Quandora tools. | Model guidance. |
| Remote MCP | Provides real callable tools and OAuth-protected execution. | Runtime tool surface. |

Marketplace entries should stay sparse and stable. The main product logic should
not live in marketplace metadata.

Plugin manifests should expose:

- product name and version
- skills directory
- remote MCP server declaration
- platform metadata
- update/install documentation

Skills should describe business workflows, not internal backend implementation.
They should instruct the agent to use Quandora MCP tools and prohibit unsafe
fallbacks such as raw HTTP calls, local scripts, local filesystem upload paths,
or user-pasted execution keys.

Remote MCP tools provide the actual execution capability. Skill text alone is
not enough: without registered MCP tools, the agent can understand the workflow
but cannot call the product.

## 4. Remote MCP And Backend Model

All production service execution should run through remote MCP.

The local agent should hold only a Remote MCP OAuth token issued for the protected
resource. It should not hold `vt_` or legacy external-agent execution keys.

Runtime chain:

```text
Local agent
  -> Remote MCP OAuth token
  -> https://mcp.quandora.ai/<resource>
  -> Remote MCP validates token, resource, scope, and connection
  -> Remote MCP calls Quandora Product Backend with service-to-service auth
  -> Product Backend calls the real platform service
  -> sanitized result returns to the local agent
```

OAuth authorizes the local agent connection to access Remote MCP. Product Backend
access is a separate service-to-service trust boundary. Remote MCP must not
forward inbound MCP OAuth access tokens to Product Backend.

The current Factor Mining protected resource is:

```text
https://mcp.quandora.ai/factor-mining
```

The current staging resource used during backend bring-up is:

```text
https://mcp-staging.varsity.lol/factor-mining
```

Future services may use separate protected resources, or a shared MCP endpoint
with namespaced tools. The choice should be based on scope isolation and platform
support, but the user-facing install should remain unified.

## 4.1 Current Backend Implementation Status

As of the Phase 06A Remote MCP backend work, the auth-service side has prepared
the Product Backend client boundary but has not yet switched staging or
production runtime traffic to the real Product Backend.

Implemented in auth-service Phase 06A:

- `REMOTE_MCP_FACTOR_MINING_BACKEND=mock|product_backend`
- `PRODUCT_BACKEND_FACTOR_MINING_BASE_URL`
- `PRODUCT_BACKEND_FACTOR_MINING_AUTH`
- `REMOTE_MCP_PRODUCT_BACKEND_FACTOR_MINING_TIMEOUT_SECONDS=55`
- Product Backend HTTP client for:

```text
POST ${PRODUCT_BACKEND_FACTOR_MINING_BASE_URL}/internal/remote-mcp/factor-mining
x-service-token: <PRODUCT_BACKEND_FACTOR_MINING_AUTH>
```

- request envelope construction:

```text
{version, action, request_id, idempotency_key, actor, authorization_context, payload}
```

- deterministic idempotency keys for mutating actions
- stripping client-supplied identity or credential-like payload fields
- no forwarding of inbound MCP OAuth bearer tokens to Product Backend
- inline `plugin_source` only; no local `plugin_path`
- MCP-safe error mapping
- artifact safety checks that reject presigned or storage URLs
- product-neutral MCP tool descriptions
- mocked HTTP tests for Product Backend contract behavior

Product Backend has provided the non-secret endpoint contract:

```text
staging PRODUCT_BACKEND_FACTOR_MINING_BASE_URL=http://product-backend.quandora-staging.internal:8000
prod    PRODUCT_BACKEND_FACTOR_MINING_BASE_URL=http://product-backend.quandora.internal:8000
path    /internal/remote-mcp/factor-mining
auth    x-service-token: <PRODUCT_BACKEND_FACTOR_MINING_AUTH>
version remote-mcp-factor-mining-v1
timeout 55 seconds
```

Product Backend reports that staging and production endpoints are ready and that
MCP-to-PB networking is available inside the VPC. Product Backend has already
verified service auth, `list_public_tasks`, `create_task_session`, validation,
and error forwarding on its side. The remaining cross-team live validation is a
successful Factor Mining backtest with a canonical valid factor plugin.

## 4.2 Current Test Boundary

All tests that can be run without secret runtime inputs should be treated as
Phase 06A tests. These are the tests that are currently in scope:

- auth-service CI for Phase 06A Product Backend client prework
- mocked Product Backend HTTP transport tests
- config fail-closed tests for `product_backend`
- request envelope and idempotency tests
- no-token Remote MCP metadata and `401` challenge smoke tests
- plugin install and tool-discovery smoke tests
- local agent -> Remote MCP authorization trigger behavior
- local agent refusal to use raw HTTP, local scripts, direct Product Backend
  calls, direct Factor Mining calls, or `vt_` keys

These tests do not prove real Factor Mining readiness. They prove that the local
agent package can reach the Remote MCP surface and that Remote MCP is prepared to
call Product Backend once runtime secrets are configured.

The following tests are blocked until the named inputs exist:

| Test | Required input |
| --- | --- |
| Direct Remote MCP ECS -> PB smoke with `factor_mining.list_public_tasks` | staging `PRODUCT_BACKEND_FACTOR_MINING_AUTH` delivered through a secure channel and an execution shell inside the VPC |
| Local agent -> Remote MCP authenticated tool call | staging Remote MCP OAuth acceptance token or repeatable OAuth connect flow |
| Remote MCP -> Product Backend -> Factor Mining list/session validation | deployed Remote MCP configured with `REMOTE_MCP_FACTOR_MINING_BACKEND=product_backend` and staging service token |
| Happy path backtest | canonical valid Factor Mining plugin plus the previous runtime inputs |
| Artifact retrieval from a real run | successful real run and safe artifact envelope |

Therefore, before Product Backend/Auth/Frontend provide the secure token and
OAuth acceptance path, plugin work should focus on installability, skill
guidance, Remote MCP declaration, OAuth trigger behavior, and safe failure
messages. It should not claim that the real Factor Mining chain is complete.

## 5. Service Expansion Model

Adding a sibling service such as Strategy Backtesting requires three contracts:

1. Product Backend to the real service.
2. Remote MCP to Product Backend action envelope.
3. Plugin skill and tool-use workflow.

For Strategy Backtesting, the shape might be:

```text
skills/
  strategy-backtesting/SKILL.md

Remote MCP tools:
  strategy_backtesting_status
  strategy_backtesting_create_session
  strategy_backtesting_upload_strategy
  strategy_backtesting_run_backtest
  strategy_backtesting_get_report

Product Backend actions:
  strategy_backtesting.status
  strategy_backtesting.create_session
  strategy_backtesting.upload_strategy
  strategy_backtesting.run_backtest
  strategy_backtesting.get_report
```

Each new service must define:

- tool names and input schemas
- required OAuth scopes
- Product Backend action names
- request payloads
- response envelopes
- artifact safety rules
- skill workflow
- result persistence conventions

Do not add a separate plugin for every sibling service by default. Separate
plugins should be reserved for distinct product families, materially different
audiences, or capabilities that require separate permissions and release cycles.

## 6. Unified Plugin Strategy

The preferred long-term marketplace shape is one primary plugin:

```text
marketplace: quandora
plugin: quandora or quandora-research
skills:
  factor-mining
  factor-mining-batch (demo-proven, deferred from first release)
  strategy-backtesting
```

This enables cross-service workflows:

```text
Mine candidate factors, select the best ones, then run a strategy backtest.
```

The agent can move between skills and MCP tool namespaces without asking the
user to install or authorize multiple independent products.

The product should avoid unnecessary plugin fragmentation. Fragmentation creates
repeated install steps, repeated authorization, inconsistent update behavior, and
weaker cross-service workflows.

For the first production version, the plugin should expose only the stable
single-factor Factor Mining workflow. The batch skill can remain in the
development/demo repository as evidence and implementation reference, but it
should not be enabled in the public product plugin until batch UX, quotas,
failure handling, and result comparison are productized.

## 7. Factor Mining First Release

Factor Mining remains the first concrete service to ship through the unified
product model.

Factor Mining requirements:

- Marketplace name is stable and professional.
- Plugin name is either the current Factor Mining product name for the first
  release or a broader Quandora product name for the multi-service release.
- MCP server name is stable, for example `quandora-factor-mining`.
- MCP endpoint is `https://mcp.quandora.ai/factor-mining`.
- Local plugin packages do not run Python MCP servers in production.
- Local plugins do not require Python, PATH fixes, cwd assumptions, or local MCP
  scripts.
- User authorization is triggered by normal agent workflow through Remote MCP
  OAuth.
- The plugin never asks users to paste `vt_` keys into chat.
- The plugin does not expose local execution-key setup as a product path.
- The first release does not expose batch mining as a user-facing capability,
  even though the demo path has already proven that serial batch orchestration
  can work.

The current repository branch still contains the validated local-MCP
`factor-mining-batch-test` package. That package is useful as an implementation
reference and regression target, but it is not the production Remote MCP plugin.
The production package should be a separate clean plugin package that:

- declares Remote MCP, not a bundled local Python MCP server
- uses product-neutral names and descriptions
- exposes only the single-factor Factor Mining skill for first release
- starts authorization through Remote MCP OAuth when the user asks for a task
- never asks for or stores a `vt_` key
- never requires local `python` or `python3`
- can be installed and tested on Codex, Claude Code, and OpenClaw

The product repository may temporarily keep both packages during development:

```text
plugins/
  factor-mining-batch-test/     # validated local-MCP demo/reference, not release
  quandora/ or factor-mining/   # production Remote MCP package
```

The release README should clearly present only the production Remote MCP package.
The local-MCP batch package should not appear in first-release user install
instructions.

## 8. Factor Mining Skill Responsibilities

The Factor Mining skill should guide the agent through:

- Checking Quandora/Factor Mining status.
- Triggering authorization if needed.
- Listing public tasks.
- Choosing between public-task and custom-idea workflows.
- Creating a task session or custom session.
- Drafting factor logic and local source when the host workspace supports files.
- Submitting inline `plugin_source` through MCP tools.
- Requesting dedup context before final submission.
- Waiting for or resuming backtest results.
- Fetching factor-card and image artifacts.
- Saving user-visible outputs to the workspace when supported.
- Summarizing metrics, fish level, factor card, charts, and failure reasons.

For the first release, the skill should optimize for one complete factor-mining
run at a time. It should not advertise automatic multi-factor batch mining,
background loops, or "mine N factors" workflows. Those behaviors belong to a
later batch release.

The skill should explicitly prohibit:

- raw HTTP fallback
- local scripts as production fallback
- local `plugin_path` upload to Remote MCP
- user-pasted `vt_` keys
- direct Factor Mining backend calls
- direct Product Backend calls from the local agent

## 9. Output Workspace Convention

The plugin may include empty asset or template folders, but it should not save
run outputs inside the installed plugin cache. Installed plugin directories are
owned by the agent platform and may be read-only, cached, replaced, or removed
during updates.

The plugin also should not pre-create product output folders inside the installed
package. Output folders are user workspace state, not plugin package state.

When a host workspace is available, the agent should save generated source,
factor cards, reports, and images under a user workspace directory.

Recommended convention:

```text
.quandora/
  factor-mining/
    runs/
      <run_id>/
        plugin.py
        factor-card.json
        summary.md
        metadata.json
        images/
          <artifact-name>.png
  strategy-backtesting/
    runs/
      <run_id>/
        strategy.py
        report.json
        summary.md
        images/
          <artifact-name>.png
```

Avoid `.plugin/factormining` as the default name. `.plugin` is ambiguous because
it can be confused with installed plugin package internals. `.quandora` more
clearly means user-owned Quandora output state.

Remote MCP cannot directly write to a user's local disk. It can return sanitized
artifact envelopes, content, metadata, and suggested paths. The local agent, when
allowed by the host, creates directories and writes files.

Artifact responses should support file persistence by returning:

- `artifact_id`
- `name`
- `content_type`
- `content` for JSON/text artifacts
- `content_base64` or host-supported image content for binary images
- `suggested_relative_path`
- `display_markdown` for hosts that can render saved local images

Example artifact envelope:

```json
{
  "run_id": "run_123",
  "artifacts": [
    {
      "name": "default_factor_card.json",
      "content_type": "application/json",
      "content": "{...}",
      "suggested_relative_path": ".quandora/factor-mining/runs/run_123/factor-card.json"
    },
    {
      "name": "default_group_return_plot.png",
      "content_type": "image/png",
      "content_base64": "...",
      "suggested_relative_path": ".quandora/factor-mining/runs/run_123/images/default_group_return_plot.png"
    }
  ]
}
```

The skill should instruct the agent to save artifacts when the host provides
workspace file access and to summarize without local persistence when file access
is unavailable.

Artifact paths must always be relative paths chosen by the product contract or
sanitized by the agent. Remote MCP should never return local absolute paths,
plugin-cache paths, or host-specific filesystem paths.

## 10. Update Model

Plugin updates have two layers:

1. Server-side updates.
2. Installed plugin package updates.

Server-side updates include Remote MCP behavior, Product Backend integrations,
artifact handling, and service implementation. These can usually take effect
without users updating the local plugin, as long as the public tool schemas and
skill assumptions remain compatible.

Installed plugin updates include marketplace metadata, plugin manifest changes,
skills, MCP declarations, install docs, and local assets. These require the agent
platform to refresh or reinstall the plugin package.

The product should minimize required local updates by keeping stable tool names,
stable schemas, and stable workflows. New backend behavior should be delivered
server-side whenever possible.

Recommended update reminder mechanism:

- Remote MCP `status` returns `plugin_version_policy`.
- The policy includes `minimum_supported_version`, `latest_version`,
  `update_required`, and `update_message`.
- Each plugin manifest carries a plugin version.
- Skill instructs the agent to call status first.
- If `update_required=true`, the agent tells the user to update before continuing.
- If an update is recommended but not required, the agent can continue and show a
  concise upgrade suggestion.
- The plugin should not silently update itself. Installed plugins are controlled
  by Codex, Claude Code, OpenClaw, or another host platform.
- The backend should maintain a compatibility window so most updates can ship
  server-side without forcing immediate local plugin updates.

Example status extension:

```json
{
  "status": "ok",
  "plugin_version_policy": {
    "current_client_version": "1.3.0",
    "minimum_supported_version": "1.2.0",
    "latest_version": "1.4.0",
    "update_required": false,
    "update_recommended": true,
    "update_message": "A newer Quandora plugin is available with Strategy Backtesting support.",
    "commands": {
      "codex": [
        "codex plugin marketplace upgrade quandora",
        "codex plugin remove <plugin>@quandora",
        "codex plugin add <plugin>@quandora"
      ],
      "claude_code": ["claude plugin update <plugin>"],
      "openclaw": ["openclaw plugins update"]
    }
  }
}
```

Platform update commands differ:

```bash
codex plugin marketplace upgrade quandora
codex plugin remove <plugin>@quandora
codex plugin add <plugin>@quandora
```

```bash
claude plugin update <plugin>
```

```bash
openclaw plugins update
```

The README should document platform-specific update commands, but the product
should not assume all platforms auto-update installed plugins. Treat installed
plugins as versioned snapshots unless the platform explicitly guarantees
automatic updates.

The skill should present update instructions only when relevant. Normal task
results should not be cluttered with upgrade text unless Remote MCP reports a
required or recommended update.

## 11. Batch Mining Status

Serial batch Factor Mining is a validated demo capability, not a first-release
production feature.

Validated demo behavior:

- A user can request multiple factor attempts.
- The demo MCP can keep per-attempt state.
- Attempts run serially rather than in parallel.
- Each attempt can maintain separate source, metadata, and result records.
- The implementation can reduce information leakage between attempts by giving
  the model only the active attempt state through MCP.

Reasons to defer batch from the first public release:

- First-release reliability should focus on a single complete Factor Mining
  workflow.
- Batch UX needs clearer quota, cancellation, comparison, and partial-failure
  behavior.
- Batch result presentation needs a dedicated product view, not only a chat
  summary.
- True model-context isolation is host-platform dependent. MCP can enforce hard
  tool-state and file-output isolation, but cannot guarantee that a host model
  forgets prior conversation context unless the platform provides separate
  sessions or subagents.

Product decision:

- Keep batch mining in the development/demo repository as a proven reference.
- Do not include or advertise the batch skill in the first production plugin.
- Do not include batch install docs in first-release user-facing README content.
- Reintroduce batch after single-run Remote MCP OAuth, artifact saving, and
  update reminders are stable.

## 12. Three-Platform Install And Verification

Formal docs should provide concise install and verification commands. They
should not expose local MCP implementation details.

For the next plugin milestone, verification is split into two layers:

1. Package smoke tests that do not need live Product Backend credentials.
2. Authenticated Remote MCP tests after a staging OAuth token or connect flow is
   available.

Package smoke tests should prove:

- marketplace install works
- plugin install works
- the Factor Mining skill is visible to the host model
- the Remote MCP declaration is visible to the host runtime
- the plugin package does not start local Python MCP servers
- the first prompt triggers Remote MCP authorization or a clear authorization
  requirement
- the agent does not fall back to raw HTTP or ask for a `vt_` key

Authenticated Remote MCP tests should prove:

- `tools/list` works with a staging Remote MCP OAuth token
- `factor_mining_status` works
- `factor_mining_list_public_tasks` works
- no `vt_` key is shown to or requested from the user

The authenticated tests still do not prove a successful backtest until the
canonical Factor Mining plugin is available.

### 12.1 Codex

Install:

```bash
codex plugin marketplace add varsity-tech-product/quandora-plugins
codex plugin add <plugin>@quandora
```

Verify:

```bash
codex plugin list --marketplace quandora
```

### 12.2 Claude Code

Install:

```bash
claude plugin marketplace add varsity-tech-product/quandora-plugins
claude plugin install <plugin>@quandora
```

Verify:

```bash
claude plugin list
```

Update:

```bash
claude plugin update <plugin>
```

### 12.3 OpenClaw

Install:

```bash
openclaw plugins install <plugin> --marketplace varsity-tech-product/quandora-plugins --force
```

Verify:

```bash
openclaw plugins inspect <plugin> --runtime
openclaw skills check
```

Update:

```bash
openclaw plugins update
```

## 13. First Prompt

The first prompt should exercise normal business flow and trigger OAuth only if
needed:

```text
Use Quandora Factor Mining to show me the public task list.
```

If the user is not yet authorized, the agent should follow the platform's Remote
MCP OAuth flow, let the user authorize in the browser, then continue the original
task.

## 14. Documentation Rules

User-facing docs should avoid:

- local Python MCP server as a production dependency
- `python` or `python3` PATH troubleshooting for production flows
- manual `vt_` key paste setup
- local execution-key setup pages
- first-release batch mining claims
- separate OpenClaw agent creation
- direct backend HTTP calls
- branch-specific install commands for stable releases

User-facing docs should include:

- marketplace install commands
- plugin install commands
- verification commands
- update commands
- unified first prompt
- OAuth authorization behavior
- workspace output directory convention
- supported service list
- version and compatibility notes

## 15. Acceptance Criteria

The final product should satisfy:

- One public marketplace repository supports Codex, Claude Code, OpenClaw, and
  future platforms.
- The marketplace primarily distributes one Quandora product plugin.
- The plugin can contain multiple skills.
- Factor Mining ships as the first service skill.
- Future sibling services are added as skills and tool namespaces unless a
  separate product-level plugin is justified.
- Production tools use Remote MCP, not local Python MCP servers.
- Local agents do not receive or store `vt_` execution keys.
- Remote MCP OAuth supports one user with multiple active local-agent
  connections.
- Product Backend calls real platform services.
- Tool names, scopes, and schemas are stable enough that most changes can ship
  server-side.
- Status tools can report plugin version policy for update reminders.
- Workspace artifacts can be saved under `.quandora/<service>/runs/<run_id>/`
  when the host permits file writes.
- Batch mining remains excluded from the first production release despite being
  validated in the demo path.

## 16. Suggested Implementation Order

1. Keep the current `factor-mining-batch-test` local-MCP package as a validated
   demo/reference package. Do not use it as the production Remote MCP package.
2. Create a new production Remote MCP plugin package in the same repository. The
   recommended first-release name is `factor-mining` for compatibility with the
   current product scope; reserve `quandora` or `quandora-research` for the
   later multi-service release.
3. Add platform-specific marketplace metadata for Codex, Claude Code, and
   OpenClaw that points to the production Remote MCP package.
4. Replace bundled local MCP declarations with Remote MCP declarations for
   `https://mcp.quandora.ai/factor-mining` and the staging equivalent used for
   testing.
5. Add a single first-release Factor Mining skill. The skill should instruct the
   agent to call Remote MCP tools, trigger OAuth when needed, list public tasks,
   create sessions, submit inline `plugin_source`, resume runs, fetch artifacts,
   and save workspace outputs under `.quandora/`.
6. Add package-level validation scripts that check manifest syntax, skill
   visibility, Remote MCP declaration presence, and absence of bundled Python
   MCP server dependencies in the production package.
7. Update README with separate sections for production Remote MCP install and
   local-MCP demo/reference install. The default user path must be the production
   Remote MCP package.
8. Run package smoke tests on Codex, Claude Code, and OpenClaw:

```text
install marketplace
install plugin
verify skill visible
verify Remote MCP server visible
ask: "Use Quandora Factor Mining to show me the public task list."
expect: OAuth trigger or clear authorization-required response
```

9. After a staging OAuth acceptance token or connect flow is available, run
   authenticated Remote MCP tool tests:

```text
tools/list
factor_mining_status
factor_mining_list_public_tasks
```

10. After `PRODUCT_BACKEND_FACTOR_MINING_AUTH` is delivered through a secure
    channel and Remote MCP staging is switched to `product_backend`, run the
    Product Backend live smoke:

```text
Remote MCP -> Product Backend -> factor_mining.list_public_tasks
Remote MCP -> Product Backend -> factor_mining.create_task_session
Remote MCP -> Product Backend -> factor_mining.validate_plugin_source
```

11. After Factor Mining provides a canonical valid plugin, run the happy path:

```text
list_public_tasks -> create_task_session -> upload_backtest_wait -> get_artifact
```

12. Only after the single-factor Remote MCP path is stable, revisit status-based
    plugin version policy, richer workspace artifact persistence, batch mining,
    and sibling services such as Strategy Backtesting.
