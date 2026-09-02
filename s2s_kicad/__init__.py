"""S2S KiCad plugin package.

KiCad discovers action plugins by importing this package and looking for
a registered ``ActionPlugin``. Importing :mod:`action` pulls in
``pcbnew``/``wx``, so guard it: outside KiCad (e.g. unit tests importing
``s2s_client``) the import fails softly and only the network client is
available.
"""

from __future__ import annotations

try:  # pragma: no cover — only succeeds inside KiCad
    from .action import S2SImportPlugin

    S2SImportPlugin().register()
except Exception:  # noqa: BLE001 — no pcbnew/wx outside KiCad
    pass
