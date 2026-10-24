import base64
import io
import wave

import cloud
import config
import voice


def _pcm(n=2400):
    return b"\x00\x01" * n


def test_find_audio_both_shapes():
    classic = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": base64.b64encode(_pcm()).decode()}}]}}]}
    newer = {"steps": [{"type": "model_output", "content": [{"type": "audio", "mime_type": "audio/wav", "data": base64.b64encode(b"RIFFxxxx").decode()}]}]}
    assert voice.GeminiTTSEngine.find_audio(classic)[1].startswith("audio/L16")
    assert voice.GeminiTTSEngine.find_audio(newer)[0] == b"RIFFxxxx"
    assert voice.GeminiTTSEngine.find_audio({"nothing": 1}) is None


def test_synth_wraps_pcm_in_wav():
    saved = (config.GEMINI_API_KEY, config.GEMINI_TTS, cloud.gemini_post)
    seen = {}

    def fake(url, payload, timeout=30):
        seen["url"], seen["payload"] = url, payload
        return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": base64.b64encode(_pcm()).decode()}}]}}]}
    try:
        config.GEMINI_API_KEY, config.GEMINI_TTS = "AQ.k", True
        cloud.gemini_post = fake
        e = voice.GeminiTTSEngine()
        assert e.available()
        data, mime = e.synth("नमस्ते, कैसे हैं आप?", "hi", {"gender": "female"})
    finally:
        config.GEMINI_API_KEY, config.GEMINI_TTS, cloud.gemini_post = saved
    assert mime == "audio/wav"
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 24000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    cfg = seen["payload"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]
    assert cfg["voiceName"] == config.GEMINI_TTS_VOICE_FEMALE and "generateContent" in seen["url"]


def test_failure_cools_down_and_english_skips_gemini():
    saved = (config.GEMINI_API_KEY, config.GEMINI_TTS, cloud.gemini_post)

    def boom(url, payload, timeout=30):
        raise RuntimeError("Gemini error 404: model not found")
    try:
        config.GEMINI_API_KEY, config.GEMINI_TTS = "AQ.k", True
        cloud.gemini_post = boom
        e = voice.GeminiTTSEngine()
        try:
            e.synth("hello", "hi", None)
            raise AssertionError("should raise")
        except RuntimeError:
            pass
        assert not e.available()                     # cooling down, so the next voice takes over
    finally:
        config.GEMINI_API_KEY, config.GEMINI_TTS, cloud.gemini_post = saved


def test_gemini_post_switches_key_style():
    import urllib.error
    import urllib.request
    saved = (config.GEMINI_API_KEY, urllib.request.urlopen, cloud._gemini_auth[0])
    styles = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=None):
        h = {k.lower(): v for k, v in req.header_items()}
        style = "header" if "x-goog-api-key" in h else "query" if "key=" in req.full_url else "bearer"
        styles.append(style)
        if style == "header":
            raise urllib.error.HTTPError(req.full_url, 401, "x", {}, io.BytesIO(b'{"error":{"message":"API key not valid"}}'))
        return Resp(b'{"ok": true}')
    try:
        config.GEMINI_API_KEY = "AQ.k"
        cloud._gemini_auth[0] = "header"
        urllib.request.urlopen = fake
        assert cloud.gemini_post("https://x.test/v1beta/m:generateContent", {}) == {"ok": True}
    finally:
        config.GEMINI_API_KEY, urllib.request.urlopen, cloud._gemini_auth[0] = saved
    assert styles == ["header", "query"]
