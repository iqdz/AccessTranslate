"""Configuration storage for Access-Translate.

Settled decision: settings live in %AppData%\\Access-Translate\\config.json,
independent of the exe's location (so the exe can be moved without
losing settings), and completely separate from the NVDA addon's own
configuration - the two never touch each other.
"""
import os
import json

APPDATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "Access-Translate"
)
CONFIG_PATH = os.path.join(APPDATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "first_run_complete": False,
    "engine": "local_offline",
    "target_lang": "en",
    "local_offline_url": "http://127.0.0.1:5000/translate",
    "api_keys": {
        "google": "",
        "deepl": "",
        "bing": "",
        "bing_region": "",
        "openai": "",
        "gemini": "",
        "openrouter": "",
    },
    # One built-in custom slot exists implicitly via the "Add Custom
    # API" action - entries land in this list, extensible beyond one.
    "custom_apis": [
        # {"name": ..., "url": ..., "api_key": ..., "format": "openai"|"libretranslate"}
    ],
    "voice": {
        "voice_id": "",  # empty = system default SAPI voice
        "rate": 0,
        "volume": 100,
        "status_use_same_voice": True,
        "status_voice_id": "",
        "status_rate": 0,
    },
    "clipboard": {
        "enabled": True,
        "format": "translation_only",  # or "original_and_translation"
    },
    "excluded_langs": [],
    "hotkeys": {
        "translate": "shift+win+f1",
        "swap": "shift+win+f2",
        "revert": "shift+win+f3",
        "clear_cache": "shift+win+f5",
        "settings": "shift+win+f6",
        "stop_speech": "pause",
    },
    "minimize_to_tray": False,  # settled: defaults OFF
    "debug_log_enabled": True,  # writes a timestamped debug.log to %AppData%\Access-Translate\
}


def ensure_appdata_dir():
    os.makedirs(APPDATA_DIR, exist_ok=True)


def load_config():
    """Loads config, creating a default one on first run. Missing keys
    in an existing (older) config file are filled in from defaults,
    so upgrades never crash on a missing key."""
    ensure_appdata_dir()
    if not os.path.exists(CONFIG_PATH):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        _deep_merge(cfg, loaded)
        return cfg
    except Exception as e:
        print(f"Could not read config, using defaults: {e}")
        return json.loads(json.dumps(DEFAULT_CONFIG))


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def save_config(cfg):
    ensure_appdata_dir()
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, CONFIG_PATH)
