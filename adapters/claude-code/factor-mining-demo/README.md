# Factor Mining Demo For Claude Code

Self-contained Claude Code plugin for the direct `vt_` Agent API Key Factor
Mining demo flow.

## Development Testing

This adapter work is currently on `feat/claude-openclaw-adapters`.

Install the feature branch with Claude Code:

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@feat/claude-openclaw-adapters
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

Local validation:

```bash
claude --plugin-dir ./adapters/claude-code/factor-mining-demo
claude plugin validate .
claude plugin validate ./adapters/claude-code/factor-mining-demo
```

## After this branch is merged to main

Install with Claude Code:

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@main
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

Install the same Claude-compatible bundle with OpenClaw:

```bash
openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo
```

The key is entered only through the bundled hidden terminal prompt or local
browser setup page. Do not paste the key into chat.
