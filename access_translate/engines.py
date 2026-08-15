"""Translation engine implementations.

Each built-in engine function has the signature
    translate(text, target_lang, source_lang, cfg) -> str or None
None signals failure. Callers (see cache.put) must never cache a None
result as if it were a real translation - this mirrors the
cache-poisoning fix already applied to the NVDA addon after real-world
debugging showed a silent failure could get permanently cached and
block a later successful attempt under a different engine.
"""
import json
import urllib.parse
import urllib.request


def _post_json(url, payload, headers=None, timeout=8):
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            else:
                print(f"Engine request to {url} returned status {resp.status}")
    except Exception as e:
        print(f"Engine request to {url} failed: {e}")
    return None


# ---------------------------------------------------------------------------
# Local Offline (LibreTranslate) - reuses the same request shape already
# proven working against the existing local service.
# ---------------------------------------------------------------------------
def translate_local_offline(text, target_lang, source_lang, cfg):
    url = cfg.get("local_offline_url", "http://127.0.0.1:5000/translate")
    result = _post_json(url, {
        "q": text,
        "source": source_lang or "auto",
        "target": target_lang,
        "format": "text",
    })
    if result:
        return result.get("translatedText") or None
    return None


# ---------------------------------------------------------------------------
# Google Translate (unofficial endpoint, same approach as the NVDA
# addon's mtranslate module - no API key needed)
# ---------------------------------------------------------------------------
def translate_google(text, target_lang, source_lang, cfg):
    quoted = urllib.parse.quote(text)
    src = source_lang or "auto"
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={src}&tl={target_lang}&dt=t&q={quoted}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                parts = []
                if data and isinstance(data, list) and data[0]:
                    for chunk in data[0]:
                        if chunk and chunk[0]:
                            parts.append(chunk[0])
                return "".join(parts) or None
            else:
                print(f"Google translate returned status {resp.status}")
    except Exception as e:
        print(f"Google translate failed: {e}")
    return None


# ---------------------------------------------------------------------------
# DeepL
# ---------------------------------------------------------------------------
def translate_deepl(text, target_lang, source_lang, cfg):
    api_key = cfg.get("api_keys", {}).get("deepl", "")
    if not api_key:
        return None
    is_free = api_key.endswith(":fx")
    base = "https://api-free.deepl.com" if is_free else "https://api.deepl.com"
    payload = urllib.parse.urlencode({
        "auth_key": api_key,
        "text": text,
        "target_lang": target_lang.upper(),
    }).encode("utf-8")
    req = urllib.request.Request(f"{base}/v2/translate", data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                translations = data.get("translations", [])
                if translations:
                    return translations[0].get("text") or None
            else:
                print(f"DeepL returned status {resp.status}")
    except Exception as e:
        print(f"DeepL translate failed: {e}")
    return None


# ---------------------------------------------------------------------------
# Bing / Azure Translator
# ---------------------------------------------------------------------------
def translate_bing(text, target_lang, source_lang, cfg):
    api_key = cfg.get("api_keys", {}).get("bing", "")
    region = cfg.get("api_keys", {}).get("bing_region", "")
    if not api_key:
        return None
    url = (
        "https://api.cognitive.microsofttranslator.com/translate"
        f"?api-version=3.0&to={target_lang}"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
    }
    if region:
        headers["Ocp-Apim-Subscription-Region"] = region
    result = _post_json(url, [{"Text": text}], headers=headers)
    if result and isinstance(result, list) and result and result[0].get("translations"):
        return result[0]["translations"][0].get("text") or None
    return None


# ---------------------------------------------------------------------------
# Chat-style AI engines (OpenAI, Gemini, OpenRouter, and generic
# OpenAI-compatible custom APIs all share this shape)
# ---------------------------------------------------------------------------
def _chat_style_translate(url, headers, model, text, target_lang):
    prompt = (
        f"Translate the following text to {target_lang}. "
        f"Reply with only the translation, nothing else:\n\n{text}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    result = _post_json(url, payload, headers=headers)
    if result:
        try:
            return result["choices"][0]["message"]["content"].strip() or None
        except (KeyError, IndexError, TypeError):
            pass
    return None


def translate_openai(text, target_lang, source_lang, cfg):
    api_key = cfg.get("api_keys", {}).get("openai", "")
    if not api_key:
        return None
    return _chat_style_translate(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        "gpt-5.4-mini",
        text, target_lang,
    )


def translate_openrouter(text, target_lang, source_lang, cfg):
    api_key = cfg.get("api_keys", {}).get("openrouter", "")
    if not api_key:
        return None
    return _chat_style_translate(
        "https://openrouter.ai/api/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        "deepseek/deepseek-chat",
        text, target_lang,
    )


def translate_gemini(text, target_lang, source_lang, cfg):
    api_key = cfg.get("api_keys", {}).get("gemini", "")
    if not api_key:
        return None
    prompt = (
        f"Translate the following text to {target_lang}. "
        f"Reply with only the translation, nothing else:\n\n{text}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-3.5-flash:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    result = _post_json(url, payload)
    if result:
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip() or None
        except (KeyError, IndexError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# Custom API - the "Add Custom API" action from the settled plan.
# Supports either an OpenAI-compatible chat endpoint, or a
# LibreTranslate-compatible endpoint (so a second self-hosted or
# third-party LibreTranslate instance can be added too).
# ---------------------------------------------------------------------------
def translate_custom(text, target_lang, source_lang, api_entry):
    fmt = api_entry.get("format", "openai")
    if fmt == "libretranslate":
        payload = {
            "q": text,
            "source": source_lang or "auto",
            "target": target_lang,
            "format": "text",
        }
        if api_entry.get("api_key"):
            payload["api_key"] = api_entry["api_key"]
        result = _post_json(api_entry["url"], payload)
        return (result or {}).get("translatedText") or None
    else:
        headers = {}
        if api_entry.get("api_key"):
            headers["Authorization"] = f"Bearer {api_entry['api_key']}"
        return _chat_style_translate(
            api_entry["url"], headers,
            api_entry.get("model", "gpt-5.4-mini"),
            text, target_lang,
        )


ENGINES = {
    "local_offline": translate_local_offline,
    "google": translate_google,
    "deepl": translate_deepl,
    "bing": translate_bing,
    "openai": translate_openai,
    "gemini": translate_gemini,
    "openrouter": translate_openrouter,
}


def translate(text, target_lang, source_lang, cfg):
    """Dispatches to whichever engine is currently configured. Custom
    API entries are addressed as 'custom:<index>' into cfg['custom_apis']."""
    engine_id = cfg.get("engine", "local_offline")
    if engine_id.startswith("custom:"):
        try:
            idx = int(engine_id.split(":", 1)[1])
        except ValueError:
            return None
        custom_apis = cfg.get("custom_apis", [])
        if 0 <= idx < len(custom_apis):
            return translate_custom(text, target_lang, source_lang, custom_apis[idx])
        return None
    fn = ENGINES.get(engine_id)
    if fn is None:
        return None
    return fn(text, target_lang, source_lang, cfg)
