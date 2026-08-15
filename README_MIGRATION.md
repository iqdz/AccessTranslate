# Access-Translate Migration README

## Project Status
This project was in active development. All core modules are written and
syntax-verified. The following pieces were complete as of migration:

### Complete modules (all syntax-verified):
- access_translate/__init__.py - package marker, version
- access_translate/config.py - settings storage in %AppData%\Access-Translate\
- access_translate/cache.py - per-app translation cache with poison-prevention
- access_translate/engines.py - all 7 engines + custom API support
- access_translate/speech.py - SAPI voice output wrapper
- access_translate/ui_automation.py - grabs selected/focused text via UIA
- access_translate/lang_detect.py - script-based language detector
- access_translate/hotkeys.py - hotkey string parser for wx.RegisterHotKey
- access_translate/first_run_dialog.py - first-run welcome + shortcut offer
- access_translate/tray_icon.py - system tray icon with context menu
- access_translate/settings_dialog.py - full settings UI (all tabs)
- access_translate/main.py - app entry point, hotkey registration, loop
- run.py - PyInstaller entry point
- requirements.txt - pip dependencies
- build.ps1 + build.bat - one-command build to portable exe

### What was NOT yet done when migration happened:
- LICENSE file (GPLv2 full text) - add from https://www.gnu.org/licenses/gpl-2.0.txt
- The settings_dialog.py hotkeys tab was built but needs end-to-end
  testing of live hotkey re-registration after save
- No real-device testing had been done yet

## Setup in new chat
1. Tell the new AI: "This is Access-Translate, a portable Windows
   accessibility translation tool. Here are all the project files."
2. Paste or upload this zip.
3. The next task is: write the GPLv2 LICENSE file, then do a full
   code review pass on main.py and settings_dialog.py for any gaps,
   then test-build with build.bat.

## Build instructions
1. Install Python 3.9+ (add to PATH)
2. Double-click build.bat
3. Find Access-Translate.exe in the dist\ folder
4. Run it - on first run it creates %AppData%\Access-Translate\config.json
   and offers a desktop shortcut

## Project decisions (settled, do not revisit):
- Config: %AppData%\Access-Translate\config.json (separate from NVDA addon)
- UI: wxPython (same toolkit as NVDA - accessibility proven)
- Voice: SAPI directly (works with NVDA, JAWS, Narrator, or none)
- Hotkeys: Win+Alt+T (translate), Win+Alt+S (swap lang),
           Win+Alt+G (revert lang), Win+Alt+C (clear cache) - all user-remappable
- Clipboard: optional, translation-only or original+translation
- Tray: minimize to tray optional, defaults OFF
- Engines: Local Offline, Google, DeepL, Bing, OpenAI, Gemini,
           OpenRouter, + unlimited custom API slots
- Exclusion list: in scope for v1
- License: GPLv2
- Portable exe via PyInstaller, settings in %AppData%
- Local LibreTranslate service NOT managed from within the app (separate scripts)
