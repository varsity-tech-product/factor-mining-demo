#!/usr/bin/env python3
from __future__ import annotations

import filecmp
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
CLAUDE_ADAPTER = ROOT / "adapters" / "claude-code" / "factor-mining-demo"
OPENCLAW_ADAPTER_ROOT = ROOT / "adapters" / "openclaw"
CLAUDE_BIN_WRAPPERS = [
    "factor-mining-demo-setup",
    "factor-mining-demo-browser-setup",
    "factor-mining-demo-status",
    "factor-mining-demo-api",
    "factor-mining-demo-upload-backtest",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"missing required path: {path.relative_to(ROOT)}")


def require_absent(path: Path) -> None:
    if path.exists():
        raise AssertionError(f"unexpected path: {path.relative_to(ROOT)}")


def require_executable(path: Path) -> None:
    require(path)
    if not os.access(path, os.X_OK):
        raise AssertionError(f"path is not executable: {path.relative_to(ROOT)}")


def require_text(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise AssertionError(f"missing text in {path.relative_to(ROOT)}: {needle}")


def require_no_text(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle in text:
        raise AssertionError(f"unexpected text in {path.relative_to(ROOT)}: {needle}")


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

    require_absent(OPENCLAW_ADAPTER_ROOT)
    require(CLAUDE_ADAPTER / "README.md")
    require(CLAUDE_ADAPTER / "skills" / "factor-mining-demo" / "SKILL.md")
    compare_scripts(CLAUDE_ADAPTER)

    for wrapper in CLAUDE_BIN_WRAPPERS:
        require_executable(CLAUDE_ADAPTER / "bin" / wrapper)

    skill = CLAUDE_ADAPTER / "skills" / "factor-mining-demo" / "SKILL.md"
    for wrapper in CLAUDE_BIN_WRAPPERS:
        require_text(skill, wrapper)
    require_no_text(skill, "python3 scripts/")

    readme = ROOT / "README.md"
    require_text(readme, "feat/claude-openclaw-adapters")
    require_text(readme, "After this branch is merged to main")
    require_text(readme, "openclaw plugins install factor-mining-demo --marketplace varsity-tech-product/factor-mining-demo")
    require_no_text(readme, "openclaw plugins install ./adapters/openclaw/factor-mining-demo")

    print("adapter validation passed")


if __name__ == "__main__":
    main()
