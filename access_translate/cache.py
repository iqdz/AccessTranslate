"""Translation cache, scoped per source application - mirrors the NVDA
addon's own per-app cache concept, and supports the Win+Alt+C hotkey's
single press (clear current app) vs double press (clear everything)
behavior from the settled plan.

Also mirrors the addon's cache-poisoning fix: a failed or no-op
translation is never cached, so a later successful attempt (different
engine, engine back online, etc.) is never permanently blocked by a
stale failure.
"""
import threading

_lock = threading.Lock()
_cache = {}  # {app_name: {source_text: translated_text}}


def get(app_name, text):
    with _lock:
        return _cache.get(app_name, {}).get(text)


def put(app_name, text, translated):
    if not translated or translated.strip() == text.strip():
        return
    with _lock:
        _cache.setdefault(app_name, {})[text] = translated


def clear_app(app_name):
    with _lock:
        _cache.pop(app_name, None)


def clear_all():
    with _lock:
        _cache.clear()
