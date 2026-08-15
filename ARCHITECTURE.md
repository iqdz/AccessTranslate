# Access-Translate - Architecture & Status

GPLv2. Portable Windows accessibility translation tool. Works
independently of NVDA/JAWS/Narrator by speaking through SAPI directly,
and reads selected/copied text through a layered strategy (UI
Automation selection, then clipboard, then a synthetic Ctrl+C as a
last resort) - see "Text-grabbing design" below.

Repository: https://github.com/iqdz/AccessTranslate

## Project structure

```
access-translate/
  access_translate/
    __init__.py        - package marker, version
    config.py           - settings in %AppData%\Access-Translate\config.json
    cache.py             - per-app translation cache, poison-prevention
    engines.py           - 7 built-in engines + custom API support
    speech.py             - SAPI voice wrapper (COM apartment fix included);
                            also exposes Speaker.stop() for the
                            "stop speech immediately" hotkey
    ui_automation.py       - UIA text reader: real TextPattern selection,
                            then clipboard fallback, then focused-element
                            value as a last resort
    lang_detect.py          - script-based language detection (exclusion list)
    hotkeys.py                - hotkey string parser + defaults + conflict
                                checking + display-name normalization
                                (including named keys like F1-F24, Pause)
    debug_log.py               - timestamped logging to console + a
                                toggleable %AppData%\...\debug.log file
    first_run_dialog.py        - welcome dialog (shows the ACTUAL
                                configured translate hotkey, not a
                                hardcoded string), desktop shortcut offer
    tray_icon.py                 - always-on system tray icon + menu
    settings_dialog.py            - full wx settings UI (7 tabs, incl. About)
    main.py                        - app entry point, hotkey handling, core logic
  run.py                - PyInstaller entry point
  requirements.txt        - wxPython, pywin32, comtypes
  build.ps1 / build.bat     - one-command build to portable exe
  LICENSE                     - GPLv2
  README.md                     - user-facing feature/setup docs
  README_MIGRATION.md           - prior migration notes
  ARCHITECTURE.md                 - this file
  .gitignore                        - excludes build artifacts, local
                                     config/logs, editor files, secrets
```

## Settled design decisions (do not revisit)

- Config: `%AppData%\Access-Translate\config.json` - fully separate from
  the NVDA "translating" addon's own config, by design
- Portable exe via PyInstaller (`--onefile --windowed`), no installer
- UI toolkit: wxPython (same as NVDA's own dialogs - proven accessible)
- Voice output: SAPI directly, NOT routed through any screen reader -
  this is what makes it work with NVDA, JAWS, Narrator, or nothing at all
- Engines: Local Offline (LibreTranslate), Google, DeepL, Bing, OpenAI,
  Gemini, OpenRouter, plus unlimited custom API entries
- Clipboard copy: optional, translation-only or original+translation;
  defaults ON
- Exclusion list: in scope, script-based detection (same limitation as
  the NVDA addon - can't distinguish Latin-script languages from each other)
- Hotkeys: fully customizable in Settings, live conflict detection.
  Current defaults (see table below) intentionally avoid `Ctrl+Alt+Shift`
  combos that turned out to be error-prone to hold down reliably, and
  avoid `Win+Alt+*` combos that conflicted with existing system/app
  shortcuts.
- Tray icon: ALWAYS visible (not conditional on a setting) - it's the
  only way to reach Settings/Quit when the app has no visible window
- Local LibreTranslate service setup/management stays external
  (a separate, standalone PowerShell-based Windows service) - not
  integrated into this app, deliberately
- Debug logging: writes a fresh, timestamped `debug.log` to
  `%AppData%\Access-Translate\` on every run, toggleable from
  Settings > About. Console output is unaffected by the toggle.

## Current default hotkeys

| Action | Default |
|---|---|
| Translate selected/focused text | `Shift+Win+F1` |
| Swap target to last detected source language | `Shift+Win+F2` |
| Revert target to default | `Shift+Win+F3` |
| Clear cache (once = current app, twice = all) | `Shift+Win+F5` |
| Open Settings window | `Shift+Win+F6` |
| Stop/silence speech immediately | `Pause` |

All are rebindable in Settings > Hotkeys with live conflict detection
before saving.

## Text-grabbing design (important - was debugged extensively)

This went through several iterations before landing on the current,
confirmed-working approach. Documented here so the reasoning isn't lost.

**What doesn't work well on its own:**
- Pure UI Automation TextPattern selection works in Notepad and most
  native Windows text fields, but browsers (Chrome, Edge, Firefox)
  generally don't expose page text selection through UIA TextPattern
  at all.
- Trusting "the focused UI element's value" as a fallback is actively
  dangerous in browsers: mouse-selected page text does not move
  keyboard/UIA focus, so the focused element can be something entirely
  unrelated - e.g. Chrome's own "Ask Gemini" sidebar button - even
  while real content is correctly selected elsewhere on the page. This
  was confirmed directly via debug logging (`TextReader: text='Ask
  Gemini' app_name='chrome.exe'` while real text was selected on the
  page).
- A synthetic Ctrl+C, sent via raw ctypes `SendInput`, is inherently
  less reliable than it looks: it's silently blocked by UIPI when the
  app runs elevated and the target window doesn't, it does nothing
  when the browser's actual selection state doesn't match what the
  screen reader's virtual cursor shows, and (a real bug that was found
  and fixed) an incorrectly-sized `INPUT` struct made it fail
  intermittently even when nothing else was wrong - see "Bugs found
  and fixed" below.

**Current (confirmed working) approach**, in
`ui_automation.py`'s `TextReader.get_selected_or_focused_text()`,
called directly by `main.py`'s `translate_now()`:

