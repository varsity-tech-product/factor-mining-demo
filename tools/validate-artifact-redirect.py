#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "plugins" / "factor-mining-demo" / "mcp"
sys.path.insert(0, str(MCP_ROOT))

from factor_mining_agent_lib.api import ApiClient


class RecordingServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, role: str):
        super().__init__(("127.0.0.1", 0), RecordingHandler)
        self.role = role
        self.target_url = ""
        self.requests: list[dict[str, str | None]] = []


class RecordingHandler(BaseHTTPRequestHandler):
    server: RecordingServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self.server.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
            }
        )
        if self.server.role == "api":
            self.send_response(302)
            self.send_header("Location", self.server.target_url)
            self.end_headers()
            return

        if self.path == "/plot.png":
            body = b"\x89PNG\r\n\x1a\nfactor-mining-demo"
            content_type = "image/png"
        else:
            body = json.dumps({"ok": True, "source": "artifact-store"}).encode("utf-8")
            content_type = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(server: HTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def main() -> int:
    api = RecordingServer("api")
    artifact_store = RecordingServer("artifact-store")
    api_thread = serve(api)
    artifact_thread = serve(artifact_store)
    try:
        artifact_store_url = f"http://127.0.0.1:{artifact_store.server_port}/artifact.json"
        api.target_url = artifact_store_url
        base_url = f"http://127.0.0.1:{api.server_port}"
        client = ApiClient(base_url, "validation-secret")

        payload = client.artifact("job-1", "default_factor_card.json")

        expected_path = f"/jobs/{quote('job-1', safe='')}/files/{quote('default_factor_card.json', safe='')}"
        assert payload == {"ok": True, "source": "artifact-store"}, payload
        assert api.requests == [{"path": expected_path, "authorization": "Bearer validation-secret"}], api.requests
        assert artifact_store.requests == [{"path": "/artifact.json", "authorization": None}], artifact_store.requests

        api.requests.clear()
        artifact_store.requests.clear()
        binary_body = b"\x89PNG\r\n\x1a\nfactor-mining-demo"
        api.target_url = f"http://127.0.0.1:{artifact_store.server_port}/plot.png"
        download = client.artifact_download("job-1", "default_cs_nav_curves.png")
        expected_png_path = f"/jobs/{quote('job-1', safe='')}/files/{quote('default_cs_nav_curves.png', safe='')}"
        assert download.body == binary_body, download
        assert download.content_type == "image/png", download
        assert api.requests == [{"path": expected_png_path, "authorization": "Bearer validation-secret"}], api.requests
        assert artifact_store.requests == [{"path": "/plot.png", "authorization": None}], artifact_store.requests
    finally:
        api.shutdown()
        artifact_store.shutdown()
        api.server_close()
        artifact_store.server_close()
        api_thread.join(timeout=1)
        artifact_thread.join(timeout=1)
    print("artifact redirect validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
