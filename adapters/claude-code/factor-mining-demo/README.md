# Factor Mining Demo For Claude Code

Self-contained Claude Code plugin for the direct `vt_` Agent API Key Factor
Mining demo flow.

Install from the marketplace:

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@main
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

Local testing:

```bash
claude --plugin-dir ./adapters/claude-code/factor-mining-demo
claude plugin validate .
claude plugin validate ./adapters/claude-code/factor-mining-demo
```

The key is entered only through the bundled hidden terminal prompt or local
browser setup page. Do not paste the key into chat.
