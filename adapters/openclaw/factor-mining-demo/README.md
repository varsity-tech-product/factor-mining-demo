# Factor Mining Demo For OpenClaw

Self-contained OpenClaw native plugin for the direct `vt_` Agent API Key Factor
Mining demo flow.

Install locally:

```bash
openclaw plugins install ./adapters/openclaw/factor-mining-demo
openclaw plugins list --json
```

If using the repository as a marketplace source:

```bash
openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo
```

Static validation from the repository root:

```bash
python3 tools/validate-adapters.py
python3 -m json.tool adapters/openclaw/factor-mining-demo/openclaw.plugin.json >/dev/null
```

The key is entered only through the bundled hidden terminal prompt or local
browser setup page. Do not paste the key into chat.
