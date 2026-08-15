"""Main settings dialog - covers engines, voice, clipboard, exclusion
list, customizable hotkeys, tray behavior, and about/debug info. Built
with wx, the same toolkit NVDA's own settings dialogs and the
"translating" NVDA addon's settings panel use, for proven accessibility.
"""
import wx
import wx.adv

from . import speech
from . import hotkeys as hotkeys_module

REPO_URL = "https://github.com/iqdz/AccessTranslate"
LICENSE_URL = "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html"
CONTACT_EMAIL = "h@shorthickey.com"

LANG_NAMES = {
    "ar": "Arabic", "zh": "Chinese", "cs": "Czech", "da": "Danish",
    "nl": "Dutch", "en": "English", "et": "Estonian", "fi": "Finnish",
    "fr": "French", "de": "German", "el": "Greek", "he": "Hebrew",
    "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian", "ga": "Irish",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "lv": "Latvian",
    "lt": "Lithuanian", "ms": "Malay", "fa": "Persian", "pl": "Polish",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak",
    "sl": "Slovenian", "es": "Spanish", "sv": "Swedish", "tl": "Tagalog",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu",
    "vi": "Vietnamese",
}

ENGINE_CHOICES = [
    ("local_offline", "Local Offline (LibreTranslate)"),
    ("google", "Google Translate"),
    ("deepl", "DeepL"),
    ("bing", "Bing Translate"),
    ("openai", "OpenAI"),
    ("gemini", "Google Gemini"),
    ("openrouter", "OpenRouter"),
]


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, cfg, on_save):
        super().__init__(parent, title="Access-Translate Settings", size=(560, 520))
        self.cfg = cfg
        self.on_save = on_save

        notebook = wx.Notebook(self)
        self.engine_panel = self._build_engine_panel(notebook)
        self.voice_panel = self._build_voice_panel(notebook)
        self.clipboard_panel = self._build_clipboard_panel(notebook)
        self.exclusion_panel = self._build_exclusion_panel(notebook)
        self.hotkeys_panel = self._build_hotkeys_panel(notebook)
        self.tray_panel = self._build_tray_panel(notebook)
        self.about_panel = self._build_about_panel(notebook)

        notebook.AddPage(self.engine_panel, "&Engine")
        notebook.AddPage(self.voice_panel, "&Voice")
        notebook.AddPage(self.clipboard_panel, "&Clipboard")
        notebook.AddPage(self.exclusion_panel, "E&xclusions")
        notebook.AddPage(self.hotkeys_panel, "&Hotkeys")
        notebook.AddPage(self.tray_panel, "&Tray")
        notebook.AddPage(self.about_panel, "A&bout")

        btn_sizer = wx.StdDialogButtonSizer()
        save_btn = wx.Button(self, wx.ID_OK, "&Save")
        save_btn.SetDefault()
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Ca&ncel")
        btn_sizer.AddButton(save_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizer(main_sizer)

        self.Bind(wx.EVT_BUTTON, self._on_save_clicked, id=wx.ID_OK)

    # ------------------------------------------------------------------
    # Engine tab
    # ------------------------------------------------------------------
    def _build_engine_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="Translation &engine:"), 0, wx.LEFT | wx.TOP, 10)
        self._engine_ids = [eid for eid, _label in ENGINE_CHOICES]
        self._custom_apis = list(self.cfg.get("custom_apis", []))
        for i, entry in enumerate(self._custom_apis):
            self._engine_ids.append(f"custom:{i}")
        labels = [label for _eid, label in ENGINE_CHOICES] + [
            f"Custom: {e.get('name', '(unnamed)')}" for e in self._custom_apis
        ]
        self.engine_choice = wx.Choice(panel, choices=labels)
        self._select_current_engine()
        sizer.Add(self.engine_choice, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Target language code (e.g. en, es, fr):"), 0, wx.LEFT, 10)
        self.target_lang_entry = wx.TextCtrl(panel, value=self.cfg.get("target_lang", "en"))
        sizer.Add(self.target_lang_entry, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Local Offline server &URL:"), 0, wx.LEFT, 10)
        self.local_url_entry = wx.TextCtrl(panel, value=self.cfg.get("local_offline_url", ""))
        sizer.Add(self.local_url_entry, 0, wx.EXPAND | wx.ALL, 10)

        api_keys = self.cfg.get("api_keys", {})
        self.api_key_entries = {}
        for key_name, label in [
            ("google", "Google API key (leave blank for free unofficial endpoint)"),
            ("deepl", "DeepL API key"),
            ("bing", "Bing/Azure API key"),
            ("bing_region", "Bing/Azure region"),
            ("openai", "OpenAI API key"),
            ("gemini", "Gemini API key"),
            ("openrouter", "OpenRouter API key"),
        ]:
            sizer.Add(wx.StaticText(panel, label=label + ":"), 0, wx.LEFT, 10)
            style = wx.TE_PASSWORD if "key" in key_name else 0
            entry = wx.TextCtrl(panel, value=api_keys.get(key_name, ""), style=style)
            self.api_key_entries[key_name] = entry
            sizer.Add(entry, 0, wx.EXPAND | wx.ALL, 10)

        add_custom_btn = wx.Button(panel, label="Add &Custom API...")
        add_custom_btn.Bind(wx.EVT_BUTTON, self._on_add_custom_api)
        sizer.Add(add_custom_btn, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    def _select_current_engine(self):
        current = self.cfg.get("engine", "local_offline")
        if current in self._engine_ids:
            self.engine_choice.SetSelection(self._engine_ids.index(current))
        else:
            self.engine_choice.SetSelection(0)

    def _on_add_custom_api(self, evt):
        dlg = CustomApiDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            entry = dlg.get_entry()
            self._custom_apis.append(entry)
            self.cfg["custom_apis"] = self._custom_apis
            idx = len(self._custom_apis) - 1
            self._engine_ids.append(f"custom:{idx}")
            self.engine_choice.Append(f"Custom: {entry['name']}")
            self.engine_choice.SetSelection(len(self._engine_ids) - 1)
        dlg.Destroy()

    # ------------------------------------------------------------------
    # Voice tab
    # ------------------------------------------------------------------
    def _build_voice_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        voice_cfg = self.cfg.get("voice", {})

        try:
            voices = speech.Speaker.list_voices()
        except Exception:
            voices = []
        self._voice_ids = [""] + [v[0] for v in voices]
        voice_labels = ["(system default)"] + [v[1] for v in voices]

        sizer.Add(wx.StaticText(panel, label="Translation &voice:"), 0, wx.LEFT | wx.TOP, 10)
        self.voice_choice = wx.Choice(panel, choices=voice_labels)
        current_voice = voice_cfg.get("voice_id", "")
        idx = self._voice_ids.index(current_voice) if current_voice in self._voice_ids else 0
        self.voice_choice.SetSelection(idx)
        sizer.Add(self.voice_choice, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Rate (-10 to 10):"), 0, wx.LEFT, 10)
        self.rate_spin = wx.SpinCtrl(panel, min=-10, max=10, initial=voice_cfg.get("rate", 0))
        sizer.Add(self.rate_spin, 0, wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Volume (0 to 100):"), 0, wx.LEFT, 10)
        self.volume_spin = wx.SpinCtrl(panel, min=0, max=100, initial=voice_cfg.get("volume", 100))
        sizer.Add(self.volume_spin, 0, wx.ALL, 10)

        self.status_same_voice_check = wx.CheckBox(
            panel,
            label="&Use the same voice for status announcements (e.g. 'translation failed')",
        )
        self.status_same_voice_check.SetValue(voice_cfg.get("status_use_same_voice", True))
        self.status_same_voice_check.Bind(wx.EVT_CHECKBOX, self._on_status_voice_toggle)
        sizer.Add(self.status_same_voice_check, 0, wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Status &voice (when not using the same voice):"), 0, wx.LEFT, 10)
        status_voice = voice_cfg.get("status_voice_id", "")
        status_idx = self._voice_ids.index(status_voice) if status_voice in self._voice_ids else 0
        self.status_voice_choice = wx.Choice(panel, choices=voice_labels)
        self.status_voice_choice.SetSelection(status_idx)
        sizer.Add(self.status_voice_choice, 0, wx.EXPAND | wx.ALL, 10)
        self.status_voice_choice.Enable(not self.status_same_voice_check.GetValue())

        panel.SetSizer(sizer)
        return panel

    def _on_status_voice_toggle(self, evt):
        self.status_voice_choice.Enable(not self.status_same_voice_check.GetValue())

    # ------------------------------------------------------------------
    # Clipboard tab
    # ------------------------------------------------------------------
    def _build_clipboard_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        clip_cfg = self.cfg.get("clipboard", {})

        self.clipboard_enable_check = wx.CheckBox(panel, label="&Copy translation to clipboard")
        self.clipboard_enable_check.SetValue(clip_cfg.get("enabled", False))
        sizer.Add(self.clipboard_enable_check, 0, wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Clipboard &format:"), 0, wx.LEFT, 10)
        self.clipboard_format_radio = wx.RadioBox(
            panel,
            choices=["Translation only", "Original text, then translation"],
            style=wx.RA_SPECIFY_ROWS,
        )
        self.clipboard_format_radio.SetSelection(
            0 if clip_cfg.get("format", "translation_only") == "translation_only" else 1
        )
        sizer.Add(self.clipboard_format_radio, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    # ------------------------------------------------------------------
    # Exclusion list tab
    # ------------------------------------------------------------------
    def _build_exclusion_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="&Never translate these languages, even if detected:"),
            0, wx.LEFT | wx.TOP, 10,
        )
        self._exclusion_codes = sorted(LANG_NAMES.keys(), key=lambda c: LANG_NAMES[c])
        choices = [f"{LANG_NAMES[c]} ({c})" for c in self._exclusion_codes]
        self.exclusion_list = wx.CheckListBox(panel, choices=choices)
        excluded = set(self.cfg.get("excluded_langs", []))
        for i, code in enumerate(self._exclusion_codes):
            if code in excluded:
                self.exclusion_list.Check(i, True)
        sizer.Add(self.exclusion_list, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    # ------------------------------------------------------------------
    # Hotkeys tab - fully customizable, with live conflict checking
    # ------------------------------------------------------------------
    def _build_hotkeys_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        hotkeys_cfg = self.cfg.get("hotkeys", {})

        self.hotkey_entries = {}
        for action, label in hotkeys_module.ACTION_LABELS.items():
            sizer.Add(wx.StaticText(panel, label=label + ":"), 0, wx.LEFT | wx.TOP, 10)
            entry = wx.TextCtrl(
                panel,
                value=hotkeys_cfg.get(action, hotkeys_module.DEFAULT_HOTKEYS.get(action, "")),
            )
            entry.Bind(wx.EVT_TEXT, self._on_hotkey_text_changed)
            self.hotkey_entries[action] = entry
            sizer.Add(entry, 0, wx.EXPAND | wx.ALL, 10)

        self.hotkey_conflict_label = wx.StaticText(panel, label="")
        self.hotkey_conflict_label.SetForegroundColour(wx.Colour(200, 0, 0))
        sizer.Add(self.hotkey_conflict_label, 0, wx.ALL, 10)

        note = wx.StaticText(
            panel,
            label=(
                "Format: modifier+modifier+key, e.g. win+alt+t. Leave a "
                "field blank to disable that hotkey. Changes take effect "
                "after saving (hotkeys are re-registered immediately, no "
                "restart needed)."
            ),
        )
        note.Wrap(500)
        sizer.Add(note, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    def _on_hotkey_text_changed(self, evt):
        current = {action: entry.GetValue() for action, entry in self.hotkey_entries.items()}
        conflicts = hotkeys_module.find_conflicts(current)
        if conflicts:
            lines = [
                f"{hotkeys_module.ACTION_LABELS[a]}  <->  {hotkeys_module.ACTION_LABELS[b]}  (both: {spec})"
                for a, b, spec in conflicts
            ]
            self.hotkey_conflict_label.SetLabel(
                "Conflict - these actions share the same hotkey:\n" + "\n".join(lines)
            )
        else:
            self.hotkey_conflict_label.SetLabel("")
        self.hotkey_conflict_label.Wrap(500)
        self.Layout()

    # ------------------------------------------------------------------
    # Tray tab
    # ------------------------------------------------------------------
    def _build_tray_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.tray_check = wx.CheckBox(panel, label="&Minimize to system tray instead of closing")
        self.tray_check.SetValue(self.cfg.get("minimize_to_tray", False))
        sizer.Add(self.tray_check, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    # ------------------------------------------------------------------
    # About tab
    # ------------------------------------------------------------------
    def _build_about_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            panel,
            label=(
                "Access-Translate\n\n"
                "A free, standalone Windows tray app that translates "
                "whatever text you've selected or copied, and speaks the "
                "result aloud - built accessibility-first for screen "
                "reader users (NVDA, JAWS, Windows Narrator), but useful "
                "to anyone.\n\n"
                "Released under the GNU General Public License v2.\n\n"
                "From Harith to the community."
            ),
        )
        description.Wrap(480)
        sizer.Add(description, 0, wx.ALL, 15)

        repo_link = wx.adv.HyperlinkCtrl(
            panel, wx.ID_ANY, "Access-Translate on GitHub", REPO_URL
        )
        sizer.Add(repo_link, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        license_link = wx.adv.HyperlinkCtrl(
            panel, wx.ID_ANY, "GNU General Public License v2 (GPLv2)", LICENSE_URL
        )
        sizer.Add(license_link, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        contact = wx.StaticText(panel, label=f"Contact Harith: {CONTACT_EMAIL}")
        sizer.Add(contact, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.debug_log_check = wx.CheckBox(
            panel,
            label=(
                "&Write a debug log file (debug.log in the app's "
                "%AppData% configuration folder)"
            ),
        )
        self.debug_log_check.SetValue(self.cfg.get("debug_log_enabled", True))
        sizer.Add(self.debug_log_check, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        debug_log_note = wx.StaticText(
            panel,
            label=(
                "When enabled, a timestamped log of hotkey presses, "
                "clipboard reads, and translation results is written "
                "to disk on each run - useful for diagnosing issues. "
                "Turning this off stops the file from being written; "
                "console output while running from source is "
                "unaffected."
            ),
        )
        debug_log_note.Wrap(480)
        sizer.Add(debug_log_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        panel.SetSizer(sizer)
        return panel

    # ------------------------------------------------------------------
    def _on_save_clicked(self, evt):
        current_hotkeys = {action: entry.GetValue() for action, entry in self.hotkey_entries.items()}
        conflicts = hotkeys_module.find_conflicts(current_hotkeys)
        if conflicts:
            wx.MessageBox(
                "Two or more actions are assigned the same hotkey. "
                "Fix the conflict shown on the Hotkeys tab before saving.",
                "Hotkey conflict",
                wx.OK | wx.ICON_ERROR,
            )
            return  # Dialog stays open - deliberately not calling evt.Skip()

        engine_idx = self.engine_choice.GetSelection()
        self.cfg["engine"] = self._engine_ids[engine_idx]
        self.cfg["target_lang"] = self.target_lang_entry.GetValue().strip()
        self.cfg["local_offline_url"] = self.local_url_entry.GetValue().strip()

        for key_name, entry in self.api_key_entries.items():
            self.cfg.setdefault("api_keys", {})[key_name] = entry.GetValue().strip()

        self.cfg["custom_apis"] = self._custom_apis

        voice_cfg = self.cfg.setdefault("voice", {})
        voice_cfg["voice_id"] = self._voice_ids[self.voice_choice.GetSelection()]
        voice_cfg["rate"] = self.rate_spin.GetValue()
        voice_cfg["volume"] = self.volume_spin.GetValue()
        voice_cfg["status_use_same_voice"] = self.status_same_voice_check.GetValue()
        voice_cfg["status_voice_id"] = self._voice_ids[self.status_voice_choice.GetSelection()]

        clip_cfg = self.cfg.setdefault("clipboard", {})
        clip_cfg["enabled"] = self.clipboard_enable_check.GetValue()
        clip_cfg["format"] = (
            "translation_only" if self.clipboard_format_radio.GetSelection() == 0
            else "original_and_translation"
        )

        self.cfg["excluded_langs"] = [
            self._exclusion_codes[i]
            for i in range(len(self._exclusion_codes))
            if self.exclusion_list.IsChecked(i)
        ]

        hotkeys_cfg = self.cfg.setdefault("hotkeys", {})
        for action, entry in self.hotkey_entries.items():
            hotkeys_cfg[action] = entry.GetValue().strip()

        self.cfg["minimize_to_tray"] = self.tray_check.GetValue()
        self.cfg["debug_log_enabled"] = self.debug_log_check.GetValue()

        self.on_save(self.cfg)
        evt.Skip()


class CustomApiDialog(wx.Dialog):
    """Adds one additional custom API engine beyond the built-in slot -
    the 'Add Custom API' action from the settled plan."""
    def __init__(self, parent):
        super().__init__(parent, title="Add Custom API", size=(420, 300))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="&Name:"), 0, wx.LEFT | wx.TOP, 10)
        self.name_entry = wx.TextCtrl(panel)
        sizer.Add(self.name_entry, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Endpoint URL:"), 0, wx.LEFT, 10)
        self.url_entry = wx.TextCtrl(panel)
        sizer.Add(self.url_entry, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="API &key (optional):"), 0, wx.LEFT, 10)
        self.key_entry = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self.key_entry, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="&Format:"), 0, wx.LEFT, 10)
        self.format_choice = wx.Choice(
            panel, choices=["OpenAI-compatible chat API", "LibreTranslate-compatible"]
        )
        self.format_choice.SetSelection(0)
        sizer.Add(self.format_choice, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "&Add")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Ca&ncel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(sizer)

    def get_entry(self):
        fmt = "openai" if self.format_choice.GetSelection() == 0 else "libretranslate"
        return {
            "name": self.name_entry.GetValue().strip() or "Custom API",
            "url": self.url_entry.GetValue().strip(),
            "api_key": self.key_entry.GetValue().strip(),
            "format": fmt,
        }
