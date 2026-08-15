"""Access-Translate entry point.

A hidden main window that:
 - registers customizable global hotkeys (defaults: Win+Alt+T/S/G/C)
 - shows the settings dialog on request
 - optionally lives in the system tray (off by default)
 - grabs selected/focused text via UI Automation, translates it
   through the configured engine, speaks it via SAPI, and optionally
   copies it to the clipboard

Copyright (C) 2026. Licensed under GPLv2 - see LICENSE.
"""
import time
import wx

from . import config as cfg_module
from . import engines
from . import cache
from . import lang_detect
from . import debug_log
from .speech import Speaker
from .ui_automation import TextReader
from .hotkeys import parse_hotkey, DEFAULT_HOTKEYS
from .settings_dialog import SettingsDialog
from .tray_icon import AppTrayIcon
from .first_run_dialog import FirstRunDialog, create_desktop_shortcut

HOTKEY_ID_TRANSLATE = 1
HOTKEY_ID_SWAP = 2
HOTKEY_ID_REVERT = 3
HOTKEY_ID_CLEAR_CACHE = 4
HOTKEY_ID_SETTINGS = 5
HOTKEY_ID_STOP_SPEECH = 6

_ACTION_TO_ID = {
    "translate": HOTKEY_ID_TRANSLATE,
    "swap": HOTKEY_ID_SWAP,
    "revert": HOTKEY_ID_REVERT,
    "clear_cache": HOTKEY_ID_CLEAR_CACHE,
    "settings": HOTKEY_ID_SETTINGS,
    "stop_speech": HOTKEY_ID_STOP_SPEECH,
}

