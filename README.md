# Import Circuit Image into KiCad (S2S plugin)

Turn a photo, screenshot, scan, or hand-drawn sketch of a circuit into an
editable KiCad schematic — without leaving KiCad. Powered by
[S2S](https://s2s.diy).

[![CI](https://github.com/s2s-diy/s2s-kicad-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/s2s-diy/s2s-kicad-plugin/actions/workflows/ci.yml)

## What it does

1. Adds an **Import Circuit Image into KiCad** button to the PCB editor.
2. You paste your S2S API token and pick an image (PNG/JPG/WebP).
3. S2S converts it to a schematic.
4. The `.kicad_sch` is saved next to your board and opens in KiCad.
5. Edit, run ERC, and simulate the same circuit online at s2s.diy.

## Repository layout

```
s2s_kicad/
  __init__.py      # registers the ActionPlugin (only inside KiCad)
  action.py        # pcbnew + wx UI dialog
  s2s_client.py    # stdlib-only S2S API client (no KiCad deps)
  resources/
    icon.png       # 64x64 PCM / toolbar icon
tests/             # client tests against a fake server
packaging/
  build_pcm.py     # builds the KiCad PCM package (zip)
pcm-submission/    # prepared, schema-validated KiCad PCM merge-request files
metadata.json      # KiCad PCM manifest
```

`s2s_client.py` intentionally has **no** `pcbnew`/`wx`/`requests`
imports — KiCad's bundled Python lacks `requests`, and keeping the
network layer pure makes it unit-testable outside KiCad.

## Install

### Recommended: Install from File (works today)

1. Download the latest `s2s-kicad-plugin-*.zip` from
   [Releases](https://github.com/s2s-diy/s2s-kicad-plugin/releases).
2. KiCad main window → **Tools → Plugin and Content Manager**.
3. Click **Install from File…** (bottom of the window), pick the zip,
   then **Apply Pending Changes**.

A one-click listing in KiCad's official repository is in progress — see
[`pcm-submission/README.md`](pcm-submission/README.md).

### Advanced: manual copy

Copy or symlink `s2s_kicad/` into your KiCad 3rd-party plugin directory:

- macOS: `~/Documents/KiCad/<ver>/3rdparty/plugins/`
- Linux: `~/.local/share/kicad/<ver>/3rdparty/plugins/`
- Windows: `%USERPROFILE%\Documents\KiCad\<ver>\3rdparty\plugins\`

### Run it — the plugin lives in the PCB Editor

It's a **PCB Editor (pcbnew)** action plugin, not a project-manager or
Schematic Editor one. Open the **PCB Editor**, then find **Import Circuit
Image into KiCad** on the toolbar or under **Tools → External Plugins**.
If it doesn't appear, run **Tools → External Plugins → Refresh Plugins**
(no restart needed).

Point the plugin at a non-default backend with the `S2S_PLUGIN_BASE_URL`
environment variable (e.g. `http://localhost:8080` for a local S2S).

## Auth — API token only

The plugin authenticates with a **personal access token** and nothing
else (no email/password — production S2S is OAuth for the browser).

1. Sign in to S2S in your browser.
2. Dashboard → **API tokens** → **Generate** → copy the `pat_…` value.
3. Paste it into the plugin's **Token** field (remembered in
   `~/.s2s_kicad.json`, `0600`).

The token rides on the `X-S2S-Key` header. Revoke any token from the
same Dashboard screen. Full setup: <https://s2s.diy/docs/kicad-plugin/>.

## Development

```bash
python -m pip install -e ".[dev]"   # or: pip install pytest
python -m pytest -q
```

Tests exercise the full project → upload → poll → export pipeline against
an in-process fake server; no KiCad or live backend required.

## Packaging & release

```bash
python packaging/build_pcm.py       # -> dist/s2s-kicad-plugin-<version>.zip
```

Pushing a `v*` tag builds the package and publishes it as a GitHub
release asset (see `.github/workflows/release.yml`); that asset URL is
the `download_url` for the KiCad addon-metadata submission.

## License

MIT — see [LICENSE](LICENSE).
