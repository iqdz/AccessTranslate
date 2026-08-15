"""Lightweight script-based language detection, mirroring the approach
used in the NVDA addon: identifies languages by character script for
common non-Latin alphabets. Latin-script languages can't be
individually distinguished this way - same known limitation carried
over from the addon, not a new one introduced here.
"""
import re

_PATTERNS = [
    ("ar", re.compile(r"[\u0600-\u06FF]")),
    ("ru", re.compile(r"[\u0400-\u04FF]")),
    ("zh", re.compile(r"[\u4E00-\u9FFF]")),
    ("ja", re.compile(r"[\u3040-\u30FF]")),
    ("ko", re.compile(r"[\uAC00-\uD7AF]")),
    ("he", re.compile(r"[\u0590-\u05FF]")),
    ("th", re.compile(r"[\u0E00-\u0E7F]")),
    ("hi", re.compile(r"[\u0900-\u097F]")),
]


def detect(text):
    for code, pattern in _PATTERNS:
        if pattern.search(text):
            return code
    return "auto"
