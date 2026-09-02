#!/usr/bin/env python3
"""Build a KiCad Plugin & Content Manager (PCM) package for the S2S plugin.

Produces ``dist/s2s-kicad-plugin-<version>.zip`` with the PCM layout:

    metadata.json          # packaged metadata (single version, no download_* fields)
    plugins/               # the action plugin python (imported by KiCad)
    resources/icon.png     # 64x64 icon shown in the Content Manager

and prints the ``download_sha256`` / ``download_size`` / ``install_size``
you paste into the KiCad addon-metadata repository entry (see SUBMITTING.md).

Stdlib only. Run: ``python3 packaging/build_pcm.py``
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # integrations/kicad-plugin
SRC = os.path.join(ROOT, "s2s_kicad")
BUILD = os.path.join(HERE, "build")
DIST = os.path.join(ROOT, "dist")

IDENTIFIER = "com.s2s.kicad.import-circuit-image"
VERSION = "0.1.0"
KICAD_VERSION = "7.0"

# Files copied into the package's plugins/ directory (the action plugin).
PLUGIN_FILES = ["__init__.py", "action.py", "s2s_client.py"]

# The packaged metadata.json — a single version with NO download_* fields.
# The repo-submission metadata (printed at the end) adds those.
PACKAGED_METADATA = {
    "$schema": "https://go.kicad.org/pcm/schemas/v1",
    "name": "Import Circuit Image into KiCad",
    "description": "Turn a photo, screenshot, scan, or hand-drawn sketch of a circuit into an editable KiCad schematic.",
    "description_full": (
        "Pick a circuit image (PNG/JPG/WebP) and this plugin converts it into an "
        "editable .kicad_sch schematic using S2S (sketch-to-schematic). The generated "
        "schematic opens in KiCad; you can further edit, run ERC, and simulate the "
        "circuit online at s2s.diy. Authenticate with a personal API token generated "
        "in the S2S web app."
    ),
    "identifier": IDENTIFIER,
    "type": "plugin",
    "author": {"name": "S2S", "contact": {"web": "https://s2s.diy"}},
    "license": "MIT",
    "resources": {"homepage": "https://s2s.diy/docs/kicad-plugin/"},
    "tags": ["import", "schematic", "ai", "ocr", "conversion"],
    "versions": [
        {"version": VERSION, "status": "development", "kicad_version": KICAD_VERSION}
    ],
}


def _reset(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def build() -> None:
    _reset(BUILD)
    os.makedirs(DIST, exist_ok=True)

    # plugins/ — the action plugin code + a copy of the icon for the toolbar
    plugins_dir = os.path.join(BUILD, "plugins")
    os.makedirs(os.path.join(plugins_dir, "resources"))
    for name in PLUGIN_FILES:
        shutil.copy2(os.path.join(SRC, name), os.path.join(plugins_dir, name))
    icon_src = os.path.join(SRC, "resources", "icon.png")
    shutil.copy2(icon_src, os.path.join(plugins_dir, "resources", "icon.png"))

    # resources/icon.png — shown in the Content Manager
    res_dir = os.path.join(BUILD, "resources")
    os.makedirs(res_dir)
    shutil.copy2(icon_src, os.path.join(res_dir, "icon.png"))

    # metadata.json at the package root
    with open(os.path.join(BUILD, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(PACKAGED_METADATA, fh, indent=2)

    install_size = _dir_size(BUILD)

    zip_path = os.path.join(DIST, f"s2s-kicad-plugin-{VERSION}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(BUILD):
            for name in files:
                abs_path = os.path.join(root, name)
                arc = os.path.relpath(abs_path, BUILD)
                zf.write(abs_path, arc)

    download_size = os.path.getsize(zip_path)
    download_sha256 = _sha256(zip_path)

    print(f"✅ built {zip_path}")
    print(f"   download_size : {download_size}")
    print(f"   install_size  : {install_size}")
    print(f"   download_sha256: {download_sha256}")
    print()
    print("Repo-submission version block (download_url is the GitHub release asset):")
    print(
        json.dumps(
            {
                "version": VERSION,
                "status": "development",
                "kicad_version": KICAD_VERSION,
                "download_url": (
                    "https://github.com/s2s-diy/s2s-kicad-plugin/releases/download/"
                    f"v{VERSION}/s2s-kicad-plugin-{VERSION}.zip"
                ),
                "download_sha256": download_sha256,
                "download_size": download_size,
                "install_size": install_size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    build()
