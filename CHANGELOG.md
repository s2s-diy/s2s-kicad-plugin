# Changelog

## 0.1.1

- Fix `SSL: CERTIFICATE_VERIFY_FAILED` on macOS: KiCad's bundled Python
  has no usable CA store, so the client now ships a CA bundle
  (`resources/cacert.pem`) and verifies against it (certifi is used
  instead when the host Python provides it).
- Fix a Cloudflare `403` before requests reach S2S: send an explicit
  `User-Agent` instead of the default `Python-urllib`, which Cloudflare
  blocks.

## 0.1.0

Initial release.

- `Import Circuit Image into KiCad` pcbnew action plugin: pick an image
  (PNG/JPG/WebP), convert it via S2S, and open the generated
  `.kicad_sch` in KiCad.
- Token-only auth (`X-S2S-Key`); token persisted locally at
  `~/.s2s_kicad.json` (`0600`).
- Stdlib-only API client (`s2s_client.py`), unit-tested against a fake
  server.
- KiCad PCM packaging (`packaging/build_pcm.py`) + submission guide.
