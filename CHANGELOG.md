# Changelog

## 0.1.0 (unreleased)

Initial release.

- `Import Circuit Image into KiCad` pcbnew action plugin: pick an image
  (PNG/JPG/WebP), convert it via S2S, and open the generated
  `.kicad_sch` in KiCad.
- Token-only auth (`X-S2S-Key`); token persisted locally at
  `~/.s2s_kicad.json` (`0600`).
- Stdlib-only API client (`s2s_client.py`), unit-tested against a fake
  server.
- KiCad PCM packaging (`packaging/build_pcm.py`) + submission guide.
