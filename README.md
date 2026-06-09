# Factor Mining Demo

Demo Codex plugin for the direct Factor Mining Agent API Key flow.

This repository shows the direct local demo workflow:

1. Install the Codex plugin.
2. Enter a `vt_` Factor Mining Agent API Key locally.
3. Ask Codex to start from a public task or a custom factor idea.
4. Let Codex write `plugin.py`, upload it, run the backtest, fetch the factor card, and summarize the result.

The key is entered through a hidden terminal prompt or local browser setup page.
Do not paste the key into Codex chat.

## Install With Codex CLI

Run:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-codex.sh | bash
```

The installer adds the marketplace, installs the plugin, asks for the `vt_`
Agent API Key locally, validates it with Factor Mining, and starts Codex with a
demo workflow prompt.

To install without starting Codex:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-codex.sh | FACTOR_MINING_DEMO_START_CODEX=0 bash
```

## Manual CLI Install

```bash
codex plugin marketplace add varsity-tech-product/factor-mining-demo --ref main
codex plugin add factor-mining-demo@factor-mining-demo-marketplace
PLUGIN_ROOT="$(find "${CODEX_HOME:-$HOME/.codex}/plugins/cache/factor-mining-demo-marketplace/factor-mining-demo" -mindepth 1 -maxdepth 1 -type d -print | sort | tail -n 1)" && python3 "$PLUGIN_ROOT/scripts/factor_setup.py" && codex "Use the Factor Mining Demo plugin. Verify Factor Mining status, then show me the Factor Mining public task list. Do not create a session until I choose a public task or provide a custom idea. Then write a valid plugin.py locally, upload it, wait for the backtest, fetch the default factor card if available, and summarize the result."
```

## Codex Desktop Install

In Codex Desktop, add this marketplace:

- Source: `varsity-tech-product/factor-mining-demo`
- Git ref: `main`
- Sparse paths: leave empty

Then install `Factor Mining Demo` from the marketplace.

To configure the `vt_` Agent API Key before opening Desktop:

```bash
codex plugin marketplace add varsity-tech-product/factor-mining-demo --ref main
codex plugin add factor-mining-demo@factor-mining-demo-marketplace
PLUGIN_ROOT="$(find "${CODEX_HOME:-$HOME/.codex}/plugins/cache/factor-mining-demo-marketplace/factor-mining-demo" -mindepth 1 -maxdepth 1 -type d -print | sort | tail -n 1)" && python3 "$PLUGIN_ROOT/scripts/factor_setup.py"
```

Open Codex Desktop and start a new chat with:

```text
Use the Factor Mining Demo plugin. Verify Factor Mining status, then show me the Factor Mining public task list. Do not create a session until I choose a public task or provide a custom idea. Then write a valid plugin.py locally, upload it, wait for the backtest, fetch the default factor card if available, and summarize the result.
```

## Claude Code And OpenClaw

Codex is the original demo path. The Claude Code bundle under
`adapters/claude-code/factor-mining-demo` adds Claude Code support and is also
the OpenClaw-compatible bundle that OpenClaw can install from the marketplace.
All paths use the same direct `vt_` Agent API Key workflow.

Install with Claude Code:

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@main
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

Recommended one-command OpenClaw install:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-openclaw.sh | bash
```

Prerequisites:

- OpenClaw CLI installed.
- OpenClaw model/auth already configured.
- The installer sets up the OpenClaw gateway service, local node host service,
  and `factormining` agent where possible.
- Enter the `vt_` key only through the hidden prompt or local browser setup
  page. Do not paste the key into chat.

Manual OpenClaw bundle install:

```bash
openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo --force
```

This command only installs the bundle and is for manual install flows where the
gateway, paired local node host, Factor Mining-capable agent, skill allowlist,
and local file/command tool policy are already configured.

## Switch Keys

Inside an active Codex CLI or Codex Desktop session, ask Codex to run:

```bash
python3 scripts/factor_setup.py --browser
```

The setup page opens on `127.0.0.1`. Paste the `vt_` Agent API Key into that
local page, not into chat.

## Local State

Configuration is stored at:

```text
~/.factor-mining-demo/config.json
```

Run state is stored at:

```text
~/.factor-mining-demo/runs/
```

## License

Apache License 2.0.
