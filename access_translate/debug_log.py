"""Timestamped debug logging for diagnosing hotkey/clipboard issues.

Writes to both the console (if any) and a persistent log file at
%APPDATA%\\Access-Translate\\debug.log, so behavior can be captured
even when running as a windowed exe with no visible console, and so
a single problematic run can be inspected after the fact rather than
relying on what scrolled past on screen.

The log file is truncated at the start of each app run (old logs
aren't useful once you're chasing a fresh repro) but everything
written during THIS run stays on disk even if the console output
gets lost or truncated.

File writing is controlled by cfg["debug_log_enabled"] (Settings >
About), since some users may not want a debug.log file continuously
written to their AppData folder. Console printing is unaffected by
this setting - it's free and only visible while actually running
from a console/source anyway.
"""
import os
import time

from . import config as cfg_module

LOG_PATH = os.path.join(cfg_module.APPDATA_DIR, "debug.log")

_log_file = None
_enabled = True


def init_log(enabled=True):
    """Call once at startup. Truncates any previous log file if
    enabled; if disabled, no file is created/opened at all."""
    global _log_file, _enabled
    _enabled = enabled
    if not enabled:
        _log_file = None
        print("Debug log file writing is disabled (Settings > About).")
        return
    cfg_module.ensure_appdata_dir()
    try:
        _log_file = open(LOG_PATH, "w", encoding="utf-8")
        log(f"=== Access-Translate debug log started, writing to {LOG_PATH} ===")
    except Exception as e:
        print(f"Could not open debug log file: {e}")
        _log_file = None


def set_enabled(enabled):
    """Lets Settings toggle logging on/off at runtime, without
    requiring an app restart."""
    global _log_file, _enabled
    _enabled = enabled
    if enabled and _log_file is None:
        cfg_module.ensure_appdata_dir()
        try:
            _log_file = open(LOG_PATH, "w", encoding="utf-8")
            log("=== Debug log re-enabled from Settings ===")
        except Exception as e:
            print(f"Could not open debug log file: {e}")
            _log_file = None
    elif not enabled and _log_file is not None:
        try:
            _log_file.write(f"[{time.strftime('%H:%M:%S')}] === Debug log disabled from Settings ===\n")
            _log_file.close()
        except Exception:
            pass
        _log_file = None


def log(msg):
    """Prints AND (if enabled) writes a timestamped line, flushing
    immediately so nothing is lost if the process is killed mid-run."""
    line = f"[{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d}] {msg}"
    print(line)
    if _log_file is not None:
        try:
            _log_file.write(line + "\n")
            _log_file.flush()
        except Exception:
            pass
