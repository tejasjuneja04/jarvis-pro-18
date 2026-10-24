"""
Hinglish hearing: fix what the keyboard or Chrome's speech recogniser gets wrong in Indian talk.

"City ka matlab pressure kukar ki CT" is about a pressure cooker whistle (सीटी). A recogniser writes it "CT",
"city", "ceete" and a language model then answers "cooking time". The glossary tells us which words only mean
something special next to a context word ("cooker", "aloo", "dal" ...), so "city" is left alone in
"which city is Delhi in" but becomes "seeti" next to "pressure cooker".

    normalize("aloo ke liye kitni ceete")  -> ("aloo ke liye kitni seeti (pressure-cooker whistle)", [hint])

Edit hinglish_data/glossary.json to teach new words. No model is involved: it is fast and predictable.
"""

from __future__ import annotations

import json
import os
import re

_PATH = os.path.join(os.path.dirname(__file__), "hinglish_data", "glossary.json")
_cache: dict = {"mtime": None, "data": None}


def _load() -> dict:
    try:
        mtime = os.path.getmtime(_PATH)
    except OSError:
        return {"domains": [], "always": {}}
    if _cache["mtime"] != mtime:                      # re-read when the file is edited, no restart needed
        try:
            with open(_PATH, encoding="utf-8") as f:
                _cache["data"] = json.load(f)
        except Exception as e:
            print("[ear] glossary.json is not valid:", e)
            _cache["data"] = {"domains": [], "always": {}}
        _cache["mtime"] = mtime
    return _cache["data"]


def _words(text: str) -> list:
    return re.findall(r"[\wऀ-ॿ]+", (text or "").lower())


def normalize(text: str) -> tuple:
    """-> (text with the mis-heard words fixed, [short hints for the language model])."""
    if not text:
        return text, []
    data = _load()
    out, hints = text, []

    for bad, good in (data.get("always") or {}).items():
        out = re.sub(rf"(?<![\w]){re.escape(bad)}(?![\w])", good, out, flags=re.I)

    present = set(_words(out))
    for dom in data.get("domains") or []:
        contexts = {c.lower() for c in dom.get("contexts", [])}
        # a context word must be in the sentence, and it must not be one of the terms we are about to replace
        terms = sorted({t.lower() for t in dom.get("terms", [])}, key=len, reverse=True)
        ctx_hits = present & (contexts - set(terms)) or {w for w in present & contexts if w not in terms}
        if not ctx_hits:
            continue
        meaning = dom.get("meaning", "")
        changed = False
        for t in terms:
            pat = rf"(?<![\wऀ-ॿ]){re.escape(t)}(?![\wऀ-ॿ])"
            if re.search(pat, out, flags=re.I):
                out = re.sub(pat, meaning.split(" (")[0], out, flags=re.I)
                changed = True
        if changed and dom.get("hint"):
            hints.append(dom["hint"])
    return out, hints
