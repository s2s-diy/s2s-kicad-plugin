# Publishing the plugin to KiCad's Plugin & Content Manager (PCM)

Getting the plugin into KiCad's built-in **Plugin & Content Manager** is
the primary discovery channel — users find it by searching "import
image" inside KiCad, where the need already exists.

## 1. Build the package

```bash
python3 packaging/build_pcm.py
```

This writes `dist/s2s-kicad-plugin-<version>.zip` (layout below) and
prints the `download_sha256`, `download_size`, and `install_size` you
need in step 3.

```
metadata.json          # packaged metadata (no download_* fields)
plugins/               # action plugin python (imported by KiCad)
resources/icon.png     # 64x64, shown in the Content Manager
```

## 2. Host the zip at a stable URL

Attach the zip to a **GitHub release** of this repo (or any stable
host). The public asset URL becomes the `download_url` in step 3. Never
move or overwrite a released zip — the repo entry pins its sha256.

## 3. Submit to the KiCad addon-metadata repository

The official PCM index is built from
<https://gitlab.com/kicad/addons/metadata>. Open a merge request that adds:

```
packages/com.s2s.kicad.import-circuit-image/metadata.json
packages/com.s2s.kicad.import-circuit-image/resources/icon.png
```

The repo `metadata.json` is the packaged one plus a fully-populated
`versions[]` entry — paste the block the build script printed and set
`download_url`:

```json
{
  "version": "0.1.0",
  "status": "development",
  "kicad_version": "7.0",
  "download_url": "https://github.com/s2s-diy/<repo>/releases/download/kicad-plugin-v0.1.0/s2s-kicad-plugin-0.1.0.zip",
  "download_sha256": "<from build script>",
  "download_size": <from build script>,
  "install_size": <from build script>
}
```

KiCad maintainers review the MR; once merged the plugin appears in every
user's Plugin & Content Manager. Each new release = a new `versions[]`
entry (append, never edit a published one) + a new hosted zip.

## 4. Meanwhile — manual install

Until the MR merges, users install by copying `s2s_kicad/` into their
KiCad 3rd-party plugins directory (see the top-level README and
`/docs/kicad-plugin/`).

## Notes

- Icon: `s2s_kicad/resources/icon.png` (64x64), generated from the brand
  logo. Replace with a purpose-drawn icon before wide release if desired.
- `status` should move `development` → `stable` once the token flow and
  conversion quality are validated with external users.
