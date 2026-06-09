#!/usr/bin/env python3
from __future__ import annotations

import filecmp
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
ADAPTERS = [
    ROOT / "adapters" / "claude-code" / "factor-mining-demo",
    ROOT / "adapters" / "openclaw" / "factor-mining-demo",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing required path: {path.relative_to(ROOT)}")


def compare_scripts(adapter: Path) -> None:
    target = adapter / "scripts"
    require(target)
    source_files = sorted(path.relative_to(SCRIPT_ROOT) for path in SCRIPT_ROOT.rglob("*") if path.is_file())
    target_files = sorted(path.relative_to(target) for path in target.rglob("*") if path.is_file())
    ignored_suffixes = {".pyc"}
    source_files = [path for path in source_files if path.suffix not in ignored_suffixes and "__pycache__" not in path.parts]
    target_files = [path for path in target_files if path.suffix not in ignored_suffixes and "__pycache__" not in path.parts]
    if source_files != target_files:
        raise AssertionError(f"script file list mismatch for {adapter.relative_to(ROOT)}")
    for rel in source_files:
        if not filecmp.cmp(SCRIPT_ROOT / rel, target / rel, shallow=False):
            raise AssertionError(f"script differs: {adapter.relative_to(ROOT)}/scripts/{rel}")


def main() -> None:
    claude_marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    assert claude_marketplace["name"] == "factor-mining-demo-marketplace"
    assert claude_marketplace["owner"]["name"] == "Varsity Tech Product"
    assert claude_marketplace["plugins"][0]["source"] == "./adapters/claude-code/factor-mining-demo"

    claude_plugin = load_json(ROOT / "adapters" / "claude-code" / "factor-mining-demo" / ".claude-plugin" / "plugin.json")
    assert claude_plugin["name"] == "factor-mining-demo"

    openclaw_manifest = load_json(ROOT / "adapters" / "openclaw" / "factor-mining-demo" / "openclaw.plugin.json")
    assert openclaw_manifest["id"] == "factor-mining-demo"
    assert openclaw_manifest["configSchema"]["additionalProperties"] is False
    assert openclaw_manifest["skills"] == ["skills/factor-mining-demo"]

    for adapter in ADAPTERS:
        require(adapter / "README.md")
        require(adapter / "skills" / "factor-mining-demo" / "SKILL.md")
        compare_scripts(adapter)

    print("adapter validation passed")


if __name__ == "__main__":
    main()
