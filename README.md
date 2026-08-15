# Access-Translate

A free, standalone Windows tray app that translates whatever text you've
selected or copied, and speaks the result aloud — built accessibility-first
for screen reader users (NVDA, JAWS, Windows Narrator), but useful to anyone.

Select text anywhere — a browser, Notepad, a chat app, a PDF reader — press
a hotkey, and hear the translation immediately. No screen reader add-on
required: speech goes straight through Windows SAPI, so it works
universally regardless of which screen reader (if any) you're running.

## Why this exists

Most translation tools assume you'll click a button, look at a popup, or
install a browser extension with its own UI to navigate. None of that
works well for a screen reader user who just wants to select some foreign
text and hear it in their own language, right now, without leaving what
they're doing. Access-Translate is built around that single workflow.

## Features

- **Global hotkeys** — work from any application, no need to switch focus
  to the app itself.
- **Multiple translation engines** — a local, fully offline engine
  (self-hosted [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)),
  plus Google Translate, DeepL, Bing, OpenAI, Gemini, OpenRouter, and any
  OpenAI- or LibreTranslate-compatible custom API you configure yourself.
- **Speaks results via SAPI** — works with any installed Windows SAPI
  voice (Microsoft voices, ETI-Eloquence, Acapela, etc.), independent of
  and simultaneous with your screen reader's own speech.
- **Clipboard-first text capture** — reliably picks up text you've
  selected and copied yourself (the recommended workflow in browsers,
  especially with a screen reader's own virtual cursor/browse mode
  involved), with a synthetic Ctrl+C as a fallback for apps with neither
  real UI Automation text selection nor a prior manual copy.
- **Per-app translation cache** — repeat selections translate instantly
  without hitting the network again; caching correctly ignores failed
  attempts so a bad request never poisons future results.
- **Language exclusion list** — skip auto-translating text already in a
  language you understand.
- **Configurable clipboard behavior** — optionally copies the translated
  text (or original + translation) back to the clipboard for pasting
  elsewhere.
- **Tray icon**, with an option to minimize to tray instead of closing.
- **Portable config** — all settings live in
  `%AppData%\Access-Translate\config.json`, independent of where the exe
  itself is located, so you can move the exe around without losing
  settings.

## Default hotkeys

All hotkeys are fully rebindable from **Settings → Hotkeys** — the list
below is just what's assigned out of the box on a fresh install.

| Action | Default hotkey |
|---|---|
| Translate selected/focused text | `Shift + Win + F1` |
| Swap target language to last detected source language | `Shift + Win + F2` |
| Revert target language to your default | `Shift + Win + F3` |
| Clear translation cache (press once = current app, twice quickly = all apps) | `Shift + Win + F5` |
| Open Settings window | `Shift + Win + F6` |
| Stop/silence speech immediately | `Pause` |

The **Stop/silence speech** hotkey is worth calling out specifically: it
cuts off SAPI playback immediately, without canceling anything already
translated. This matters for long passages or whole articles — silence
the reading partway through, then paste the (already-complete)
translation into a text file and read it with your own screen reader at
your own pace, instead of waiting for SAPI to finish the whole thing.

## Recommended workflow (browsers, and anywhere with a screen reader
involved)

1. Select the text you want translated, using your screen reader's own
   selection tools.
2. Copy it (however your screen reader/browser normally copies a
   selection).
3. Press the Translate hotkey.

Access-Translate reads the clipboard directly rather than depending
entirely on a background, synthetic Ctrl+C — synthetic keystrokes are
inherently less reliable across different browsers and screen readers, so
trusting a selection you've already copied yourself is the more robust
path. A synthetic Ctrl+C is still attempted as a fallback if nothing
usable is found via UI Automation or the clipboard.

In apps with genuine UI Automation text support (Notepad, most native
Windows text fields), you can usually just select and press the hotkey
directly, with no manual copy step needed.

## Translation engines

Configured under **Settings → Engine**:

- **Local Offline** — points at a self-hosted LibreTranslate instance
  (default `http://127.0.0.1:5000/translate`). No internet connection or
  API key required; see the companion LibreTranslate Windows service
  setup for running one locally.
- **Google Translate**, **DeepL**, **Bing** — require your own API key,
  entered in Settings.
- **OpenAI**, **Gemini**, **OpenRouter** — chat-style AI translation,
  require your own API key.
- **Custom API** — add any OpenAI-compatible or LibreTranslate-compatible
  endpoint of your own.

## Requirements

- Windows 10/11
- Python 3.10+ (only if running from source — see below)

## Running from source

```
pip install -r requirements.txt
python run.py
```

## Building a portable exe

```
build.bat
```

(or `build.ps1` directly) — produces a standalone portable executable via
PyInstaller, with no installation required.

## Configuration file location

All settings, including hotkeys, engine choice, API keys, and voice
preferences, are stored at:

```
%AppData%\Access-Translate\config.json
```

Deleting this file resets the app to defaults on next launch.

## Project status

Actively developed and tested end-to-end with real screen reader
workflows across Chrome, Firefox, and Notepad. See `ARCHITECTURE.md` for
implementation details and design decisions.

## License

GPLv2 — see `LICENSE`.

## Related projects

Access-Translate is one part of a broader set of accessible translation
tooling, alongside an NVDA translation add-on and a self-hosted
LibreTranslate Windows service used as the "Local Offline" engine above.

## Contributing

Issues and pull requests are welcome. This project exists specifically to
serve blind and low-vision Windows users well — accessibility-first
design decisions take priority over convenience-driven ones when the two
conflict.
