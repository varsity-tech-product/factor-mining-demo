#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "plugins" / "factor-mining-demo" / "mcp"
sys.path.insert(0, str(MCP_ROOT))

import server
from factor_mining_agent_lib.api import ArtifactDownload


class FakeClient:
    def __init__(self) -> None:
        self.requested: list[tuple[str, str]] = []
        self.card = {
            "factor_name": "Validation Factor",
            "metrics": {"rank_ic": 0.1},
            "artifacts": {
                "group_daily.parquet": {"kind": "data"},
                "notes": "factor card intentionally omits image artifact names",
            },
        }
        self.card_body = json.dumps(self.card, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.images = {
            "default_cs_nav_curves.png": b"\x89PNG\r\n\x1a\nnav",
            "default_cs_profile_4panel.png": b"\x89PNG\r\n\x1a\nprofile",
            "default_group_return_plot.png": b"\x89PNG\r\n\x1a\ngroups",
        }

    def artifact_download(self, job_id: str, name: str) -> ArtifactDownload:
        self.requested.append((job_id, name))
        if name == "default_factor_card.json":
            return ArtifactDownload(
                body=self.card_body,
                status=200,
                content_type="application/json",
                final_url="https://artifact-store/default_factor_card.json",
                headers={"Content-Type": "application/json"},
            )
        if name in self.images:
            return ArtifactDownload(
                body=self.images[name],
                status=200,
                content_type="image/png",
                final_url=f"https://artifact-store/{name}",
                headers={"Content-Type": "image/png"},
            )
        raise AssertionError(f"unexpected artifact request: {name}")


def main() -> int:
    client = FakeClient()
    with tempfile.TemporaryDirectory() as tmpdir:
        card, artifact = server._fetch_optional_artifact(
            client,
            ["job-1"],
            "default_factor_card.json",
            tmpdir,
        )
        assert card == client.card, card
        assert artifact["status"] == "available", artifact
        assert artifact["path"] == str(Path(tmpdir) / "default_factor_card.json"), artifact
        assert len(artifact.get("image_artifacts") or []) == 3, artifact
        assert not (Path(tmpdir) / "group_daily.parquet").exists()
        assert (Path(tmpdir) / "default_factor_card.json").read_bytes() == client.card_body
        for image_name, image_body in client.images.items():
            assert (Path(tmpdir) / image_name).read_bytes() == image_body
        requested_names = [name for _job_id, name in client.requested]
        assert requested_names == [
            "default_factor_card.json",
            "default_cs_nav_curves.png",
            "default_cs_profile_4panel.png",
            "default_group_return_plot.png",
        ], requested_names
    print("artifact saving validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