DOUBLE_PRESS_WINDOW = 0.5  # seconds - clear-cache single vs double press


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Access-Translate", size=(1, 1))
        self.cfg = cfg_module.load_config()

        self.reader = TextReader()
        self.speaker = self._build_speaker()
        self.status_speaker = self._build_status_speaker()

        self.last_source_lang = None
        self.default_target_lang = self.cfg.get("target_lang", "en")
        self.temp_target_lang = None  # session-only override from the swap hotkey

        self._last_clear_press_time = 0.0
        self._last_translate_time = 0.0
        # Tracks the last text WE wrote to the system clipboard (only
        # set when "copy result to clipboard" is enabled - see
        # _copy_to_clipboard). Lets translate_now() recognize when a
        # synthetic Ctrl+C found nothing new selected and is just
        # reading back our own previous output, instead of feeding it
        # back through translation again.
        self._last_written_clipboard_text = None
        self._registered_hotkey_ids = set()

        self.tray_icon = None
        self._apply_tray_setting()

        self._register_hotkeys()
        self.Bind(wx.EVT_HOTKEY, self._on_hotkey)

        # Fully hidden - no normal visible window, only the settings
        # dialog opened on demand and (optionally) a tray icon.
        self.Hide()

    # ------------------------------------------------------------------
    def _build_speaker(self):
        voice_cfg = self.cfg.get("voice", {})
        return Speaker(
            voice_id=voice_cfg.get("voice_id", ""),
            rate=voice_cfg.get("rate", 0),
            volume=voice_cfg.get("volume", 100),
        )

    def _build_status_speaker(self):
        voice_cfg = self.cfg.get("voice", {})
        if voice_cfg.get("status_use_same_voice", True):
            return self.speaker
        return Speaker(
            voice_id=voice_cfg.get("status_voice_id", ""),
            rate=voice_cfg.get("status_rate", 0),
            volume=voice_cfg.get("volume", 100),
        )

    def _apply_tray_setting(self):
        # The tray icon is ALWAYS created - it is the only way to open
        # settings and quit when the app is running headlessly (no visible
        # window). The "minimize_to_tray" setting only controls whether
        # closing/minimizing the settings dialog hides to tray (True) or
        # just closes that dialog while the app keeps running (False).
        if self.tray_icon is None:
            self.tray_icon = AppTrayIcon(
                on_open_settings=self.open_settings,
                on_revert_target=self.revert_target_language,
                on_quit=self.quit_app,
            )

    # ------------------------------------------------------------------
    # Hotkeys - fully customizable via settings, re-registered live on
    # save with no restart required.
    # ------------------------------------------------------------------
    def _register_hotkeys(self):
        hotkeys_cfg = self.cfg.get("hotkeys", {})
        for action, hotkey_id in _ACTION_TO_ID.items():
            if hotkey_id in self._registered_hotkey_ids:
                continue  # already registered, skip to prevent duplicate
            spec = hotkeys_cfg.get(action, DEFAULT_HOTKEYS.get(action, ""))
            modifiers, key = parse_hotkey(spec)
            if key is None:
                debug_log.log(f"Hotkey for '{action}' is blank/disabled, skipping.")
                continue  # blank/disabled hotkey
            ok = self.RegisterHotKey(hotkey_id, modifiers, key)
            debug_log.log(
                f"RegisterHotKey(id={hotkey_id}, action='{action}', "
                f"spec='{spec}', modifiers={modifiers}, key={key}) -> {ok}"
            )
            if ok:
                self._registered_hotkey_ids.add(hotkey_id)
            else:
                print(
                    f"Could not register hotkey '{spec}' for {action} - "
                    "it may already be in use by another app. "
                    "Change it in Settings > Hotkeys."
                )

    def _unregister_hotkeys(self):
        for hotkey_id in list(self._registered_hotkey_ids):
            self.UnregisterHotKey(hotkey_id)
        self._registered_hotkey_ids.clear()

    def _on_hotkey(self, evt):
        hotkey_id = evt.GetId()
        debug_log.log(f"HOTKEY EVENT RECEIVED: id={hotkey_id}")
        if hotkey_id == HOTKEY_ID_TRANSLATE:
            debug_log.log("  -> dispatching to translate_now()")
            self.translate_now()
        elif hotkey_id == HOTKEY_ID_SWAP:
            debug_log.log("  -> dispatching to swap_target_language()")
            self.swap_target_language()
        elif hotkey_id == HOTKEY_ID_REVERT:
            debug_log.log("  -> dispatching to revert_target_language()")
            self.revert_target_language()
        elif hotkey_id == HOTKEY_ID_CLEAR_CACHE:
            debug_log.log("  -> dispatching to _on_clear_cache_hotkey()")
            self._on_clear_cache_hotkey()
        elif hotkey_id == HOTKEY_ID_SETTINGS:
            debug_log.log("  -> dispatching to open_settings()")
            self.open_settings()
        elif hotkey_id == HOTKEY_ID_STOP_SPEECH:
            debug_log.log("  -> dispatching to stop_speech()")
            self.stop_speech()
        else:
            debug_log.log(f"  -> UNKNOWN hotkey id, no handler matched: {hotkey_id}")

    # ------------------------------------------------------------------
    # Core action: translate whatever is selected/focused
    # ------------------------------------------------------------------
    def stop_speech(self):
        """Immediately silences any ongoing SAPI speech (both the main
        translation voice and the status-message voice), without
        affecting anything already copied to the clipboard or cached.
        Meant for long translations: stop listening partway through,
        paste the (already-complete) translation into a text file,
        and read it with the screen reader instead."""
        debug_log.log("stop_speech() called - silencing both voices")
        self.speaker.stop()
        self.status_speaker.stop()

    def translate_now(self):
        import time
        now = time.time()
        debug_log.log(f"translate_now() called at {now}")
        if now - self._last_translate_time < 0.8:
            debug_log.log(
                f"  -> debounced (only {now - self._last_translate_time:.3f}s "
                "since last call), returning without action"
            )
            return
        self._last_translate_time = now

        # PRIMARY PATH: ask TextReader for whatever's selected/focused.
        # It already tries, in order: (1) genuine UI Automation text
        # selection - works in Notepad, Word, etc. without touching
        # the clipboard at all, (2) a focused edit field's value, (3)
        # falling back to whatever's currently on the clipboard as-is.
        # That third tier is exactly the "select it, copy it yourself,
        # then press the hotkey" workflow browsers need - especially
        # with a screen reader's own virtual cursor/browse-mode
        # involved, where a synthetic Ctrl+C we send often doesn't act
        # on the same selection the user actually made. Trusting this
        # directly, instead of discarding it and re-deriving our own
        # (much less reliable) copy of "what's selected" via a
        # synthetic Ctrl+C, is the fix.
        text, app_name = self.reader.get_selected_or_focused_text()
        app_name = app_name or "unknown"
        debug_log.log(f"  -> TextReader: text={text!r} app_name='{app_name}'")

        # Guard against re-translating our own last output (e.g. if
        # "copy result to clipboard" is on and nothing new has been
        # copied since).
        if (
            text
            and text.strip()
            and self._last_written_clipboard_text is not None
            and text.strip() == self._last_written_clipboard_text
        ):
            debug_log.log(
                "  -> TextReader result matches Access-Translate's own "
                "last output - treating as no new selection"
            )
            text = None

        if not text or not text.strip():
            # FALLBACK: nothing selected via UIA and nothing usable on
            # the clipboard yet. Try one synthetic Ctrl+C as a last
            # resort - this mainly helps apps with neither real UIA
            # text selection nor a prior manual copy. Not relied on as
            # the primary mechanism anymore since it's inherently less
            # reliable (blocked by UIPI when elevated, ignored while a
            # screen reader's own input hooks are active, etc.).
            debug_log.log("  -> nothing usable yet, trying synthetic Ctrl+C as fallback")
            old_clip = self._read_clipboard_raw()
            debug_log.log(f"  -> clipboard BEFORE synthetic Ctrl+C: {old_clip!r}")
            self._copy_selection_to_clipboard()
            new_clip = self._read_clipboard_raw()
            debug_log.log(f"  -> clipboard AFTER synthetic Ctrl+C: {new_clip!r}")

            if (
                new_clip
                and new_clip.strip()
                and (
                    self._last_written_clipboard_text is None
                    or new_clip.strip() != self._last_written_clipboard_text
                )
            ):
                text = new_clip.strip()
            else:
                text = None

        debug_log.log(f"  -> FINAL text to translate from '{app_name}': {text!r}")

        if not text or not text.strip():
            debug_log.log("  -> speaking status_speaker: 'No text found...'")
            self.status_speaker.speak(
                "No text found. Select text first then press the translate hotkey."
            )
            return

        stripped = text.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            debug_log.log("  -> speaking status_speaker: 'Selected text appears to be a URL.'")
            self.status_speaker.speak("Selected text appears to be a URL.")
            return

        target_lang = self.temp_target_lang or self.default_target_lang
        detected = lang_detect.detect(stripped)
        excluded = set(self.cfg.get("excluded_langs", []))
        if detected in excluded:
            self.status_speaker.speak("This language is excluded from translation.")
            return

        cached = cache.get(app_name, stripped)
        if cached:
            self._emit_result(stripped, cached)
            return

        import threading
        cfg_snapshot = dict(self.cfg)
        threading.Thread(
            target=self._translate_in_background,
            args=(stripped, app_name, target_lang, detected, cfg_snapshot),
            daemon=True,
        ).start()

    def _read_clipboard_raw(self):
        """Reads current clipboard text, or None if clipboard has no
        text or can't be opened."""
        try:
            if wx.TheClipboard.Open():
                try:
                    # Skip the IsSupported() pre-check - across wxPython
                    # versions it's been inconsistent about whether it
                    # wants a raw DF_* id or a wx.DataFormat object, and
                    # getting that wrong throws before we ever read
                    # anything. GetData() on a mismatched/empty
                    # clipboard just returns False, which is all the
                    # signal we need.
                    data = wx.TextDataObject()
                    if wx.TheClipboard.GetData(data):
                        return data.GetText()
                    return None
                finally:
                    wx.TheClipboard.Close()
        except Exception as e:
            print(f"Clipboard read failed: {e}")
        return None

    def _copy_selection_to_clipboard(self):
        """Simulate Ctrl+C to copy whatever is selected in the active
        app to the clipboard before we try to read it. Pure ctypes
        SendInput - no extra dependencies."""
        try:
            import ctypes
            import time as _time
            INPUT_KEYBOARD = 1
            KEYEVENTF_KEYUP = 0x0002
            VK_CONTROL = 0x11
            VK_C = 0x43

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                ]

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", ctypes.c_long),
                    ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                ]

            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [
                    ("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort),
                ]

            class INPUT(ctypes.Structure):
                # The union MUST include mi/hi, not just ki - Windows'
                # real INPUT struct is sized to fit the largest member
                # (MOUSEINPUT). Omitting them makes ctypes.sizeof(INPUT)
                # here (32 bytes) smaller than what user32.dll actually
                # expects (40 bytes on 64-bit Windows). SendInput then
                # walks the array using the wrong stride, so every
                # event after the first reads misaligned/garbage
                # memory - explaining why the synthetic Ctrl+C worked
                # unreliably instead of either always or never.
                class _INPUT(ctypes.Union):
                    _fields_ = [
                        ("ki", KEYBDINPUT),
                        ("mi", MOUSEINPUT),
                        ("hi", HARDWAREINPUT),
                    ]
                _anonymous_ = ("_input",)
                _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]

            def make_key(vk, flags=0):
                i = INPUT()
                i.type = INPUT_KEYBOARD
                i.ki.wVk = vk
                i.ki.dwFlags = flags
                return i

            inputs = [
                make_key(VK_CONTROL),
                make_key(VK_C),
                make_key(VK_C, KEYEVENTF_KEYUP),
                make_key(VK_CONTROL, KEYEVENTF_KEYUP),
            ]
            arr = (INPUT * len(inputs))(*inputs)

            # Log which window actually has OS input focus right now.
            # SendInput delivers to the foreground window - if this
            # doesn't match the app you think you're copying from
            # (e.g. it's still the terminal, or a UAC/other dialog),
            # that alone explains a failed/wrong copy.
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                debug_log.log(f"  -> foreground window at Ctrl+C time: hwnd={hwnd} title={buf.value!r}")
            except Exception as e:
                debug_log.log(f"  -> could not read foreground window: {e}")

            ctypes.windll.kernel32.SetLastError(0)
            sent = ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
            if sent != len(inputs):
                err = ctypes.windll.kernel32.GetLastError()
                debug_log.log(
                    f"  -> SendInput only queued {sent}/{len(inputs)} events! "
                    f"GetLastError()={err} (5=ERROR_ACCESS_DENIED often means "
                    "UIPI blocked input to an elevated/higher-privilege window - "
                    "try running Access-Translate WITHOUT Administrator rights)"
                )
            else:
                debug_log.log(f"  -> SendInput queued all {sent} events successfully")
            _time.sleep(0.15)
        except Exception as e:
            debug_log.log(f"Ctrl+C simulation failed: {e}")

    def _translate_in_background(self, text, app_name, target_lang, detected, cfg):
        try:
            translated = engines.translate(text, target_lang, detected, cfg)
        except Exception as e:
            print(f"Engine exception: {e}")
            translated = None

        wx.CallAfter(self._on_translation_result, text, app_name, detected, translated)

    def _on_translation_result(self, original_text, app_name, detected, translated):
        """Called on the main wx thread once the background translation
        finishes. Safe to call SAPI and wx.TheClipboard from here."""
        debug_log.log(
            f"_on_translation_result: original={original_text!r} "
            f"translated={translated!r} detected={detected!r}"
        )
        if not translated:
            debug_log.log(f"  -> translation FAILED (engine returned None) for: {original_text!r}")
            self.status_speaker.speak(
                "Translation failed. Check that the selected engine "
                "and, if using offline mode, the local translation "
                "service is running."
            )
            return

        # Normalise whitespace for the "already in target language" check
        if translated.strip().lower() == original_text.strip().lower():
            debug_log.log(f"  -> no-op (same text returned): {original_text!r}")
            self.status_speaker.speak("Already in target language.")
            return

        cache.put(app_name, original_text, translated)
        if detected != "auto":
            self.last_source_lang = detected
        debug_log.log(f"  -> speaking translated result: {translated!r}")
        self._emit_result(original_text, translated)

    def _emit_result(self, original_text, translated_text):
        debug_log.log(f"  -> self.speaker.speak({translated_text!r})")
        self.speaker.speak(translated_text)

        clip_cfg = self.cfg.get("clipboard", {})
        if clip_cfg.get("enabled", False):
            if clip_cfg.get("format", "translation_only") == "original_and_translation":
                clip_text = f"{original_text}\n{translated_text}"
            else:
                clip_text = translated_text
            self._copy_to_clipboard(clip_text)

    def _copy_to_clipboard(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            self._last_written_clipboard_text = text.strip() if text else None

    # ------------------------------------------------------------------
    # Swap / revert target language
    # ------------------------------------------------------------------
    def swap_target_language(self):
        if not self.last_source_lang:
            self.status_speaker.speak("No previous translation to swap with yet.")
            return
        self.temp_target_lang = self.last_source_lang
        self.status_speaker.speak(f"Target language temporarily set to {self.last_source_lang}.")

    def revert_target_language(self):
        self.temp_target_lang = None
        self.status_speaker.speak("Target language reverted to default.")

    # ------------------------------------------------------------------
    # Clear cache: single press = current app, double press = everything
    # ------------------------------------------------------------------
    def _on_clear_cache_hotkey(self):
        now = time.time()
        debug_log.log(f"_on_clear_cache_hotkey() called at {now}")
        if now - self._last_clear_press_time <= DOUBLE_PRESS_WINDOW:
            cache.clear_all()
            debug_log.log("  -> double-press detected: cleared ALL app caches")
            self.status_speaker.speak("Cleared translation cache for all apps.")
            self._last_clear_press_time = 0.0
        else:
            self._last_clear_press_time = now
            debug_log.log("  -> single press so far, arming finalize timer")
            wx.CallLater(int(DOUBLE_PRESS_WINDOW * 1000) + 50, self._finalize_single_clear, now)

    def _finalize_single_clear(self, press_time):
        debug_log.log(f"_finalize_single_clear(press_time={press_time}) firing")
        if self._last_clear_press_time != press_time:
            debug_log.log("  -> superseded by a second press, doing nothing")
            return  # a second press already handled it as "clear all"
        _text, app_name = self.reader.get_selected_or_focused_text()
        cache.clear_app(app_name or "unknown")
        debug_log.log(f"  -> cleared cache for app '{app_name or 'unknown'}', speaking now")
        self.status_speaker.speak("Cleared translation cache for the current app.")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def open_settings(self):
        dlg = SettingsDialog(self, self.cfg, on_save=self._on_settings_saved)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_settings_saved(self, new_cfg):
        cfg_module.save_config(new_cfg)
        self.cfg = new_cfg
        self.default_target_lang = new_cfg.get("target_lang", "en")
        self.temp_target_lang = None  # a saved config change resets any temporary swap
        self.speaker = self._build_speaker()
        self.status_speaker = self._build_status_speaker()
        self._unregister_hotkeys()
        self._register_hotkeys()
        self._apply_tray_setting()
        debug_log.set_enabled(new_cfg.get("debug_log_enabled", True))

    def quit_app(self):
        self._unregister_hotkeys()
        if self.tray_icon is not None:
            self.tray_icon.Destroy()
        self.Destroy()


def main():
    # Load config once, early, just to read the debug-log preference
    # before anything else happens - so hotkey registration and other
    # early startup events are captured in the log file, not just
    # console prints. MainFrame() below re-loads config normally.
    _early_cfg = cfg_module.load_config()
    debug_log.init_log(enabled=_early_cfg.get("debug_log_enabled", True))

    app = wx.App(False)
    frame = MainFrame()

    if not frame.cfg.get("first_run_complete", False):
        dlg = FirstRunDialog(frame, hotkeys_cfg=frame.cfg.get("hotkeys", {}))
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.wants_shortcut():
                create_desktop_shortcut()
        dlg.Destroy()
        frame.cfg["first_run_complete"] = True
        cfg_module.save_config(frame.cfg)
        frame.open_settings()

    app.MainLoop()


if __name__ == "__main__":
    main()
