"""
Everyday life helpers, all offline and stored on this computer:

  Notes       "note: call the bank tomorrow" · "show my notes" · "search notes for bank" · "delete note 2"
  Expenses    "I spent 250 on lunch" · "show expenses" · "how much did I spend this month" · "undo expense"
  Converter   "convert 5 km to miles" · "100 f to c" · "10 kg in pounds"
  World clock "time in Tokyo" · "what time is it in New York"
  Split bill  "split 2400 among 4" · "split 2400 among 4 with 10% tip"
  Dice & co.  "roll a dice" · "flip a coin" · "random number between 1 and 50" · "generate a password"
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from skills import _Store

_notes = _exp = None


def _stores():
    global _notes, _exp
    if _notes is None:
        _notes = _Store(config.NOTES_FILE, {"notes": []})
        _exp = _Store(config.EXPENSES_FILE, {"items": []})
        _notes.data.setdefault("notes", [])
        _exp.data.setdefault("items", [])
    return _notes, _exp


def _money(n: float) -> str:
    return f"₹{n:,.0f}" if abs(n - round(n)) < 0.005 else f"₹{n:,.2f}"


# ------------------------------------------------------------------------------------------ notes

def notes(text: str):
    ns, _ = _stores()
    items = ns.data["notes"]
    t = text.strip()
    low = t.lower().rstrip("?!. ")
    m = re.match(r"^(?:note|jot down|add (?:a )?note|save (?:a )?note|take (?:a )?note)\s*[:\-]?\s+(?!that\b)(.+)$", t, re.I | re.S)
    if m:
        items.append({"text": m.group(1).strip(), "at": datetime.now().isoformat(timespec="minutes")})
        ns.save()
        return f"📝 Noted ({len(items)} saved)."
    if re.match(r"^(?:show|list|open|see|read)?\s*(?:me\s+)?(?:all\s+)?(?:my\s+)?notes$", low) and low != "notes" or low in ("notes", "my notes"):
        if not items:
            return "You have no notes yet. Say “note: …” to add one."
        return "📝 Your notes\n" + "\n".join(f"{i}. {n['text']}  ·  {n['at'][5:10]}" for i, n in enumerate(items[-20:], max(1, len(items) - 19)))
    m = re.match(r"^search notes? (?:for )?(.+)$", low)
    if m:
        hits = [(i, n) for i, n in enumerate(items, 1) if m.group(1) in n["text"].lower()]
        return "\n".join(f"{i}. {n['text']}" for i, n in hits) if hits else "No notes match that."
    m = re.match(r"^(?:delete|remove) note (\d+)$", low)
    if m:
        i = int(m.group(1)) - 1
        if 0 <= i < len(items):
            gone = items.pop(i)
            ns.save()
            return f"Deleted: {gone['text']}"
        return "There is no note with that number."
    if re.match(r"^(?:clear|delete) (?:all )?notes$", low):
        items.clear()
        ns.save()
        return "All notes cleared."
    return None


# ------------------------------------------------------------------------------------------ expenses

CATS = {
    "food": r"lunch|dinner|breakfast|food|coffee|tea|snack|pizza|burger|restaurant|swiggy|zomato|groceries|grocery|chai|biryani",
    "travel": r"uber|ola|cab|taxi|petrol|fuel|metro|bus|train|flight|auto|ticket|travel",
    "shopping": r"clothes|shoes|amazon|flipkart|shopping|shirt|gift|phone|laptop",
    "bills": r"rent|bill|electricity|wifi|internet|recharge|subscription|netflix|spotify|emi",
    "fun": r"movie|game|party|concert|drinks|bar|outing",
    "health": r"doctor|medicine|pharmacy|gym|hospital",
}


def category(desc: str) -> str:
    for c, rx in CATS.items():
        if re.search(rf"\b(?:{rx})\b", desc.lower()):
            return c
    return "other"


EXP_RE = re.compile(
    r"^(?:i\s+)?(?:spent|paid|bought|gave)\s+(?:rs\.?|₹|inr|\$)?\s*(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?:rupees|rs|inr|bucks)?\s*(?:on|for|in)?\s*(?P<d>.*)$|"
    r"^(?:log|add|record)\s+(?:an?\s+)?expense\s*[:\-]?\s*(?:rs\.?|₹)?\s*(?P<a2>\d[\d,]*(?:\.\d+)?)\s*(?:on|for)?\s*(?P<d2>.*)$", re.I)


def expenses(text: str):
    _, es = _stores()
    items = es.data["items"]
    t = text.strip().rstrip(".!")
    low = t.lower().rstrip("?")
    m = EXP_RE.match(t)
    if m:
        amt = float((m.group("a") or m.group("a2")).replace(",", ""))
        desc = (m.group("d") if m.group("a") else m.group("d2")).strip() or "misc"
        c = category(desc)
        items.append({"amt": amt, "desc": desc, "cat": c, "at": datetime.now().isoformat(timespec="minutes")})
        es.save()
        today = datetime.now().strftime("%Y-%m")
        month = sum(i["amt"] for i in items if i["at"].startswith(today))
        return f"💸 Logged {_money(amt)} for {desc} ({c}). This month so far: {_money(month)}."
    if re.match(r"^undo (?:last )?expense$", low):
        if not items:
            return "No expenses to undo."
        g = items.pop()
        es.save()
        return f"Removed {_money(g['amt'])} for {g['desc']}."
    if re.match(r"^(?:clear|delete) (?:all )?expenses$", low):
        items.clear()
        es.save()
        return "Expenses cleared."
    if re.search(r"\b(?:show|list|my|view)\b.*\bexpenses?\b|\bexpenses?\b.*\b(?:report|summary|so far|this month)\b|"
                 r"\bhow much (?:have i|did i) (?:spent|spend)\b|\bspending (?:summary|report)\b", low):
        if not items:
            return "No expenses logged yet. Try “I spent 250 on lunch”."
        now = datetime.now()
        period = "today" if "today" in low else "this week" if "week" in low else "this month" if ("month" in low or True) else ""
        if period == "today":
            sel = [i for i in items if i["at"].startswith(now.strftime("%Y-%m-%d"))]
        elif period == "this week":
            sel = [i for i in items if (now - datetime.fromisoformat(i["at"])).days < 7]
        else:
            sel = [i for i in items if i["at"].startswith(now.strftime("%Y-%m"))]
        if not sel:
            return f"Nothing logged {period}."
        total = sum(i["amt"] for i in sel)
        by: dict = {}
        for i in sel:
            by[i["cat"]] = by.get(i["cat"], 0) + i["amt"]
        rows = "\n".join(f"| {c} | {_money(v)} | {v / total * 100:.0f}% |" for c, v in sorted(by.items(), key=lambda x: -x[1]))
        last = "\n".join(f"• {i['desc']}: {_money(i['amt'])}" for i in sel[-5:])
        return f"💸 Spending {period}: {_money(total)} across {len(sel)} items\n\n| Category | Spent | Share |\n|---|---|---|\n{rows}\n\nLatest\n{last}"
    return None


# ------------------------------------------------------------------------------------------ converter

LEN = {"mm": .001, "cm": .01, "m": 1, "meter": 1, "meters": 1, "metre": 1, "metres": 1, "km": 1000, "kilometer": 1000, "kilometers": 1000,
       "in": .0254, "inch": .0254, "inches": .0254, "ft": .3048, "feet": .3048, "foot": .3048, "yd": .9144, "yard": .9144, "yards": .9144,
       "mile": 1609.344, "miles": 1609.344, "mi": 1609.344}
MASS = {"mg": 1e-6, "g": 1e-3, "gram": 1e-3, "grams": 1e-3, "kg": 1, "kilo": 1, "kilos": 1, "kilogram": 1, "kilograms": 1,
        "lb": .45359237, "lbs": .45359237, "pound": .45359237, "pounds": .45359237, "oz": .0283495, "ounce": .0283495, "ounces": .0283495,
        "ton": 1000, "tonne": 1000}
VOL = {"ml": .001, "l": 1, "litre": 1, "litres": 1, "liter": 1, "liters": 1, "gal": 3.78541, "gallon": 3.78541, "gallons": 3.78541,
       "cup": .236588, "cups": .236588, "tsp": .00492892, "tbsp": .0147868}
SPEED = {"kmh": 1, "kph": 1, "km/h": 1, "mph": 1.609344, "m/s": 3.6, "knot": 1.852, "knots": 1.852}
DATA = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3, "tb": 1024 ** 4}
TEMP = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}
GROUPS = (LEN, MASS, VOL, SPEED, DATA)
CONV_RE = re.compile(r"^(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*°?\s*([a-z/]+)\s+(?:to|in|into|=)\s+°?([a-z/]+)$", re.I)


def convert(text: str):
    m = CONV_RE.match(text.strip().rstrip("?!. "))
    if not m:
        return None
    v, a, b = float(m.group(1)), m.group(2).lower(), m.group(3).lower()
    if a in TEMP and b in TEMP:
        k = v if a[0] == "k" else v + 273.15 if a[0] == "c" else (v - 32) * 5 / 9 + 273.15
        out = k if b[0] == "k" else k - 273.15 if b[0] == "c" else (k - 273.15) * 9 / 5 + 32
    else:
        grp = next((g for g in GROUPS if a in g and b in g), None)
        if not grp:
            return None
        out = v * grp[a] / grp[b]
    return f"{v:g} {a} = {out:,.4g} {b}" if abs(out) < 1e6 else f"{v:g} {a} = {out:,.0f} {b}"


# ------------------------------------------------------------------------------------------ clock, split, dice

ZONES = {"tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo", "new york": "America/New_York", "nyc": "America/New_York", "london": "Europe/London",
         "uk": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin", "dubai": "Asia/Dubai", "singapore": "Asia/Singapore",
         "sydney": "Australia/Sydney", "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "california": "America/Los_Angeles",
         "chicago": "America/Chicago", "toronto": "America/Toronto", "hong kong": "Asia/Hong_Kong", "beijing": "Asia/Shanghai",
         "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "india": "Asia/Kolkata", "moscow": "Europe/Moscow", "seoul": "Asia/Seoul",
         "bangkok": "Asia/Bangkok", "cairo": "Africa/Cairo", "johannesburg": "Africa/Johannesburg", "sao paulo": "America/Sao_Paulo"}


def world_clock(text: str):
    m = re.search(r"\btime\s+(?:is it\s+)?in\s+([a-z ]+?)\s*$", text.lower().strip().rstrip("?!. "))
    if not m:
        return None
    place = m.group(1).strip()
    tz = ZONES.get(place)
    if not tz:
        return None
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        return "I couldn't load that time zone on this machine."
    return f"🕒 {place.title()}: {now.strftime('%I:%M %p, %a %d %b').lstrip('0')}"


def split_bill(text: str):
    m = re.search(r"\bsplit\s+(?:rs\.?|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(?:rupees|rs)?\s+(?:among|between|by|with|ways?)\s*(\d+)", text.lower())
    if not m:
        return None
    total, n = float(m.group(1).replace(",", "")), int(m.group(2))
    if n < 1:
        return None
    tip = re.search(r"(\d+(?:\.\d+)?)\s*%\s*tip|tip\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%", text.lower())
    pct = float(next(g for g in tip.groups() if g)) if tip else 0
    grand = total * (1 + pct / 100)
    extra = f" (with {pct:g}% tip, total {_money(grand)})" if pct else ""
    return f"🧾 {_money(total)} among {n}{extra}: {_money(grand / n)} each."


def dice(text: str):
    low = text.lower().strip().rstrip("?!. ")
    if re.search(r"\b(?:roll|throw)\s+(?:a\s+|the\s+)?(?:dice|die)\b", low):
        return f"🎲 {secrets.randbelow(6) + 1}"
    if re.search(r"\b(?:flip|toss)\s+(?:a\s+)?coin\b", low):
        return "🪙 " + secrets.choice(["Heads", "Tails"])
    m = re.search(r"\brandom number (?:between|from)\s+(-?\d+)\s+(?:and|to)\s+(-?\d+)", low)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return f"🎯 {a + secrets.randbelow(b - a + 1)}"
    if re.search(r"\b(?:generate|make|create|give me)\s+(?:a\s+)?(?:\d{2}\s*(?:-?\s*(?:char\w*|digit|letter)s?)?\s+)?(?:strong\s+|random\s+|secure\s+)?password\b", low):
        n = re.search(r"(\d{2})\s*(?:-?\s*(?:char|digit|letter)|\s+password)", low)
        n = min(64, max(8, int(n.group(1)))) if n else 16
        pool = string.ascii_letters + string.digits + "!@#$%^&*-_"
        pw = "".join(secrets.choice(pool) for _ in range(n))
        return f"🔐 {pw}\n\nI don't store this. Copy it into your password manager."
    return None


def handle(text: str):
    for f in (notes, expenses, convert, world_clock, split_bill, dice):
        r = f(text)
        if r:
            return r
    return None
