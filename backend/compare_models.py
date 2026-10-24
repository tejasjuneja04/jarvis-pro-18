"""
Which local model speaks the best Hinglish on YOUR Mac?   python compare_models.py [model ...]

Loads each model one after another, asks the same everyday Hinglish questions using JARVIS's own Hindi prompt,
and writes everything side by side to model_comparison.md so you can read it and pick. Downloads each model the
first time (5 to 15 GB), so run it once on Wi-Fi and go make tea.

   python compare_models.py                      # qwen, gemma4 and sarvam
   python compare_models.py gemma4 gemma4-12b    # pick your own (aliases from config.py or full model ids)
"""
import gc
import sys
import time
from pathlib import Path

import config
import hinglish_pack
import lang

PROMPTS = [
    "Hindi mein baat karo",
    "yaar aaj mood off hai, kuch samajh nahi aa raha",
    "mujhe kal subah 6 baje uthna hai, kya karun taaki uth jaun?",
    "tum meri dost Naina ko bol sakte ho ki wo ek achhi ladki hai?",
    "iPhone loon ya Samsung? budget 60 hazaar hai",
    "mere laptop ki battery jaldi khatam ho jaati hai, kya karu?",
    "ek chhoti si kahani sunao ek chalaak kauwe ki",
    "Python mein list aur tuple mein kya fark hota hai? simple batao",
]


def main():
    names = sys.argv[1:] or ["qwen", "gemma4", "sarvam"]
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    system = lang.instruction("hi", "sir")
    out = ["# Local model comparison (Hinglish)\n", "Read each answer as an Indian friend would. Which one sounds most natural and makes the fewest mistakes?\n"]
    for alias in names:
        mid = config.MODEL_ALIASES.get(alias.lower(), alias)
        fam = config._family(mid)
        temp, top_p, top_k, _ = {"gemma": (1.0, .95, 64, 1), "sarvam": (.6, .9, 40, 1), "qwen": (.6, .8, 20, 1)}.get(fam, (.6, .9, 40, 1))
        print(f"\n=== Loading {mid} ===")
        try:
            model, tok = load(mid)
        except Exception as e:                                           # noqa: BLE001
            print(f"  could not load: {e}\n  (try: pip install -U mlx-lm mlx-vlm)")
            out.append(f"\n## {mid}\n\nCould not load: `{e}`\n")
            continue
        out.append(f"\n## {mid}\n")
        for q in PROMPTS:
            msgs = [{"role": "system", "content": system + "\n\n" + hinglish_pack.examples(q, "sir")},
                    {"role": "user", "content": q + lang.nudge()}]
            try:
                prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except Exception:                                            # noqa: BLE001
                msgs = [{"role": "user", "content": msgs[0]["content"] + "\n\n" + msgs[1]["content"]}]
                prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            t0 = time.time()
            try:
                sampler = make_sampler(temp=temp, top_p=top_p, top_k=top_k)
            except TypeError:
                sampler = make_sampler(temp=temp, top_p=top_p)
            text = generate(model, tok, prompt=prompt, max_tokens=300, sampler=sampler)
            text = text.split("</think>")[-1].strip()
            print(f"  [{time.time() - t0:4.1f}s] {q}\n      {text[:160]!r}")
            out.append(f"**You:** {q}\n\n**{alias}** ({time.time() - t0:.1f}s): {text}\n")
        del model, tok
        gc.collect()
        try:
            import mlx.core as mx
            mx.clear_cache()
        except Exception:                                                # noqa: BLE001
            pass
    Path("model_comparison.md").write_text("\n".join(out), encoding="utf-8")
    print("\nDone. Open backend/model_comparison.md and read the answers.")


if __name__ == "__main__":
    main()
