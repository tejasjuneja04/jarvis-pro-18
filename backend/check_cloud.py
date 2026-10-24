"""Run this to see exactly what your cloud keys do:   python check_cloud.py
Sends one tiny request to each provider you have a key for and prints the result and how long it took."""
import json
import time
import urllib.error
import urllib.request

import config


def post(url, headers, body):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode()), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400], time.time() - t0
    except Exception as e:                                       # noqa: BLE001
        return type(e).__name__, str(e), time.time() - t0


if config.GEMINI_API_KEY:
    base = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": "Say 'namaste' in Hindi, one word."}]}], "generationConfig": {"maxOutputTokens": 200}}
    k = config.GEMINI_API_KEY
    print(f"Key starts with {k[:3]}... and is {len(k)} characters long")
    for label, url, hdr in (("key in x-goog-api-key header", base, {"x-goog-api-key": k}),
                            ("key in URL (?key=)", base + "?key=" + k, {}),
                            ("key as Bearer token", base, {"Authorization": "Bearer " + k})):
        st, out, dt = post(url, hdr, body)
        txt = ""
        if isinstance(out, dict):
            txt = "".join(p.get("text", "") for c in out.get("candidates", []) for p in c.get("content", {}).get("parts", []) if not p.get("thought"))
        print(f"Gemini {config.GEMINI_MODEL} [{label}]: {st} in {dt:.1f}s -> {txt or out}")
else:
    print("Gemini: no GEMINI_API_KEY in backend/.env")

if config.GROQ_API_KEY:
    st, out, dt = post("https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {config.GROQ_API_KEY}", "User-Agent": "jarvis"},
                       {"model": config.GROQ_MODEL, "max_completion_tokens": 100, "messages": [{"role": "user", "content": "Say namaste in Hindi, one word."}]})
    txt = out["choices"][0]["message"].get("content") if isinstance(out, dict) else out
    print(f"Groq {config.GROQ_MODEL}: {st} in {dt:.1f}s -> {txt}")
else:
    print("Groq: no GROQ_API_KEY in backend/.env")

if config.CUSTOM_API_KEY or config.CUSTOM_BASE_URL or config.CUSTOM_MODEL:
    k = config.CUSTOM_API_KEY
    if not (k and config.CUSTOM_BASE_URL and config.CUSTOM_MODEL):
        print("Custom model: one of JARVIS_LLM_API_KEY / JARVIS_LLM_BASE_URL / JARVIS_LLM_MODEL is empty in backend/.env")
    elif k.startswith("PASTE"):
        print("Custom model: JARVIS_LLM_API_KEY still says PASTE_YOUR_... Put your real key there.")
    else:
        print(f"Custom model key starts with {k[:8]}... and is {len(k)} characters long")
        st, out, dt = post(config.CUSTOM_BASE_URL.rstrip("/") + "/chat/completions",
                           {"Authorization": f"Bearer {k}", "User-Agent": "jarvis"},
                           {"model": config.CUSTOM_MODEL, "max_tokens": 60, "messages": [{"role": "user", "content": "Say namaste in Hindi, one word."}]})
        txt = out["choices"][0]["message"].get("content") if isinstance(out, dict) and out.get("choices") else out
        print(f"Custom {config.CUSTOM_MODEL}: {st} in {dt:.1f}s -> {txt}")
        if st == 401:
            print("  401 = the key was not accepted. Copy the whole key again from OpenRouter (or create a new one).")
        if st == 402:
            print("  402 = no credit. Add a few dollars under Credits on openrouter.ai.")
        if st == 404 or st == 400:
            print("  The model id may be wrong. Check it at openrouter.ai/models (use the copy button next to the name).")
else:
    print("Custom model: not set up (no JARVIS_LLM_* lines in backend/.env)")

# ---- Gemini voice test: writes gemini_voice_test.wav, open it and listen ----
if config.GEMINI_API_KEY:
    import base64
    import cloud
    import voice
    print("\nGemini voice test (Hindi)...")
    try:
        data, mime = voice.GeminiTTSEngine().synth("नमस्ते! मैं जार्विस हूँ। बताइए, आज मैं आपकी क्या मदद कर सकता हूँ?", "hi", None)
        open("gemini_voice_test.wav", "wb").write(data)
        print(f"  OK: {len(data) // 1024} KB saved to gemini_voice_test.wav. Open it and listen.")
    except Exception as e:                                             # noqa: BLE001
        print(f"  Gemini voice failed: {e}")
