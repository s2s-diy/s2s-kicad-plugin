"""KiCad action plugin: "Import Circuit Image into KiCad".

Registered in pcbnew's plugin menu. Leads with the task, not the brand:
the user picks an image, it is converted by S2S, and the resulting
``.kicad_sch`` is saved next to the board and opened in eeschema. S2S
branding + the "edit/simulate online" link appear only after the file
is delivered.

This module imports ``pcbnew``/``wx`` and therefore only loads inside
KiCad. All network logic lives in :mod:`s2s_client`, which stays
importable (and testable) on its own.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

import pcbnew  # type: ignore
import wx  # type: ignore

from .s2s_client import DEFAULT_BASE_URL, S2SClient, S2SError

_SETTINGS_BASE_URL = os.environ.get("S2S_PLUGIN_BASE_URL", DEFAULT_BASE_URL)
_WILDCARD = "Circuit images (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp"
_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".s2s_kicad.json")


def _load_token() -> str:
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh).get("api_token", "")
    except (OSError, ValueError):
        return ""


def _save_token(token: str) -> None:
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump({"api_token": token}, fh)
        os.chmod(_CONFIG_PATH, 0o600)  # token is a credential — keep it private
    except OSError:
        pass


class S2SImportPlugin(pcbnew.ActionPlugin):
    def defaults(self) -> None:
        self.name = "Import Circuit Image into KiCad (S2S)"
        self.category = "Import"
        self.description = "Turn a photo, screenshot, or scan of a circuit into an editable KiCad schematic."
        self.show_toolbar_button = True
        icon = os.path.join(os.path.dirname(__file__), "resources", "icon.png")
        if os.path.exists(icon):
            self.icon_file_name = icon

    def Run(self) -> None:
        frame = _top_window()
        dlg = _ImportDialog(frame, base_url=_SETTINGS_BASE_URL)
        dlg.ShowModal()
        dlg.Destroy()


class _ImportDialog(wx.Dialog):
    def __init__(self, parent, base_url: str) -> None:
        super().__init__(parent, title="Import Circuit Image → KiCad", size=(460, 300))
        self.base_url = base_url
        self._sch_text = None
        self._filename = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="1. Paste your S2S API token"), 0, wx.ALL, 6
        )
        hint = wx.StaticText(
            panel,
            label=f"Generate one at {self.base_url} → Dashboard → API tokens",
        )
        hint.SetForegroundColour(wx.Colour(120, 120, 120))
        sizer.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.token = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=_load_token())
        sizer.Add(_labeled(panel, "Token", self.token), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        sizer.Add(wx.StaticText(panel, label="2. Choose a circuit image"), 0, wx.ALL, 6)
        self.file_picker = wx.FilePickerCtrl(panel, wildcard=_WILDCARD)
        sizer.Add(self.file_picker, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        self.status = wx.StaticText(panel, label="")
        sizer.Add(self.status, 0, wx.ALL, 6)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.convert_btn = wx.Button(panel, label="Convert to schematic")
        self.convert_btn.Bind(wx.EVT_BUTTON, self._on_convert)
        cancel = wx.Button(panel, id=wx.ID_CANCEL, label="Close")
        btns.Add(self.convert_btn, 0, wx.RIGHT, 6)
        btns.Add(cancel, 0)
        sizer.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 6)

        panel.SetSizer(sizer)

    def _set_status(self, msg: str) -> None:
        wx.CallAfter(self.status.SetLabel, msg)

    def _on_convert(self, _evt) -> None:
        token = self.token.GetValue().strip()
        if not token:
            wx.MessageBox("Paste your S2S API token first.", "S2S", wx.OK | wx.ICON_INFORMATION)
            return
        image = self.file_picker.GetPath()
        if not image:
            wx.MessageBox("Pick a circuit image first.", "S2S", wx.OK | wx.ICON_INFORMATION)
            return
        _save_token(token)  # remember it so the user pastes once
        self.convert_btn.Disable()
        threading.Thread(target=self._worker, args=(image, token), daemon=True).start()

    def _worker(self, image: str, token: str) -> None:
        try:
            client = S2SClient(base_url=self.base_url, api_key=token, timeout=120)
            filename, content = client.convert_image_to_kicad(image, on_progress=self._set_status)
        except S2SError as exc:
            wx.CallAfter(self._fail, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — surface anything to the user
            wx.CallAfter(self._fail, f"Unexpected error: {exc}")
            return
        wx.CallAfter(self._deliver, image, filename, content)

    def _fail(self, msg: str) -> None:
        self.status.SetLabel("❌ " + msg)
        self.convert_btn.Enable()

    def _deliver(self, image: str, filename: str, content: str) -> None:
        out_path = os.path.join(os.path.dirname(image), filename)
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            self._fail(f"Could not save schematic: {exc}")
            return
        self.status.SetLabel(f"✅ Saved {os.path.basename(out_path)} — converted by S2S")
        self.convert_btn.Enable()
        if wx.MessageBox(
            f"Schematic saved to:\n{out_path}\n\nOpen it in KiCad now?\n\n"
            "Tip: edit and simulate this circuit online at s2s.diy",
            "Converted by S2S",
            wx.YES_NO | wx.ICON_INFORMATION,
        ) == wx.YES:
            _open_in_kicad(out_path)


def _labeled(parent, label: str, ctrl) -> wx.BoxSizer:
    row = wx.BoxSizer(wx.HORIZONTAL)
    row.Add(wx.StaticText(parent, label=label, size=(70, -1)), 0, wx.ALIGN_CENTER_VERTICAL)
    row.Add(ctrl, 1)
    return row


def _top_window():
    for w in wx.GetTopLevelWindows():
        if w.IsShown():
            return w
    return None


def _open_in_kicad(sch_path: str) -> None:
    """Open the generated schematic in eeschema via the OS handler."""
    try:
        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", sch_path])
        elif os.name == "nt":
            os.startfile(sch_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", sch_path])
    except Exception:  # noqa: BLE001 — opening is best-effort
        pass
