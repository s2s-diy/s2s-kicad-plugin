"""S2S API client — stdlib only, safe to run inside KiCad's bundled Python.

KiCad ships a Python without ``requests``, so this uses ``urllib``. The
client knows nothing about KiCad or wx; it is fully unit-testable on its
own.

Auth is a **personal access token only** (``X-S2S-Key`` header). The
user generates one in the S2S web app (Dashboard → API tokens) and
pastes it into the plugin. There is no email/password path — production
S2S uses OAuth for the browser, and desktop clients use tokens.

High-level entry point: :meth:`S2SClient.convert_image_to_kicad`, which
runs the whole project → upload → ingest → export pipeline and returns
the ``.kicad_sch`` text.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import uuid
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Callable, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

DEFAULT_BASE_URL = "https://s2s.diy"

# KiCad's bundled Python on macOS ships without a usable CA store, so the
# default SSL context can't verify s2s.diy's (valid) certificate and every
# request dies with CERTIFICATE_VERIFY_FAILED. We ship a CA bundle with the
# plugin and verify against it. certifi (if the host Python has it) wins;
# then our bundled pem; then the system default as a last resort.
_BUNDLED_CACERT = os.path.join(os.path.dirname(__file__), "resources", "cacert.pem")

# Cloudflare blocks urllib's default ``Python-urllib/x.y`` User-Agent with a
# 403 before the request ever reaches S2S, so we send our own.
_USER_AGENT = "s2s-kicad-plugin/0.1.1"


def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — certifi is optional
        pass
    if os.path.exists(_BUNDLED_CACERT):
        try:
            return ssl.create_default_context(cafile=_BUNDLED_CACERT)
        except Exception:  # noqa: BLE001 — fall through to system default
            pass
    return ssl.create_default_context()

# Poll cadence for the async ingestion job. The VLM pipeline typically
# lands in 15–60s; cap the wait so a wedged job surfaces as an error
# instead of hanging the KiCad UI thread forever.
_POLL_INTERVAL_SECONDS = 2.0
_POLL_TIMEOUT_SECONDS = 300.0

_IMAGE_MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

ProgressFn = Callable[[str], None]


class S2SError(Exception):
    """Any failure talking to the S2S API, with a human-readable message."""


@dataclass
class S2SClient:
    base_url: str = DEFAULT_BASE_URL
    # Personal access token — the ONLY supported credential. Sent as the
    # ``X-S2S-Key`` header on every request. Generate one at
    # {base_url}/  → Dashboard → API tokens.
    api_key: Optional[str] = None
    timeout: float = 60.0
    _opener: urlrequest.OpenerDirector = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        # Cookie jar kept only to follow benign redirects; auth is header-based.
        # HTTPSHandler carries our CA bundle so verification works inside
        # KiCad's cert-less Python.
        self._opener = urlrequest.build_opener(
            urlrequest.HTTPCookieProcessor(CookieJar()),
            urlrequest.HTTPSHandler(context=_build_ssl_context()),
        )

    # ---- auth -----------------------------------------------------------

    def ensure_auth(self) -> None:
        """Require a token before any operation."""
        if not self.api_key or not self.api_key.startswith("pat_"):
            raise S2SError(
                "Missing S2S API token. Generate one at "
                f"{self.base_url} → Dashboard → API tokens, then paste it here."
            )

    # ---- pipeline steps -------------------------------------------------

    def create_project(self, name: str) -> str:
        data = self._request("POST", "/api/projects", json_body={"name": name})
        return data["id"]

    def upload_image(self, project_id: str, image_path: str) -> str:
        ext = os.path.splitext(image_path)[1].lower()
        mime = _IMAGE_MIMES.get(ext)
        if mime is None:
            raise S2SError(
                f"Unsupported image type {ext or '(none)'}. "
                "Use PNG, JPG, or WebP. (PDFs must be rasterized first.)"
            )
        with open(image_path, "rb") as fh:
            payload = fh.read()
        body, content_type = _encode_multipart(
            field_name="file",
            filename=os.path.basename(image_path),
            content=payload,
            content_type=mime,
        )
        data = self._request(
            "POST",
            f"/api/projects/{project_id}/assets",
            raw_body=body,
            content_type=content_type,
        )
        return data["id"]

    def start_ingestion(self, project_id: str, asset_id: str, mode: str = "schematic_photo") -> str:
        data = self._request(
            "POST",
            f"/api/projects/{project_id}/ingestions",
            json_body={"asset_id": asset_id, "mode": mode},
        )
        return data["id"]

    def wait_for_ingestion(
        self,
        project_id: str,
        ingestion_id: str,
        on_progress: Optional[ProgressFn] = None,
    ) -> dict:
        """Poll until the ingestion is terminal. Returns the final row."""
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        last_status = None
        while True:
            row = self._request("GET", f"/api/projects/{project_id}/ingestions/{ingestion_id}")
            status = row.get("status")
            if status != last_status and on_progress:
                on_progress(f"⏳ ingestion {status}")
                last_status = status
            if status == "complete":
                return row
            if status == "failed":
                err = row.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise S2SError(f"Conversion failed: {msg or 'unknown error'}")
            if time.monotonic() > deadline:
                raise S2SError("Conversion timed out. Try again or use a clearer image.")
            time.sleep(_POLL_INTERVAL_SECONDS)

    def export_kicad(self, project_id: str) -> tuple[str, str]:
        """Return ``(filename, kicad_sch_text)`` for the project's circuit."""
        data = self._request(
            "POST",
            f"/api/projects/{project_id}/exports",
            json_body={"format": "kicad_schematic"},
        )
        return data["filename"], data["content"]

    # ---- orchestration --------------------------------------------------

    def convert_image_to_kicad(
        self,
        image_path: str,
        project_name: Optional[str] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> tuple[str, str]:
        """Full pipeline: image file → ``(filename, .kicad_sch text)``."""

        def note(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        self.ensure_auth()
        name = project_name or f"KiCad import {uuid.uuid4().hex[:6]}"
        note("📁 creating project")
        project_id = self.create_project(name)
        note("⬆️  uploading image")
        asset_id = self.upload_image(project_id, image_path)
        note("🧠 running vision conversion")
        ingestion_id = self.start_ingestion(project_id, asset_id)
        self.wait_for_ingestion(project_id, ingestion_id, on_progress=on_progress)
        note("📐 exporting KiCad schematic")
        filename, content = self.export_kicad(project_id)
        note("✅ done")
        return filename, content

    # ---- transport ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        raw_body: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        if self.api_key:
            headers["X-S2S-Key"] = self.api_key

        body: Optional[bytes] = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif raw_body is not None:
            body = raw_body
            if content_type:
                headers["Content-Type"] = content_type

        req = urlrequest.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                payload = resp.read()
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except URLError as exc:
            raise S2SError(f"Cannot reach S2S at {self.base_url}: {exc.reason}") from exc

        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}

    def _http_error(self, exc: HTTPError) -> S2SError:
        detail = ""
        try:
            body = json.loads(exc.read())
            d = body.get("detail", body)
            detail = d.get("message") if isinstance(d, dict) else str(d)
        except Exception:  # noqa: BLE001 — best-effort error extraction
            detail = exc.reason or ""
        if exc.code == 401:
            return S2SError("Not signed in or session expired. Sign in and retry.")
        if exc.code == 503 and "vision" in (detail or "").lower():
            return S2SError("S2S vision backend is offline right now. Try again later.")
        return S2SError(f"S2S API error {exc.code}: {detail}")


def _encode_multipart(field_name: str, filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    """Encode a single-file multipart/form-data body (stdlib has no helper)."""
    boundary = f"----s2s{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode(),
        f"Content-Type: {content_type}".encode(),
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ]
    return crlf.join(parts), f"multipart/form-data; boundary={boundary}"
