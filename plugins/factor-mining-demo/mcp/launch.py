#!/usr/bin/env python3
from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path


def _redact(text: str) -> str:
    try:
        from factor_mining_agent_lib.redaction import redact_text

        return redact_text(text)
    except Exception:
        return re.sub(r"vt_[A-Za-z0-9._-]+", "vt_...", text)


def main() -> int:
    mcp_root = Path(__file__).resolve().parent
    server_path = mcp_root / "server.py"
    if not server_path.is_file():
        sys.stderr.write("Factor Mining Demo MCP launcher could not find server.py.\n")
        return 1

    if str(mcp_root) not in sys.path:
        sys.path.insert(0, str(mcp_root))

    previous_argv0 = sys.argv[0]
    sys.argv[0] = str(server_path)
    try:
        runpy.run_path(str(server_path), run_name="__main__")
    except SystemExit:
        raise
    except Exception as exc:
        message = f"Factor Mining Demo MCP launcher could not start the bundled server: {exc}\n"
        sys.stderr.write(_redact(message))
        return 1
    finally:
        sys.argv[0] = previous_argv0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
