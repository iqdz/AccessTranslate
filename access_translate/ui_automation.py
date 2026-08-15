"""Grabs text from whatever is currently selected, falling back to
whatever's focused, using UI Automation - the same API screen readers
themselves rely on.

Honest scope note (from the project plan discussion): "last read by
the screen reader" is NOT obtainable this way, or any universal way -
that information only exists inside each screen reader's own private
speech queue, with no shared OS-level API for it. This module's scope
is deliberately limited to what UI Automation can see: selection,
focus, and accessible names/values. For NVDA specifically, "translate
the last spoken utterance" is a natural fit for the NVDA addon itself
instead, since it already intercepts everything NVDA says.
"""
import comtypes.client
import win32process
import win32api
import win32con

try:
    import comtypes.gen.UIAutomationClient as UIA
except ImportError:
    comtypes.client.GetModule("UIAutomationCore.dll")
    import comtypes.gen.UIAutomationClient as UIA


class TextReader:
    def __init__(self):
        self.uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=UIA.IUIAutomation,
        )

    def get_selected_or_focused_text(self):
        """Returns (text, app_name).

        Priority order:
        1. Genuine UIA TextPattern selection (works in Notepad, Word, etc.)
        2. Clipboard contents (covers Chrome and other apps that don't
           expose text selection through UIA TextPattern - matches the
           "select it, copy it, then translate" workflow)
        3. Short value of a focused edit field (search boxes, URL bars)
           - LAST resort, not second: in browsers especially, "the
           focused element" is frequently some unrelated toolbar or
           sidebar control (e.g. a Chrome "Ask Gemini" sidebar button)
           that has nothing to do with what's actually selected on the
           page. That makes its Value pattern far less trustworthy
           than something the user has already deliberately copied to
           the clipboard, so clipboard content must be checked first.

        The clipboard fallback is intentional and matches how
        instantTranslate handles browsers: select text, copy it, then
        trigger translation. Having the app read the clipboard
        automatically makes this seamless rather than requiring a
        separate hotkey.
        """
        element = self._get_focused_element()
        app_name = self._get_app_name(element) if element else "unknown"

        if element is not None:
            # 1. Genuine text selection
            text = self._get_selected_text(element)
            if text and text.strip():
                return text.strip(), app_name

        # 2. Clipboard fallback - covers Chrome, Edge, Firefox and any
        # other app where UIA TextPattern selection isn't available.
        # User workflow: select text, Ctrl+C, then press translate hotkey.
        # Checked BEFORE the focused-element value below, since a
        # deliberate manual copy is far more likely to be what the
        # user wants than whatever UI element happens to hold focus.
        try:
            import wx
            from . import debug_log
            if wx.TheClipboard.Open():
                data = wx.TextDataObject()
                got = wx.TheClipboard.GetData(data)
                wx.TheClipboard.Close()
                if got:
                    clip_text = data.GetText().strip()
                    debug_log.log(f"TextReader clipboard fallback found: {clip_text!r}")
                    if clip_text and not clip_text.startswith("http"):
                        return clip_text, app_name
        except Exception as e:
            print(f"Clipboard fallback failed: {e}")

        if element is not None:
            # 3. Short edit field value - last resort only.
            text = self._get_value_text(element)
            if text and text.strip() and len(text.strip()) <= 500:
                stripped = text.strip()
                # Skip bare URLs - not useful to translate
                if not (stripped.startswith("http://") or stripped.startswith("https://")):
                    return stripped, app_name

        return None, app_name

    def _get_focused_element(self):
        try:
            return self.uia.GetFocusedElement()
        except Exception:
            return None

    def _get_app_name(self, element):
        try:
            pid = element.CurrentProcessId
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid,
            )
            try:
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                return exe_path.rsplit("\\", 1)[-1]
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            return "unknown"

    def _get_selected_text(self, element):
        try:
            pattern = element.GetCurrentPattern(UIA.UIA_TextPatternId)
            if pattern is None:
                return None
            text_pattern = pattern.QueryInterface(UIA.IUIAutomationTextPattern)
            selection = text_pattern.GetSelection()
            if selection and selection.Length > 0:
                text_range = selection.GetElement(0)
                text = text_range.GetText(-1)
                if text and text.strip():
                    return text.strip()
        except Exception:
            pass
        return None

    def _get_value_text(self, element):
        try:
            pattern = element.GetCurrentPattern(UIA.UIA_ValuePatternId)
            if pattern is None:
                return None
            value_pattern = pattern.QueryInterface(UIA.IUIAutomationValuePattern)
            value = value_pattern.CurrentValue
            if value and value.strip():
                return value.strip()
        except Exception:
            pass
        return None

    def _get_document_text(self, element):
        try:
            pattern = element.GetCurrentPattern(UIA.UIA_TextPatternId)
            if pattern is None:
                return None
            text_pattern = pattern.QueryInterface(UIA.IUIAutomationTextPattern)
            text_range = text_pattern.DocumentRange
            text = text_range.GetText(-1)
            if text and text.strip():
                return text.strip()
        except Exception:
            pass
        return None
