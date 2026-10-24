"""
Language-model layer (MLX).

    generate()      one-shot answer (used by the advisor, summaries, private reasoning notes)
    stream_text()   token-by-token answer, cancellable, with hidden <think> blocks filtered out
"""

from __future__ import annotations

import re
import threading

import config
from mlxthread import MLX
from models import _SPECIAL, clean_model_output


class ThinkFilter:
    """Turns a raw token stream into visible text: drops <think>…</think> and chat-template tokens."""

    def __init__(self):
        self.raw = ""
        self.sent = 0

    def feed(self, delta: str) -> str:
        self.raw += delta
        vis = re.sub(r"<think>.*?</think>", "", self.raw, flags=re.S)
        vis = re.sub(r"<think>.*$", "", vis, flags=re.S)
        for tok in _SPECIAL:
            vis = vis.replace(tok, "")
        hold = 0  # never emit half of a tag that is still arriving
        for tag in ("<think>",) + _SPECIAL:
            for k in range(len(tag) - 1, 0, -1):
                if vis.endswith(tag[:k]):
                    hold = max(hold, k)
                    break
        safe = vis[: len(vis) - hold] if hold else vis
        new = safe[self.sent:]
        self.sent = len(safe)
        return new


def _is_oom(e: Exception) -> bool:
    t = str(e).lower()
    return "insufficient memory" in t or "out of memory" in t or "outofmemory" in t


def free_gpu_memory():
    """Hand MLX's cached buffers back to the system (call on the MLX thread)."""
    try:
        import gc
        import mlx.core as mx
        gc.collect()
        (getattr(mx, "clear_cache", None) or mx.metal.clear_cache)()
    except Exception:                                  # noqa: BLE001
        pass


