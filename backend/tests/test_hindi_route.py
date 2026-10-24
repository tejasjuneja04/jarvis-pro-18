import cloud
import config


def _keys(claude, gemini, groq, want="auto"):
    config.ANTHROPIC_API_KEY = "x" if claude else ""
    config.GEMINI_API_KEY = "x" if gemini else ""
    config.GROQ_API_KEY = "x" if groq else ""
    config.HINDI_PROVIDER = want
    cloud._client = object() if claude else None


def test_hindi_provider_prefers_best_available():
    saved = (config.ANTHROPIC_API_KEY, config.GEMINI_API_KEY, config.GROQ_API_KEY, config.HINDI_PROVIDER, cloud._client)
    try:
        _keys(False, True, True)
        assert cloud.hindi_provider() == "gemini"
        assert cloud.provider("gemini") == "gemini" and cloud.provider("claude") != "claude"
        _keys(False, False, True)
        assert cloud.hindi_provider() == "groq"
        _keys(False, True, True, "groq")
        assert cloud.hindi_provider() == "groq"
        _keys(False, False, False)
        assert cloud.hindi_provider() == ""
    finally:
        config.ANTHROPIC_API_KEY, config.GEMINI_API_KEY, config.GROQ_API_KEY, config.HINDI_PROVIDER, cloud._client = saved


def test_fallback_when_first_provider_fails():
    saved = (config.ANTHROPIC_API_KEY, config.GEMINI_API_KEY, config.GROQ_API_KEY, config.HINDI_PROVIDER, cloud._client, cloud._stream_one)
    got = []
    calls = []

    def fake(pv, system, messages, max_tokens, cancel, on_delta, deep=False, prepared=False, temperature=0.8):
        calls.append(pv)
        if pv == "gemini":
            raise RuntimeError("Gemini did not answer within 40s")
        on_delta("namaste")
        return "namaste"
    try:
        _keys(False, True, True)
        cloud._stream_one = fake
        out = cloud.stream_text("s", [{"role": "user", "content": "hi"}], 50, None, got.append, prefer="gemini")
    finally:
        config.ANTHROPIC_API_KEY, config.GEMINI_API_KEY, config.GROQ_API_KEY, config.HINDI_PROVIDER, cloud._client, cloud._stream_one = saved
    assert out == "namaste" and calls == ["gemini", "groq"] and got == ["namaste"]


def test_gemini_400_retries_with_next_thinking_setting():
    import io
    import urllib.error
    import urllib.request
    saved = (config.GEMINI_API_KEY, config.GEMINI_MODEL, urllib.request.urlopen)
    bodies = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_open(req, timeout=None):
        import json
        bodies.append(json.loads(req.data.decode()))
        if len(bodies) == 1:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b"bad thinking level"))
        return Resp(b'data: {"candidates":[{"content":{"parts":[{"text":"namaste"}]},"finishReason":"STOP"}]}\n')
    try:
        config.GEMINI_API_KEY, config.GEMINI_MODEL = "k", "gemini-3.8-flash"
        urllib.request.urlopen = fake_open
        out = cloud._gemini_stream("s", [{"role": "user", "content": "hi"}], 50, None, lambda t: None)
    finally:
        config.GEMINI_API_KEY, config.GEMINI_MODEL, urllib.request.urlopen = saved
    assert out == "namaste" and len(bodies) == 2
    assert bodies[0]["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert bodies[1]["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "low"


def test_gemini_switches_key_style_on_auth_error():
    import io
    import urllib.error
    import urllib.request
    saved = (config.GEMINI_API_KEY, config.GEMINI_MODEL, urllib.request.urlopen, cloud._gemini_auth[0])
    seen = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_open(req, timeout=None):
        hdr = {k.lower(): v for k, v in req.header_items()}
        style = "header" if "x-goog-api-key" in hdr else "query" if "key=" in req.full_url else "bearer"
        seen.append(style)
        if style != "query":
            raise urllib.error.HTTPError(req.full_url, 400, "Bad", {}, io.BytesIO(b'{"error":{"message":"API key not valid."}}'))
        return Resp(b'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}\n')
    try:
        config.GEMINI_API_KEY, config.GEMINI_MODEL = "AQ.k", "gemini-3.8-flash"
        cloud._gemini_auth[0] = "header"
        urllib.request.urlopen = fake_open
        out = cloud._gemini_stream("s", [{"role": "user", "content": "hi"}], 50, None, lambda t: None)
    finally:
        config.GEMINI_API_KEY, config.GEMINI_MODEL, urllib.request.urlopen, cloud._gemini_auth[0] = saved
    assert out == "ok" and seen == ["header", "query"]


def test_custom_provider_streams_and_retries_token_field():
    import io
    import json
    import urllib.error
    import urllib.request
    saved = (config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL, urllib.request.urlopen)
    payloads = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_open(req, timeout=None):
        payloads.append((req.full_url, json.loads(req.data.decode())))
        if len(payloads) == 1:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad", {}, io.BytesIO(b"unsupported parameter max_completion_tokens"))
        return Resp(b'data: {"choices":[{"delta":{"content":"namaste"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
    try:
        config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL = "k", "https://x.test/v1/", "m"
        urllib.request.urlopen = fake_open
        out = cloud._custom_stream("s", [{"role": "user", "content": "hi"}], 50, None, lambda t: None)
        assert cloud._has("custom") and cloud.provider() == "custom"
    finally:
        config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL, urllib.request.urlopen = saved
    assert out == "namaste" and payloads[0][0] == "https://x.test/v1/chat/completions"
    assert "max_completion_tokens" in payloads[0][1] and "max_completion_tokens" not in payloads[1][1] and payloads[1][1]["max_tokens"] == 50


def test_low_credit_retries_with_smaller_reply():
    import io
    import json
    import urllib.error
    import urllib.request
    saved = (config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL, urllib.request.urlopen)
    sent = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_open(req, timeout=None):
        body = json.loads(req.data.decode())
        sent.append(body.get("max_completion_tokens"))
        if body.get("max_completion_tokens") == 4000:
            msg = b'{"error":{"message":"You requested up to 4000 tokens, but can only afford 3887."}}'
            raise urllib.error.HTTPError(req.full_url, 402, "Payment", {}, io.BytesIO(msg))
        return Resp(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
    try:
        config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL = "k", "https://x.test/v1", "m"
        urllib.request.urlopen = fake_open
        out = cloud._custom_stream("s", [{"role": "user", "content": "hi"}], 4000, None, lambda t: None)
    finally:
        config.CUSTOM_API_KEY, config.CUSTOM_BASE_URL, config.CUSTOM_MODEL, urllib.request.urlopen = saved
    assert out == "ok" and sent == [4000, 3867]
