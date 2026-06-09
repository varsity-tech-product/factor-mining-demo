from __future__ import annotations

import html
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, TextIO
from urllib.parse import parse_qs, urlsplit


class _SetupServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], token: str):
        super().__init__(server_address, _SetupHandler)
        self.token = token
        self.agent_key: str | None = None
        self.done = threading.Event()


class _SetupHandler(BaseHTTPRequestHandler):
    server: _SetupServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if not self._is_setup_path():
            self._send_text(404, "Not found")
            return
        self._send_html(200, _setup_page(error=None))

    def do_POST(self) -> None:
        if not self._is_setup_path():
            self._send_text(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._send_html(400, _setup_page(error="Enter a Factor Mining Agent API Key."))
            return
        if length > 8192:
            self._send_html(413, _setup_page(error="The submitted value is too large."))
            return

        payload = self.rfile.read(length).decode("utf-8", errors="replace")
        fields = parse_qs(payload, keep_blank_values=True)
        key = (fields.get("api_key") or [""])[0].strip()
        if not key:
            self._send_html(400, _setup_page(error="Enter a Factor Mining Agent API Key."))
            return

        self.server.agent_key = key
        self.server.done.set()
        self._send_html(200, _success_page())

    def _is_setup_path(self) -> bool:
        return urlsplit(self.path).path == f"/{self.server.token}"

    def _send_text(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(encoded)


def _setup_page(error: str | None) -> str:
    error_html = ""
    if error:
        error_html = f'<p class="error" role="alert">{html.escape(error)}</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Factor Mining Setup</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: Canvas;
      color: CanvasText;
    }}
    main {{
      width: min(420px, calc(100vw - 32px));
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.2;
    }}
    p {{
      margin: 0 0 18px;
      color: color-mix(in srgb, CanvasText 72%, Canvas 28%);
      line-height: 1.45;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
    }}
    input {{
      box-sizing: border-box;
      width: 100%;
      height: 42px;
      padding: 8px 10px;
      border: 1px solid color-mix(in srgb, CanvasText 28%, Canvas 72%);
      border-radius: 8px;
      background: Canvas;
      color: CanvasText;
      font: inherit;
    }}
    button {{
      margin-top: 14px;
      width: 100%;
      height: 42px;
      border: 0;
      border-radius: 8px;
      background: #0F766E;
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .error {{
      color: #B42318;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Configure Factor Mining Demo</h1>
    <p>Paste your Factor Mining Agent API Key. The key is sent only to this local setup helper and is not shown in chat.</p>
    {error_html}
    <form method="post" autocomplete="off">
      <label for="api_key">Agent API Key</label>
      <input id="api_key" name="api_key" type="password" autocomplete="off" autofocus required>
      <button type="submit">Save Key</button>
    </form>
  </main>
</body>
</html>"""


def _success_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Factor Mining Setup Complete</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: Canvas;
      color: CanvasText;
    }
    main {
      width: min(420px, calc(100vw - 32px));
    }
    h1 {
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.2;
    }
    p {
      margin: 0;
      color: color-mix(in srgb, CanvasText 72%, Canvas 28%);
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <main>
    <h1>Key Saved</h1>
    <p>The local setup helper saved the key. You can close this page and return to Codex.</p>
  </main>
</body>
</html>"""


def collect_agent_key_via_browser(
    *,
    stderr: TextIO,
    open_browser: Callable[[str], object] | None = None,
    timeout: float = 300.0,
) -> str:
    token = secrets.token_urlsafe(24)
    open_browser = open_browser or webbrowser.open
    server = _SetupServer(("127.0.0.1", 0), token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}/{token}"
    try:
        stderr.write(f"Opening Factor Mining setup page: {url}\n")
        try:
            open_browser(url)
        except Exception:
            stderr.write("Open the setup page URL above in your browser to continue.\n")
        if not server.done.wait(timeout):
            raise RuntimeError("Timed out waiting for the Factor Mining Agent API Key.")
        if not server.agent_key:
            raise RuntimeError("No Factor Mining Agent API Key was received.")
        return server.agent_key
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
