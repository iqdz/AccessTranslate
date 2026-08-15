"""First-run dialog: shown once, the first time Access-Translate runs,
detected by the config file not existing yet. Offers to create a
desktop shortcut - offered, not forced, matching Shorthickey's own
proven first-run pattern.
"""
import os
import sys
import wx

from . import hotkeys as hotkeys_module


class FirstRunDialog(wx.Dialog):
    def __init__(self, parent=None, hotkeys_cfg=None):
        super().__init__(parent, title="Welcome to Access-Translate", size=(440, 240))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Pull the actual configured (or default) translate hotkey
        # rather than hardcoding a string here - hardcoding is exactly
        # how this message went stale before (it said "Win+Alt+T" long
        # after the real default had changed to Shift+Win+F1).
        hotkeys_cfg = hotkeys_cfg or {}
        translate_spec = hotkeys_cfg.get(
            "translate", hotkeys_module.DEFAULT_HOTKEYS.get("translate", "")
        )
        display_hotkey = _format_hotkey_for_display(translate_spec)

        intro = wx.StaticText(
            panel,
            label=(
                "Access-Translate is ready to use.\n\n"
                f"Press {display_hotkey} anywhere to translate selected or "
                "focused text - the result is spoken aloud and, if "
                "enabled, copied to the clipboard. Open Settings any "
                "time from the system tray (if enabled) or the desktop "
                "shortcut below."
            ),
        )
        intro.Wrap(400)
        sizer.Add(intro, 0, wx.ALL, 15)

        self.shortcut_checkbox = wx.CheckBox(panel, label="&Create a desktop shortcut")
        self.shortcut_checkbox.SetValue(True)
        sizer.Add(self.shortcut_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Get Started")
        ok_btn.SetDefault()
        btn_sizer.AddButton(ok_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(sizer)

    def wants_shortcut(self):
        return self.shortcut_checkbox.GetValue()


def _format_hotkey_for_display(spec):
    """'shift+win+f1' -> 'Shift+Win+F1' - just title-cases each part
    for a readable message, without needing to re-parse/validate."""
    if not spec:
        return "your configured hotkey (see Settings > Hotkeys)"
    return "+".join(part.capitalize() for part in spec.split("+"))


def create_desktop_shortcut():
    """Creates a .lnk shortcut to the running exe on the user's Desktop."""
    try:
        import win32com.client
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "Access-Translate.lnk")
        target = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = os.path.dirname(target)
        shortcut.IconLocation = target
        shortcut.Description = "Access-Translate"
        shortcut.save()
        return True
    except Exception as e:
        print(f"Could not create desktop shortcut: {e}")
        return False