1. **Genuine UIA TextPattern selection** - tried first; this is what
   makes Notepad and similar apps work with zero clipboard interaction
   at all.
2. **Clipboard, read as-is** - tried second, *before* the focused
   element's value. This is what makes browsers work reliably: select
   text, copy it yourself (however your screen reader/browser does
   that), then press the hotkey. No synthetic keystroke is required
   for this to succeed, which is exactly why it's more robust than
   relying on simulated input.
3. **Focused element's value** (e.g. a search box or URL bar) - tried
   last, specifically *after* clipboard, because of the "Ask Gemini"
   problem above: a manual copy the user actually made is far more
   trustworthy than whatever element happens to hold UI focus.

If none of those three produce anything, `translate_now()` falls back
further to attempting one synthetic Ctrl+C itself, purely as a last
resort for apps with neither real UIA selection nor anything already
on the clipboard.

This was confirmed working end-to-end via debug logging across
multiple real sessions: Chrome (French, Russian, Chinese selections),
Notepad (Spanish selections), all captured correctly, translated
correctly, and spoken correctly, one hotkey press per translation.

## Bugs found and fixed (chronological, for reference)

1. **Clipboard-changed requirement rejected valid manual copies.** The
   original logic required the clipboard to *change* after a synthetic
   Ctrl+C before trusting it - which directly punished the "select,
   copy yourself, then translate" workflow, since re-copying an
   already-selected range often produces identical (i.e. "unchanged")
   clipboard content. Fixed by trusting clipboard content after the
   copy attempt regardless of whether it changed.
2. **`wx.TheClipboard.IsSupported()` crashed on every call**, due to a
   wxPython version mismatch (`argument 1 has unexpected type
   'DataFormatId'`), silently killing every clipboard read. Fixed by
   dropping the pre-check entirely and relying on `GetData()`'s own
   return value.
3. **`SendInput`'s `INPUT` struct was undersized.** Its union only
   defined the `KEYBDINPUT` member, but Windows sizes the real `INPUT`
   struct to fit its *largest* union member (`MOUSEINPUT`). This made
   `ctypes.sizeof(INPUT)` smaller than what `user32.dll` actually
   expects, so `SendInput` read the wrong stride for a multi-element
   array - corrupting all but the first synthetic keystroke. Fixed by
   defining the full union (`ki`, `mi`, `hi`).
4. **Self-feedback loop**: with "copy result to clipboard" enabled, a
   later hotkey press with no fresh selection could read back the
   app's own last translated output and "translate" it again
   (harmlessly, but confusingly - it always came back as a no-op).
   Fixed by tracking the last text the app itself wrote to the
   clipboard and treating a match as "no new selection."
5. **`translate_now()` discarded `TextReader`'s actual result**,
   keeping only the app name and re-deriving text via its own,
   less-reliable synthetic-Ctrl+C-and-diff logic. This was the root
   cause of most of the Chrome-specific flakiness. Fixed by using
   `TextReader`'s result directly as the primary source (see
   "Text-grabbing design" above).
6. **`TextReader` checked the focused element's value before the
   clipboard**, so a stray focused UI element (Chrome's "Ask Gemini"
   sidebar button) could shadow a real, already-copied selection.
   Fixed by reordering clipboard ahead of focused-element value.
7. **First-run welcome message showed a hardcoded, outdated hotkey**
   (`Win+Alt+T`) that had already drifted from the real default.
   Fixed by reading the actual configured/default hotkey at display
   time instead of hardcoding a string.

## Diagnostics

`debug_log.py` writes a timestamped line for every hotkey dispatch
(including which handler it resolved to), every `SendInput` attempt
(with the real return value and `GetLastError()` code - not just
assumed success), the foreground window title at the moment of a
synthetic Ctrl+C, clipboard state before/after, and every spoken status
message. This made it possible to definitively rule out several
suspected-but-wrong theories during debugging (e.g. confirming the
clear-cache hotkey was never actually firing, when overlapping SAPI
speech made it sound like it was).

Toggle in Settings > About; defaults ON. File lives at
`%AppData%\Access-Translate\debug.log`, truncated fresh each run.

## Other known limitations (by design, not bugs)

- "Read by the screen reader itself" (i.e. intercepting the screen
  reader's own speech pipeline) is NOT achievable universally - no OS
  API exists for it. Only NVDA (via the separate "translating" addon,
  which already intercepts its own speech) can do this natively.
  Access-Translate speaks independently via SAPI instead, which works
  everywhere but is a parallel voice, not an interception.
- Latin-script language exclusion (e.g. distinguishing French from
  Spanish for the exclusion list) is not possible with the current
  script-based detector - same limitation as the NVDA addon.
- The synthetic-Ctrl+C fallback can still be blocked by UIPI when
  Access-Translate runs elevated and the target app doesn't. Not
  usually an issue now that it's a last resort rather than the primary
  mechanism, but worth knowing if translation still fails with nothing
  on the clipboard and no UIA selection available.

## Related sibling projects

- **NVDA addon "translating"** (fork of
  `github.com/salmanf16/nvda-translate`) - live, automatic translation
  within NVDA specifically, with the same local LibreTranslate offline
  backend. Separate, working, not modified by Access-Translate work.
- **LibreTranslate Windows service** - a self-hosted, offline
  LibreTranslate instance running as a Windows service (via NSSM,
  under the user's own account, CPU-affinity pinned to efficiency
  cores), used as the "Local Offline" engine by both Access-Translate
  and the NVDA addon above. Managed independently via standalone
  PowerShell scripts, not integrated into Access-Translate itself.
