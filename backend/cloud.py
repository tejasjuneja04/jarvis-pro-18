"""
JARVIS cloud brain: Claude (Anthropic API, paid), Groq (free tier) or Gemini (Google, free tier).

Optional. When ANTHROPIC_API_KEY, GROQ_API_KEY or GEMINI_API_KEY is set (backend/.env) and the "Cloud brain" switch is on,
normal conversation and pictures go to the cloud instead of the local model. Everything else (commands,
files, data analysis, charts, voice) still runs on the Mac.

Privacy: in cloud mode your messages and the conversation history are sent to Anthropic or Google.
Cost: Claude is paid per use. Gemini has a free tier with daily limits.
Turn the switch off to go back to fully local and offline.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import config

_client = None
_error = ""

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _get_client():
    global _client, _error
    if _client is not None:
        return _client
    if not config.ANTHROPIC_API_KEY:
        _error = "ANTHROPIC_API_KEY is not set in backend/.env"
        return None
    try:
        import anthropic
    except ImportError:
        _error = "the anthropic package is not installed (pip install anthropic)"
        return None
    _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _has(p: str) -> bool:
    return ((p == "claude" and _get_client() is not None) or (p == "groq" and bool(config.GROQ_API_KEY))
            or (p == "gemini" and bool(config.GEMINI_API_KEY))
            or (p == "custom" and bool(config.CUSTOM_API_KEY and config.CUSTOM_BASE_URL and config.CUSTOM_MODEL)))


def hindi_provider() -> str:
    """The cloud provider that writes the best Hindi among the keys you have: Claude, then Gemini, then Groq."""
    want = config.HINDI_PROVIDER
    order = [want] if want in ("claude", "custom", "gemini", "groq") else []
    for p in order + ["claude", "custom", "gemini", "groq"]:
        if _has(p):
            return p
    return ""


def provider(prefer: str = "") -> str:
    """"claude", "groq", "gemini" or "" (no cloud brain set up). `prefer` picks one for this call when its key exists."""
    if prefer and _has(prefer):
        return prefer
    want = config.CLOUD_PROVIDER
    if want in ("auto", "custom") and _has("custom"):
        return "custom"                      # a model you chose on purpose beats the free defaults
    if want in ("auto", "claude") and _get_client() is not None:
        return "claude"
    if want in ("auto", "groq") and config.GROQ_API_KEY:
        return "groq"
    if want in ("auto", "gemini") and config.GEMINI_API_KEY:
        return "gemini"
    return ""


def available() -> bool:
    return provider() != ""


def name() -> str:
    """Short name for the UI: Claude or Gemini."""
    return {"claude": "Claude", "groq": "Groq", "gemini": "Gemini", "custom": "Custom"}.get(provider(), "Claude")   # terminal only, never shown in the app


def model_for(pv: str) -> str:
    return {"claude": config.CLOUD_MODEL, "groq": config.GROQ_MODEL, "gemini": config.GEMINI_MODEL, "custom": config.CUSTOM_MODEL}.get(pv, "")


def model_name() -> str:
    return {"claude": config.CLOUD_MODEL, "groq": config.GROQ_MODEL, "gemini": config.GEMINI_MODEL, "custom": config.CUSTOM_MODEL}.get(provider(), "")


def status() -> str:
    """One line for the startup banner."""
    if available():
        return f"ready ({model_name()})"
    return "off: add GROQ_API_KEY or GEMINI_API_KEY (both free), ANTHROPIC_API_KEY, or JARVIS_LLM_* to backend/.env"


def _clean(messages: list) -> list:
    """The API wants user/assistant turns that alternate and start with the user."""
    out: list = []
    for m in messages:
        role, content = m.get("role"), (m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _consume(stream, cancel, on_delta) -> tuple[str, str]:
    parts = []
    for delta in stream.text_stream:
        if cancel is not None and cancel.is_set():
            break
        parts.append(delta)
        on_delta(delta)
    stop = ""
    if not (cancel is not None and cancel.is_set()):
        stop = getattr(stream.get_final_message(), "stop_reason", "") or ""
    return "".join(parts), stop


_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}


def stream_vision(system: str, history: list, question: str, image_path, cancel, on_delta) -> str:
    """Claude looks at a picture and answers, streaming. The picture is sent with the question only."""
    path = Path(image_path)
    media = _MEDIA.get(path.suffix.lower())
    if media is None:
        raise ValueError(f"unsupported picture type {path.suffix}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
        {"type": "text", "text": question},
    ]
    messages = _clean(history)
    if messages and messages[-1]["role"] == "user":
        messages.append({"role": "assistant", "content": "Understood."})
    if provider() in ("groq", "custom"):
        raise RuntimeError("this cloud brain does not look at pictures")    # the local vision model answers instead
    if provider() == "gemini":
        parts = [{"inline_data": {"mime_type": media, "data": data}}, {"text": question}]
        return _gemini_stream(system, messages + [{"role": "user", "parts": parts}], config.CLOUD_MAX_TOKENS,
                              cancel, on_delta)
    messages.append({"role": "user", "content": content})
    return stream_text(system, messages, config.CLOUD_MAX_TOKENS, cancel, on_delta, prepared=True)


def _stream_one(pv: str, system: str, messages: list, max_tokens: int, cancel, on_delta, deep: bool = False, prepared: bool = False,
                temperature: float = 0.8) -> str:
    """Stream a Claude reply, calling on_delta(text) for each piece. Returns the full text.

    Raises on connection or API errors so the caller can fall back to the local model.
    """
    if pv == "custom":
        return _custom_stream(system, messages if prepared else _clean(messages), max_tokens, cancel, on_delta, deep, temperature)
    if pv == "groq":
        return _groq_stream(system, messages if prepared else _clean(messages), max_tokens, cancel, on_delta, deep, temperature)
    if pv == "gemini":
        return _gemini_stream(system, messages if prepared else _clean(messages), max_tokens, cancel, on_delta, deep, temperature)
    client = _get_client()
    if client is None:
        raise RuntimeError(f"cloud brain unavailable: {_error}")

    effort = "high" if deep else config.CLOUD_EFFORT
    kwargs = dict(model=config.CLOUD_MODEL, max_tokens=max_tokens, system=system, messages=messages if prepared else _clean(messages))

    # Server-side refusal fallback: if Claude declines, the API retries on Anthropic's recommended
    # fallback model inside the same call. Older SDKs (Python 3.9 resolves anthropic 0.x) may not
    # know these parameters, so retry by sending the same fields as raw body/header extras.
    try:
        with client.beta.messages.stream(**kwargs, output_config={"effort": effort},
                                         betas=[FALLBACK_BETA], fallbacks="default") as stream:
            text, stop = _consume(stream, cancel, on_delta)
    except TypeError:
        with client.messages.stream(**kwargs, extra_headers={"anthropic-beta": FALLBACK_BETA},
                                    extra_body={"output_config": {"effort": effort}, "fallbacks": "default"}) as stream:
            text, stop = _consume(stream, cancel, on_delta)

    if stop == "refusal":
        note = "\n\n*(I'd rather not answer that one.)*"
        on_delta(note)
        text += note
    elif stop == "max_tokens":
        note = " …"
        on_delta(note)
        text += note
    return text


# ------------------------------------------------------------------ Gemini (Google, free tier)
_gemini_auth = ["header"]            # remembers which way of sending the key worked
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"


def _gemini_body(system: str, messages: list, max_tokens: int, deep: bool, thinking: dict | None, temperature: float = 0.8) -> dict:
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        parts = m.get("parts") or [{"text": m.get("content") or ""}]
        contents.append({"role": role, "parts": parts})
    gen = {"maxOutputTokens": max_tokens, "temperature": temperature}
    if thinking:
        gen["thinkingConfig"] = thinking                   # chat stays fast; deep mode lets it think more
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": gen,
        "safetySettings": [{"category": c, "threshold": "BLOCK_ONLY_HIGH"} for c in (
            "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")],
    }


def _gemini_stream(system: str, messages: list, max_tokens: int, cancel, on_delta, deep: bool = False, temperature: float = 0.8) -> str:
    """Stream a Gemini reply over plain HTTPS (no extra package), calling on_delta for each piece."""
    import json
    import urllib.error
    import urllib.request

    base_url = GEMINI_URL.format(model=config.GEMINI_MODEL)
    key = config.GEMINI_API_KEY

    def open_stream(thinking: dict | None, auth: str):
        """Newer AQ. keys are picky about how they are presented, so the key can go in a header, the URL or a Bearer header."""
        headers = {"Content-Type": "application/json"}
        url = base_url
        if auth == "header":
            headers["x-goog-api-key"] = key
        elif auth == "query":
            url += "&key=" + key
        else:
            headers["Authorization"] = "Bearer " + key
        body = json.dumps(_gemini_body(system, messages, max_tokens, deep, thinking, temperature)).encode("utf-8")
        return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout=config.CLOUD_TIMEOUT)

    # Gemini 3 takes a thinking level, Gemini 2.5 a thinking budget. Try the fast settings first and fall
    # back step by step if this model rejects one, so a slow "thinking" pass never stalls a quick chat.
    if config.GEMINI_MODEL.startswith("gemini-2"):
        tries = [None] if deep else [{"thinkingBudget": 0}, None]
    else:
        tries = [{"thinkingLevel": "high"}, None] if deep else [{"thinkingLevel": "minimal"}, {"thinkingLevel": "low"}, None]
    auths = [_gemini_auth[0]] + [a for a in ("header", "query", "bearer") if a != _gemini_auth[0]]
    resp, last_err = None, ""
    for auth in auths:
        bad_auth = False
        for i, thinking in enumerate(tries):
            try:
                resp = open_stream(thinking, auth)
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                last_err = f"Gemini error {e.code}: {detail}"
                low = detail.lower()
                if e.code in (400, 401, 403) and re.search(r"api key|credential|token|authenticat|permission|unsupported", low):
                    bad_auth = True                      # not the request, the way the key was sent: try the next style
                    break
                if e.code == 400 and i < len(tries) - 1:     # this model rejects that thinking setting: try the next
                    continue
                if e.code == 429:
                    raise RuntimeError("the free daily limit of the cloud brain is used up for now") from None
                raise RuntimeError(last_err) from None
            except OSError as e:                                     # timeouts, DNS, connection resets
                raise RuntimeError(f"Gemini did not answer within {config.CLOUD_TIMEOUT}s ({type(e).__name__}: {e})") from None
        if resp is not None:
            _gemini_auth[0] = auth
            break
        if not bad_auth:
            break
    if resp is None:
        raise RuntimeError(last_err or "Gemini did not answer")

    parts, finish = [], ""
    with resp:
        for raw in resp:
            if cancel is not None and cancel.is_set():
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                chunk = json.loads(line[5:].strip())
            except ValueError:
                continue
            for cand in chunk.get("candidates") or []:
                for part in (cand.get("content") or {}).get("parts") or []:
                    if part.get("thought"):
                        continue                      # private reasoning, not part of the answer
                    t = part.get("text") or ""
                    if t:
                        parts.append(t)
                        on_delta(t)
                finish = cand.get("finishReason") or finish
    text = "".join(parts)
    if not text and finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
        note = "*(I'd rather not answer that one.)*"
        on_delta(note)
        text = note
    elif finish == "MAX_TOKENS":
        on_delta(" …")
        text += " …"
    return text


# ------------------------------------------------------------------ Groq (free tier, very fast)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _groq_stream(system, messages, max_tokens, cancel, on_delta, deep=False, temperature=0.8) -> str:
    # reasoning models think briefly in chat and properly in deep mode; other models reject the setting
    tries = [{"reasoning_effort": "high" if deep else "low", "include_reasoning": False}, {}]
    return _openai_stream(GROQ_URL, config.GROQ_API_KEY, config.GROQ_MODEL, "Groq", tries, system, messages, max_tokens,
                          cancel, on_delta, temperature)


def _custom_stream(system, messages, max_tokens, cancel, on_delta, deep=False, temperature=0.8) -> str:
    """Any OpenAI-style API: OpenRouter, DeepSeek, Mistral, OpenAI, Together, a local server... (JARVIS_LLM_* in .env)."""
    # providers differ on the token-limit and temperature fields, so retry without the ones a model refuses
    tries = [{}, {"max_completion_tokens": None, "max_tokens": max_tokens}, {"max_completion_tokens": None, "temperature": None}]
    url = config.CUSTOM_BASE_URL.rstrip("/") + "/chat/completions"
    return _openai_stream(url, config.CUSTOM_API_KEY, config.CUSTOM_MODEL, "Custom model", tries, system, messages, max_tokens,
                          cancel, on_delta, temperature)


def _openai_stream(url, key, model, label, tries, system, messages, max_tokens, cancel, on_delta, temperature, shrunk=None) -> str:
    """Stream a reply from an OpenAI-style chat API over plain HTTPS (no extra package), calling on_delta for each piece."""
    import json
    import urllib.error
    import urllib.request

    shrunk = [] if shrunk is None else shrunk
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "jarvis"}
    base = {"model": model, "stream": True, "temperature": temperature, "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}] + messages}

    def open_stream(extra: dict):
        payload = {k: v for k, v in {**base, **extra}.items() if v is not None}
        body = json.dumps(payload).encode("utf-8")
        return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout=config.CLOUD_TIMEOUT)

    resp = None
    for i, extra in enumerate(tries):
        try:
            resp = open_stream(extra)
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code == 400 and i < len(tries) - 1:
                continue
            afford = re.search(r"can only afford (\d+)", detail)
            if e.code == 402 and afford and not shrunk:
                # a small balance can't reserve the full reply length: ask for what it can pay for and retry
                room = int(afford.group(1)) - 20
                if room >= 200:
                    shrunk.append(room)
                    base["max_completion_tokens"] = base["max_tokens"] = room
                    print(f"[cloud] {label}: low credit, limiting this reply to {room} tokens. Add credit to remove the limit.")
                    return _openai_stream(url, key, model, label, tries, system, messages, room, cancel, on_delta, temperature, shrunk)
                raise RuntimeError(f"{label}: out of credit. Add a few dollars at your provider (OpenRouter: Settings > Credits).") from None
            if e.code == 402:
                raise RuntimeError(f"{label}: out of credit. Add a few dollars at your provider (OpenRouter: Settings > Credits).") from None
            if e.code == 429:
                raise RuntimeError(f"{label}: rate limit or quota used up for now") from None
            raise RuntimeError(f"{label} error {e.code}: {detail}") from None
        except OSError as e:
            raise RuntimeError(f"{label} did not answer within {config.CLOUD_TIMEOUT}s ({type(e).__name__}: {e})") from None

    parts, finish = [], ""
    with resp:
        for raw in resp:
            if cancel is not None and cancel.is_set():
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            for choice in chunk.get("choices") or []:
                t = (choice.get("delta") or {}).get("content") or ""
                if t:
                    parts.append(t)
                    on_delta(t)
                finish = choice.get("finish_reason") or finish
    text = "".join(parts)
    if not text and finish == "content_filter":
        note = "*(I'd rather not answer that one.)*"
        on_delta(note)
        text = note
    elif finish == "length":
        on_delta(" …")
        text += " …"
    return text


def stream_text(system: str, messages: list, max_tokens: int, cancel, on_delta, deep: bool = False, prepared: bool = False,
                prefer: str = "", temperature: float = 0.8) -> str:
    """Stream a reply from the preferred provider. If it fails before saying anything (timeout, quota, bad key),
    try the other providers you have keys for, so one slow service never leaves Jarvis stuck on "Thinking"."""
    import time

    first = provider(prefer)
    order = [first] + [p for p in ("claude", "custom", "gemini", "groq") if p != first and _has(p)]
    started = [False]

    def watch(t):
        started[0] = True
        on_delta(t)

    last = None
    for pv in order:
        t0 = time.time()
        try:
            out = _stream_one(pv, system, messages, max_tokens, cancel, watch, deep, prepared, temperature)
            print(f"[cloud] {pv} answered in {time.time() - t0:.1f}s")
            return out
        except Exception as e:                                   # noqa: BLE001
            print(f"[cloud] {pv} failed after {time.time() - t0:.1f}s: {type(e).__name__}: {e}")
            last = e
            if started[0] or (cancel is not None and cancel.is_set()):
                raise
    raise last if last else RuntimeError("no cloud provider is set up")


def gemini_post(url: str, payload: dict, timeout: float = 30) -> dict:
    """POST JSON to a Gemini endpoint and return the parsed reply. Newer AQ. keys are picky about how they are sent,
    so the key goes in a header, then the URL, then a Bearer header, and the style that works is remembered."""
    import json
    import urllib.error
    import urllib.request

    key = config.GEMINI_API_KEY
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set in backend/.env")
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for auth in [_gemini_auth[0]] + [a for a in ("header", "query", "bearer") if a != _gemini_auth[0]]:
        headers, u = {"Content-Type": "application/json"}, url
        if auth == "header":
            headers["x-goog-api-key"] = key
        elif auth == "query":
            u += ("&" if "?" in u else "?") + "key=" + key
        else:
            headers["Authorization"] = "Bearer " + key
        try:
            with urllib.request.urlopen(urllib.request.Request(u, data=body, headers=headers, method="POST"), timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            _gemini_auth[0] = auth
            return data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            last = f"Gemini error {e.code}: {detail}"
            if e.code in (400, 401, 403) and re.search(r"api key|credential|access.token|authenticat|permission", detail, re.I):
                continue                                   # the way the key was sent, not the request: try the next style
            raise RuntimeError(last) from None
        except OSError as e:
            raise RuntimeError(f"Gemini did not answer ({type(e).__name__}: {e})") from None
    raise RuntimeError(last or "Gemini rejected the key")
