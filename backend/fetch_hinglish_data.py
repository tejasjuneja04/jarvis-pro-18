"""
Build a clean Hinglish example file for JARVIS from a big public dataset.   python fetch_hinglish_data.py [--keep 4000]

Downloads Abhishekcr448/Hinglish-Everyday-Conversations-1M (about 1 million short Roman Hinglish exchanges, MIT licence,
machine-generated so it is noisy), throws away the bad rows and keeps the best few thousand in
backend/hinglish_data/community_filtered.jsonl. JARVIS shows the most relevant ones to the model on every Hindi message.

What is filtered out: Devanagari or English-heavy lines, links, rude or slangy replies, 'tu/tera' replies (JARVIS says "aap"),
feminine first-person forms (JARVIS is male), one-word and rambling lines, repeats and near-repeats, replies that just echo the
question. What is preferred: real Hindi vocabulary, "aap", natural length, a reply that actually answers.
It cannot judge meaning perfectly, so it prints 15 random samples at the end: read them, and delete the file if they look bad.
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

REPO = "Abhishekcr448/Hinglish-Everyday-Conversations-1M"
OUT = Path(__file__).resolve().parent / "hinglish_data" / "community_filtered.jsonl"

HINDI = set("""
hai hain tha thi the hoga hogi honge ho hoon hun raha rahi rahe kar karo karna karta karte karti kiya kiye kya kyu kyun kaise kaisa
kaisi kab kahan kaun kaunsa kitna kitni kitne mujhe mera meri mere main mai hum humne hamara tum tumhe tumhara aap aapko aapka aapki
aapke aapne yeh ye woh wo is us isko usko isme usme se ko ka ki ke mein me par pe aur ya bhi toh to nahi nahin na haan han ji accha
acha achha theek thik bilkul zaroor jarur abhi aaj kal subah shaam raat din baad pehle phir fir ab tab jab tak kuch koi sab bahut
bohot thoda zyada jyada kam lekin magar kyunki isliye agar toh chahiye chahta chahte sakta sakte sakti milega mil gaya gayi gaye
jaana jaao jao aana aao aaya aaye dekho dekhna dekha suno sunna bolo bolna bola batao batana bataya samajh samjha samjhe lagta lagti
lag raha rahi wala wali wale liye liya diya do dena lena le de ghar kaam khana chai paani yaar bhai dost pata matlab waise sach
sahi galat mushkil aasaan jaldi der kal parso mausam baarish garmi sardi paisa paise
""".split())
ENGLISH = set("""
the a an and or but if then so because i you he she it we they me him her us them my your his its our their am is are was were be been
being do does did have has had will would can could should may might must to of in on at by for with from as that this these those
what when where why how who which just really very much more most some any not no yes ok okay hey hi hello bro dude man chilling
home work phone movie music game party weekend""".split())
RUDE = set("""saala sala saale bc mc bsdk chutiya chutiye madarchod behenchod bhosdike gandu harami kamina kamine kutta kutte randi lund gaand
fuck fucking shit bitch ass damn abe abey oye""".split())
TU = re.compile(r"\b(?:tu|tera|teri|tere|tujhe|tujhse|tujhko|tumhara|tumhari|tumhare|tumne|tumse|tumhe|tum)\b", re.I)
FEMININE = re.compile(r"\b(?:karti|rahi hoon|rahi hu|sakti|chahti|gayi|gai|aati|jaati|jati|khaati|piti|soti|hoon na)\b|\bmain .*\b(?:thi|ayi|aayi)\b", re.I)
WORD = re.compile(r"[A-Za-z']+")
FIX = {"nahin": "nahi", "nhi": "nahi", "nai": "nahi", "kr": "kar", "krna": "karna", "hu": "hoon", "h": "hai", "bhut": "bahut", "bohot": "bahut",
       "acha": "accha", "achha": "accha", "thik": "theek", "jyada": "zyada", "jarur": "zaroor", "mujhko": "mujhe"}


def words(t: str) -> list:
    return [w.lower() for w in WORD.findall(t)]


def clean(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "").strip().strip('"\'`'))
    return re.sub(r"\s+([?!.,])", r"\1", t)


def fix_spelling(t: str) -> str:
    return re.sub(r"[A-Za-z']+", lambda m: FIX.get(m.group(0).lower(), m.group(0)) if m.group(0).islower() else m.group(0), t)


def hindi_ratio(ws: list) -> float:
    return sum(w in HINDI for w in ws) / len(ws) if ws else 0.0


def english_ratio(ws: list) -> float:
    return sum(w in ENGLISH and w not in HINDI for w in ws) / len(ws) if ws else 1.0


def score_pair(user: str, reply: str):
    """Return a quality score (higher is better) or None to reject the pair."""
    user, reply = clean(user), clean(reply)
    if not user or not reply or user.lower() == reply.lower():
        return None
    for t in (user, reply):
        if re.search(r"[ऀ-ॿ]|https?:|www\.|@|#|\d{4,}|[<>{}\[\]|\\_*]", t) or t.count("?") > 2:
            return None
    uw, rw = words(user), words(reply)
    if not (2 <= len(uw) <= 18 and 3 <= len(rw) <= 24):
        return None
    if set(rw) & RUDE or set(uw) & RUDE or TU.search(reply) or FEMININE.search(reply):
        return None
    if hindi_ratio(rw) < 0.35 or hindi_ratio(uw) < 0.2 or english_ratio(rw) > 0.4:
        return None
    if len(set(rw) & set(uw)) / max(1, len(set(rw))) > 0.6:                      # just echoes the question
        return None
    if reply.endswith("?") and len(rw) <= 4:                                      # a bare question back is no answer
        return None
    s = hindi_ratio(rw) + 0.3 * hindi_ratio(uw)
    s += 0.25 if "aap" in rw else 0
    s += 0.15 if 6 <= len(rw) <= 16 else 0
    s += 0.1 if reply[0].isupper() else 0
    s -= 0.2 * english_ratio(rw)
    return s


def select(rows, keep: int = 4000, seed: int = 7):
    """rows: iterable of (user, reply). Returns the best `keep` pairs, de-duplicated."""
    random.seed(seed)
    seen_u, per_reply, per_sig, scored = set(), Counter(), Counter(), []
    for user, reply in rows:
        s = score_pair(user, reply)
        if s is None:
            continue
        user, reply = fix_spelling(clean(user)), fix_spelling(clean(reply))
        ku, kr = re.sub(r"\W+", " ", user.lower()).strip(), re.sub(r"\W+", " ", reply.lower()).strip()
        sig = " ".join(ku.split()[:3])
        if ku in seen_u or per_reply[kr] >= 2 or per_sig[sig] >= 3:
            continue
        seen_u.add(ku)
        per_reply[kr] += 1
        per_sig[sig] += 1
        scored.append((s + random.random() * 0.05, user, reply))
    scored.sort(reverse=True)
    return [(u, r) for _, u, r in scored[:keep]]


def read_rows(limit: int | None = None):
    from huggingface_hub import snapshot_download
    print(f"Downloading {REPO} (about 185 MB, once)...")
    folder = Path(snapshot_download(REPO, repo_type="dataset", allow_patterns=["*.csv", "*.parquet", "*.json*"]))
    files = sorted(folder.rglob("*.csv"))
    if not files:
        sys.exit("No CSV found in the dataset download. Tell me and I will adapt this script.")
    csv.field_size_limit(10_000_000)
    n = 0
    for f in files:
        with f.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                u = row.get("input") or row.get("user") or ""
                r = row.get("output") or row.get("reply") or ""
                yield u, r
                n += 1
                if limit and n >= limit:
                    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=4000, help="how many pairs to keep (default 4000)")
    ap.add_argument("--limit", type=int, default=0, help="only read this many rows (for a quick test)")
    args = ap.parse_args()
    best = select(read_rows(args.limit or None), args.keep)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for u, r in best:
            fh.write(json.dumps({"user": u, "reply": r}, ensure_ascii=False) + "\n")
    print(f"\nKept {len(best)} pairs -> {OUT}\n\n15 random samples. Read them: do they sound like a smart Indian friend?\n")
    for u, r in random.sample(best, min(15, len(best))):
        print(f"  you:    {u}\n  jarvis: {r}\n")
    print("Restart JARVIS to use them. If the samples look bad, delete the file and tell me what is wrong.")


if __name__ == "__main__":
    main()
