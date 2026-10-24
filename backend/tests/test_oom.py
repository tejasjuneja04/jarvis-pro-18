import config
import llm


def test_oom_detection():
    assert llm._is_oom(RuntimeError("[METAL] Command buffer execution failed: Insufficient Memory (kIOGPUCommandBufferCallbackErrorOutOfMemory)"))
    assert not llm._is_oom(RuntimeError("something else"))


def test_gemma4_alias_matches_memory():
    want = "26b-a4b" if config.RAM_GB >= 40 else "12B"
    assert want in config.MODEL_ALIASES["gemma4"]
    assert "12B" in config.MODEL_ALIASES["gemma4-12b"] and "26b" in config.MODEL_ALIASES["gemma4-26b"]


def test_oom_retries_once_then_explains():
    import sys
    import threading
    import types
    calls = {"n": 0}
    mod = types.ModuleType("mlx_lm")
    sub = types.ModuleType("mlx_lm.sample_utils")

    def stream_generate(m, t, **kw):
        calls["n"] += 1
        raise RuntimeError("Insufficient Memory")
        yield  # pragma: no cover
    mod.stream_generate = stream_generate
    sub.make_sampler = lambda **k: None
    sub.make_logits_processors = lambda **k: None
    saved = {k: sys.modules.get(k) for k in ("mlx_lm", "mlx_lm.sample_utils")}
    sys.modules["mlx_lm"], sys.modules["mlx_lm.sample_utils"] = mod, sub
    try:
        c = type("C", (llm.LLM,), {})()
        c._init_llm(load_model=False)
        c.model, c.tokenizer = "m", "t"
        try:
            list(c._stream_raw("p", 5, threading.Event()))
            raise AssertionError("should raise")
        except RuntimeError as e:
            assert "gemma4-12b" in str(e)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    assert calls["n"] == 2