class LLM:
    """Mixin for Client. Call self._init_llm() from __init__."""

    def _init_llm(self, load_model: bool = True):
        self.model = None
        self.tokenizer = None
        self.llm_ready = False
        self.llm_lock = threading.Lock()
        if load_model:
            self._load_model()

    def _load_model(self):
        print(f"Loading AI model: {config.MODEL_NAME}   (detected {config.RAM_GB:.0f} GB memory)")
        tried = []
        if config.MODEL_NOTE:
            print(f"Model choice: {config.MODEL_NOTE}")
        for name in [config.MODEL_NAME] + ([config.FALLBACK_MODEL] if config.FALLBACK_MODEL != config.MODEL_NAME else []):
            try:
                def _load(n=name):
                    from mlx_lm import load        # imported here so MLX's streams belong to the MLX thread
                    return load(n)
                self.model, self.tokenizer = MLX.call(_load)
                self.llm_ready = True
                self.model_name = name
                print(f"AI model loaded: {name}\n")
                if tried:
                    print("    (Running on the backup model. Fix the error above to use your chosen one.)\n")
                return
            except Exception as e:
                tried.append(name)
                print(f"⚠️  Could not load {name}: {e}")
                if "gemma" in name.lower() or "sarvam" in name.lower():
                    print("    Newer models need a newer library: pip install -U mlx-lm mlx-vlm   (Python 3.10 or newer)")
        print("    Data analytics, voice, timers and tools still work; chat falls back to simple replies.\n")

    # ---------------------------------------------------------

    def _render_prompt(self, system: str, messages: list, thinking: bool | None = None) -> str:
        msgs = [{"role": "system", "content": system}] + messages
        try:
            return self._template(msgs, thinking)
        except Exception:
            folded = [dict(m) for m in messages]
            folded[0]["content"] = system + "\n\n" + folded[0]["content"]
            return self._template(folded, thinking)

    def _template(self, msgs: list, thinking: bool | None = None) -> str:
        # Qwen3 accepts enable_thinking; older templates ignore or reject it, so fall back cleanly.
        try:
            return self.tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True,
                enable_thinking=config.THINKING if thinking is None else thinking)
        except TypeError:
            return self.tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    temp_override = None            # set for the duration of a Hindi turn

    def _sampler(self):
        try:
            from mlx_lm.sample_utils import make_sampler
            temp = self.temp_override if self.temp_override is not None else config.TEMPERATURE
            try:
                return make_sampler(temp=temp, top_p=config.TOP_P, top_k=config.TOP_K)
            except TypeError:                         # older mlx-lm without top_k
                return make_sampler(temp=temp, top_p=config.TOP_P)
        except Exception:
            return None

    def _sampling_kwargs(self) -> dict:
        """Sampler plus a gentle repetition penalty (so he does not say the same sentence twice)."""
        kw = {}
        sampler = self._sampler()
        if sampler is not None:
            kw["sampler"] = sampler
        if config.REPETITION_PENALTY and config.REPETITION_PENALTY != 1.0:
            try:
                from mlx_lm.sample_utils import make_logits_processors
                kw["logits_processors"] = make_logits_processors(
                    repetition_penalty=config.REPETITION_PENALTY, repetition_context_size=64)
            except Exception:
                pass
        return kw

    def _generate_raw(self, prompt: str, max_tokens: int) -> str:
        kwargs = {"prompt": prompt, "max_tokens": max_tokens, **self._sampling_kwargs()}
        model, tok = self.model, self.tokenizer

        def work():
            from mlx_lm import generate
            kw = dict(kwargs)
            for attempt in range(3):
                try:
                    return generate(model, tok, **kw)
                except TypeError:
                    kw.pop("sampler", None)
                    kw.pop("logits_processors", None)
                except RuntimeError as e:
                    if not _is_oom(e):
                        raise
                    free_gpu_memory()
                    if attempt:
                        raise RuntimeError("The model does not fit in this Mac's GPU memory right now. Set JARVIS_MODEL=gemma4-12b "
                                           "in backend/.env (or close other apps), then restart.") from None
                finally:
                    free_gpu_memory()
            return generate(model, tok, **kw)

        with self.llm_lock:
            out = MLX.call(work)

        if isinstance(out, list):
            out = "".join(out)
        return clean_model_output(out)

    def _stream_raw(self, prompt: str, max_tokens: int, cancel: threading.Event):
        """Yield text deltas. Stops promptly when `cancel` is set."""
        kwargs = {"prompt": prompt, "max_tokens": max_tokens, **self._sampling_kwargs()}
        model, tok = self.model, self.tokenizer

        def gen():                                    # runs on the MLX thread
            from mlx_lm import stream_generate
            kw = dict(kwargs)
            oom_retry = True
            while True:
                it = stream_generate(model, tok, **kw)
                try:
                    first = next(it)
                except StopIteration:
                    return
                except TypeError:                     # older mlx-lm without the sampler argument
                    if "sampler" not in kw:
                        raise
                    kw.pop("sampler", None)
                    kw.pop("logits_processors", None)
                    continue
                except RuntimeError as e:
                    if _is_oom(e):
                        free_gpu_memory()
                        if oom_retry:                 # first time: free the cache and try once more, quietly
                            oom_retry = False
                            continue
                        raise RuntimeError("The model does not fit in this Mac's GPU memory right now. Set JARVIS_MODEL=gemma4-12b "
                                           "in backend/.env (or close other apps), then restart.") from None
                    raise
                try:
                    yield getattr(first, "text", first)
                    for resp in it:
                        yield getattr(resp, "text", resp)
                finally:
                    free_gpu_memory()                 # give cached buffers back so the next reply starts clean
                return

        with self.llm_lock:
            for delta in MLX.iterate(gen, cancel):
                if cancel.is_set():
                    break
                yield delta

    # ---------------------------------------------------------

    def generate(self, system: str, user: str, max_tokens: int) -> str:
        """One-shot generation used by the advisor and by internal helpers."""
        if not self.llm_ready:
            raise RuntimeError("language model not loaded")
        prompt = self._render_prompt(system, [{"role": "user", "content": user}])
        return self._generate_raw(prompt, max_tokens)

    def stream_text(self, system: str, messages: list, max_tokens: int, cancel: threading.Event, on_delta,
                    thinking: bool | None = None) -> str:
        prompt = self._render_prompt(system, messages, thinking)
        filt, parts = ThinkFilter(), []
        for delta in self._stream_raw(prompt, max_tokens, cancel):
            out = filt.feed(delta)
            if out:
                parts.append(out)
                on_delta(out)
        return clean_model_output("".join(parts))
