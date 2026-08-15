"""Parses hotkey strings like 'win+alt+t' into (modifiers, keycode)
pairs for use with wx.Frame.RegisterHotKey, and validates a full set
of hotkeys for conflicts before they get applied.

Hotkeys are fully customizable from the app's own Settings > Hotkeys
tab - these are just the defaults from the project plan, stored in
config and editable there, not hardcoded elsewhere.
"""
import wx

DEFAULT_HOTKEYS = {
    "translate": "shift+win+f1",
    "swap": "shift+win+f2",
    "revert": "shift+win+f3",
    "clear_cache": "shift+win+f5",
    "settings": "shift+win+f6",
    "stop_speech": "pause",
}

ACTION_LABELS = {
    "translate": "Translate selected/focused text",
    "swap": "Swap target to last source language",
    "revert": "Revert target to default",
    "clear_cache": "Clear cache (once = current app, twice = all)",
    "settings": "Open settings window",
    "stop_speech": "Stop/silence speech immediately",
}


def parse_hotkey(spec):
    """'win+alt+t' -> (wx.MOD_WIN | wx.MOD_ALT, ord('T')) or (0, None)
    if the spec is empty/unparseable, meaning "disabled"."""
    if not spec or not spec.strip():
        return 0, None

    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    modifiers = 0
    key = None
    for p in parts:
        if p == "win":
            modifiers |= wx.MOD_WIN
        elif p == "alt":
            modifiers |= wx.MOD_ALT
        elif p == "ctrl":
            modifiers |= wx.MOD_CONTROL
        elif p == "shift":
            modifiers |= wx.MOD_SHIFT
        elif len(p) == 1:
            key = ord(p.upper())
        else:
            named = getattr(wx, f"WXK_{p.upper()}", None)
            if named is not None:
                key = named
    return modifiers, key


def normalize_hotkey(spec):
    """Rebuilds a canonical string from a parsed spec, so two different
    typed forms of the same combo (e.g. 'Alt+Win+T' vs 'win+alt+t')
    compare as equal when checking for conflicts."""
    modifiers, key = parse_hotkey(spec)
    if key is None:
        return None
    parts = []
    if modifiers & wx.MOD_WIN:
        parts.append("win")
    if modifiers & wx.MOD_CONTROL:
        parts.append("ctrl")
    if modifiers & wx.MOD_ALT:
        parts.append("alt")
    if modifiers & wx.MOD_SHIFT:
        parts.append("shift")
    if 32 <= key < 127:
        parts.append(chr(key).lower())
    else:
        # Reverse-lookup named keys (F1-F24, arrows, etc.) so the
        # display string reads e.g. "f1" instead of a raw numeric
        # code like "340" - this string is shown directly to the user
        # in the hotkey-conflict warning message.
        name = _WXK_NAME_BY_VALUE.get(key)
        parts.append(name.lower() if name else str(key))
    return "+".join(parts)


def _build_wxk_name_lookup():
    lookup = {}
    for attr in dir(wx):
        if attr.startswith("WXK_"):
            lookup[getattr(wx, attr)] = attr[len("WXK_"):]
    return lookup


_WXK_NAME_BY_VALUE = _build_wxk_name_lookup()


def find_conflicts(hotkeys_dict):
    """hotkeys_dict: {action_name: spec_string}. Returns a list of
    (action_a, action_b, normalized_spec) for every pair of actions
    that would register the same physical combination. Empty specs
    (disabled hotkeys) never conflict with anything."""
    normalized = {}
    for action, spec in hotkeys_dict.items():
        norm = normalize_hotkey(spec)
        if norm:
            normalized[action] = norm

    conflicts = []
    actions = list(normalized.keys())
    for i in range(len(actions)):
        for j in range(i + 1, len(actions)):
            a, b = actions[i], actions[j]
            if normalized[a] == normalized[b]:
                conflicts.append((a, b, normalized[a]))
    return conflicts
