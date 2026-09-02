"""End-to-end tests for the S2S client against a fake in-process server.

Spins up a real ``http.server`` that emulates the S2S endpoints the
plugin touches, so we exercise header auth, multipart upload, async
poll, and export without a live backend or KiCad. Auth is token-only:
every scoped request must carry the ``X-S2S-Key`` header.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from s2s_kicad.s2s_client import S2SClient, S2SError  # noqa: E402

_TOKEN = "pat_testtoken123"


class _Handler(BaseHTTPRequestHandler):
    poll_calls = 0

    def log_message(self, *_args):  # silence test noise
        pass

    def _authed(self) -> bool:
        return self.headers.get("X-S2S-Key") == _TOKEN

    def _send(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        if not self._authed():
            self._send(401, {"detail": {"message": "unauthenticated"}})
            return
        path = self.path
        if path == "/api/projects":
            self._send(201, {"id": "proj_1", "name": json.loads(raw)["name"]})
        elif path.endswith("/assets"):
            assert self.headers["Content-Type"].startswith("multipart/form-data")
            assert b'filename="sketch.png"' in raw
            self._send(201, {"id": "asset_1", "project_id": "proj_1"})
        elif path.endswith("/ingestions"):
            assert json.loads(raw)["asset_id"] == "asset_1"
            self._send(202, {"id": "ing_1", "project_id": "proj_1", "status": "queued"})
        elif path.endswith("/exports"):
            assert json.loads(raw)["format"] == "kicad_schematic"
            self._send(200, {"format": "kicad_schematic", "filename": "circuit.kicad_sch", "content": "(kicad_sch)"})
        else:
            self._send(404, {"detail": {"message": "nope"}})

    def do_GET(self):  # noqa: N802
        if not self._authed():
            self._send(401, {"detail": {"message": "unauthenticated"}})
            return
        if "/ingestions/ing_1" in self.path:
            _Handler.poll_calls += 1
            status = "complete" if _Handler.poll_calls >= 2 else "running"
            self._send(200, {"id": "ing_1", "project_id": "proj_1", "status": status, "result": {}, "error": None})
        else:
            self._send(404, {"detail": {"message": "nope"}})


@pytest.fixture()
def server():
    _Handler.poll_calls = 0
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture()
def image(tmp_path):
    p = tmp_path / "sketch.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return str(p)


def test_full_pipeline(server, image, monkeypatch):
    monkeypatch.setattr("s2s_kicad.s2s_client._POLL_INTERVAL_SECONDS", 0.01)
    client = S2SClient(base_url=server, api_key=_TOKEN)
    events = []
    filename, content = client.convert_image_to_kicad(image, on_progress=events.append)
    assert filename == "circuit.kicad_sch"
    assert content == "(kicad_sch)"
    assert any("done" in e for e in events)


def test_requires_token(server, image):
    client = S2SClient(base_url=server)  # no api_key
    with pytest.raises(S2SError, match="Missing S2S API token"):
        client.convert_image_to_kicad(image)


def test_rejects_non_token_value(server, image):
    client = S2SClient(base_url=server, api_key="not-a-pat")
    with pytest.raises(S2SError, match="Missing S2S API token"):
        client.convert_image_to_kicad(image)


def test_rejects_pdf(server, tmp_path):
    client = S2SClient(base_url=server, api_key=_TOKEN)
    pdf = tmp_path / "schematic.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(S2SError, match="Unsupported image type"):
        client.upload_image("proj_1", str(pdf))


def test_bad_token_surfaces_auth_error(server, image, monkeypatch):
    monkeypatch.setattr("s2s_kicad.s2s_client._POLL_INTERVAL_SECONDS", 0.01)
    client = S2SClient(base_url=server, api_key="pat_wrong")
    with pytest.raises(S2SError, match="Not signed in or session expired"):
        client.convert_image_to_kicad(image)
