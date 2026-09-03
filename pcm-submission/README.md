# KiCad PCM submission (ready to open the MR)

Everything needed to list the plugin in KiCad's **Plugin & Content
Manager** is prepared and pre-validated here:

```
packages/com.s2s.kicad.import-circuit-image/
  metadata.json           # repo format, real v0.1.1 release URL + sha256 + sizes
  resources/icon.png      # 64x64 catalog icon
```

- Points at the published release asset:
  `https://github.com/s2s-diy/s2s-kicad-plugin/releases/download/v0.1.1/s2s-kicad-plugin-0.1.1.zip`
- `download_sha256` `68ecbd155af89e110345b077224e970d16888c42f2078f43166ea73ebbc7f0e7`,
  `download_size` 174463, `install_size` 300606.
- **Validated against KiCad's PCM schema** (`https://go.kicad.org/pcm/schemas/v1`).

## Open the merge request (needs a GitLab account)

The KiCad addon index lives on GitLab, so this last step is done under
your GitLab identity — it can't be automated from here.

1. On GitLab, **fork** <https://gitlab.com/kicad/addons/metadata>.
2. Clone your fork and make a branch (not `main` — CI needs a branch):
   ```bash
   git clone git@gitlab.com:<you>/metadata.git
   cd metadata
   git checkout -b add-s2s-import-circuit-image
   ```
3. Copy the prepared package in:
   ```bash
   cp -R <path-to>/s2s-kicad-plugin/pcm-submission/packages/com.s2s.kicad.import-circuit-image \
         packages/
   ```
4. Commit and push to your fork:
   ```bash
   git add packages/com.s2s.kicad.import-circuit-image
   git commit -m "Add com.s2s.kicad.import-circuit-image 0.1.1"
   git push -u origin add-s2s-import-circuit-image
   ```
   The push runs GitLab CI validation on your fork (CI/CD → Pipelines).
5. Open a **merge request** from your branch to `kicad/addons/metadata` `main`.
   KiCad maintainers review; on merge the plugin appears in everyone's PCM.

## Updating later

Bump the plugin (`packaging/build_pcm.py`), tag `vX.Y.Z` (release workflow
publishes the zip), then regenerate this `metadata.json` — append a new
entry to `versions[]` with the new URL/sha256/sizes (never edit a
published one) and open another MR.
