# Factor Mining Demo For Claude Code

Self-contained Claude Code plugin for the direct `vt_` Agent API Key Factor
Mining demo flow.

## Install With Claude Code

```bash
claude plugin marketplace add varsity-tech-product/factor-mining-demo@main
claude plugin install factor-mining-demo@factor-mining-demo-marketplace
```

## Install With OpenClaw

Recommended OpenClaw install:

```bash
curl -fsSL https://raw.githubusercontent.com/varsity-tech-product/factor-mining-demo/main/install-openclaw.sh | bash
```

The installer installs or updates this bundle, prepares the OpenClaw gateway and
local node host services, and configures a `factormining` agent for the
`factor-mining-demo` skill where possible. OpenClaw model/auth must already be
configured.

Manual bundle install:

```bash
openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo --force
```

The manual command only installs the bundle. Use it when the gateway, paired
local node host, agent skill allowlist, and local file/command tools are already
configured.

The key is entered only through the bundled hidden terminal prompt or local
browser setup page. Do not paste the key into chat.
