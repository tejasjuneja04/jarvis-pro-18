"""
English words spoken the way an Indian speaker says them inside a Hindi sentence.

The Hindi voices read Latin letters with an English accent, so "whistle" or "potato" sound foreign in the
middle of Hindi. Respelling the word in Devanagari makes the same voice say it with a Hindi accent, which is
how people really talk in Hinglish ("प्रेशर कुकर", "आलू बॉइल"). Only used for the voice, never shown on screen.

Add your own words in hinglish_data/loanwords.json:  {"whistle": "सीटी", "laptop": "लैपटॉप"}
"""

from __future__ import annotations

import json
import os
import re

_BASE = {
    # kitchen
    "pressure": "प्रेशर", "cooker": "कुकर", "whistle": "सीटी", "boil": "बॉइल", "boiled": "बॉइल", "boiling": "बॉइलिंग",
    "potato": "पोटैटो", "potatoes": "पोटैटो", "tomato": "टमाटर", "onion": "ऑनियन", "rice": "राइस", "dal": "दाल",
    "salt": "सॉल्ट", "water": "वॉटर", "oil": "ऑयल", "gas": "गैस", "flame": "फ्लेम", "stove": "स्टोव", "lid": "ढक्कन",
    "minute": "मिनट", "minutes": "मिनट", "hour": "घंटा", "hours": "घंटे", "second": "सेकंड", "seconds": "सेकंड",
    "time": "टाइम", "cooking": "कुकिंग", "recipe": "रेसिपी", "fry": "फ्राई", "bake": "बेक", "steam": "स्टीम",
    "soak": "सोक", "medium": "मीडियम", "low": "लो", "high": "हाई", "sugar": "शुगर", "milk": "मिल्क", "tea": "टी",
    "coffee": "कॉफ़ी", "bread": "ब्रेड", "egg": "एग", "eggs": "एग", "chicken": "चिकन", "paneer": "पनीर",
    # tech
    "phone": "फ़ोन", "mobile": "मोबाइल", "laptop": "लैपटॉप", "computer": "कंप्यूटर", "file": "फ़ाइल", "files": "फ़ाइल",
    "folder": "फ़ोल्डर", "data": "डेटा", "dataset": "डेटासेट", "chart": "चार्ट", "graph": "ग्राफ़", "table": "टेबल",
    "app": "ऐप", "apps": "ऐप्स", "software": "सॉफ़्टवेयर", "internet": "इंटरनेट", "wifi": "वाई-फ़ाई", "wi-fi": "वाई-फ़ाई",
    "bluetooth": "ब्लूटूथ", "battery": "बैटरी", "charge": "चार्ज", "charger": "चार्जर", "screen": "स्क्रीन",
    "screenshot": "स्क्रीनशॉट", "camera": "कैमरा", "photo": "फ़ोटो", "video": "वीडियो", "music": "म्यूज़िक",
    "song": "सॉन्ग", "songs": "सॉन्ग्स", "play": "प्ले", "pause": "पॉज़", "stop": "स्टॉप", "start": "स्टार्ट",
    "open": "ओपन", "close": "क्लोज़", "click": "क्लिक", "button": "बटन", "link": "लिंक", "email": "ईमेल", "mail": "मेल",
    "message": "मैसेज", "messages": "मैसेज", "whatsapp": "व्हाट्सऐप", "google": "गूगल", "youtube": "यूट्यूब",
    "chrome": "क्रोम", "search": "सर्च", "download": "डाउनलोड", "upload": "अपलोड", "save": "सेव", "delete": "डिलीट",
    "copy": "कॉपी", "paste": "पेस्ट", "password": "पासवर्ड", "login": "लॉगिन", "online": "ऑनलाइन", "offline": "ऑफ़लाइन",
    "update": "अपडेट", "setting": "सेटिंग", "settings": "सेटिंग्स", "mode": "मोड", "voice": "वॉइस", "mic": "माइक",
    "volume": "वॉल्यूम", "brightness": "ब्राइटनेस", "system": "सिस्टम", "memory": "मेमोरी", "storage": "स्टोरेज",
    "server": "सर्वर", "cloud": "क्लाउड", "model": "मॉडल", "code": "कोड", "python": "पाइथन", "error": "एरर",
    "bug": "बग", "test": "टेस्ट", "report": "रिपोर्ट", "result": "रिज़ल्ट", "score": "स्कोर", "match": "मैच",
    # daily life
    "weather": "वेदर", "temperature": "टेंपरेचर", "rain": "रेन", "alarm": "अलार्म", "timer": "टाइमर", "reminder": "रिमाइंडर",
    "meeting": "मीटिंग", "office": "ऑफ़िस", "class": "क्लास", "exam": "एग्ज़ाम", "school": "स्कूल", "college": "कॉलेज",
    "doctor": "डॉक्टर", "hospital": "हॉस्पिटल", "medicine": "मेडिसिन", "train": "ट्रेन", "bus": "बस", "flight": "फ़्लाइट",
    "ticket": "टिकट", "hotel": "होटल", "bank": "बैंक", "account": "अकाउंट", "payment": "पेमेंट", "money": "मनी",
    "rupees": "रुपये", "budget": "बजट", "expense": "खर्चा", "expenses": "खर्चे", "bill": "बिल", "shopping": "शॉपिंग",
    "order": "ऑर्डर", "delivery": "डिलीवरी", "traffic": "ट्रैफ़िक", "road": "रोड", "car": "कार", "bike": "बाइक",
    "movie": "मूवी", "film": "फ़िल्म", "news": "न्यूज़", "game": "गेम", "cricket": "क्रिकेट", "football": "फुटबॉल",
    "birthday": "बर्थडे", "party": "पार्टी", "gift": "गिफ़्ट", "holiday": "हॉलिडे", "trip": "ट्रिप", "plan": "प्लान",
    "problem": "प्रॉब्लम", "solution": "सॉल्यूशन", "idea": "आइडिया", "tip": "टिप", "tips": "टिप्स", "step": "स्टेप",
    "steps": "स्टेप्स", "option": "ऑप्शन", "options": "ऑप्शन्स", "list": "लिस्ट", "note": "नोट", "notes": "नोट्स",
    "task": "टास्क", "tasks": "टास्क", "calendar": "कैलेंडर", "today": "टुडे", "tomorrow": "टुमॉरो", "sir": "सर",
    "madam": "मैडम", "friend": "फ़्रेंड", "sorry": "सॉरी", "thanks": "थैंक्स", "please": "प्लीज़", "okay": "ओके",
    "ok": "ओके", "hello": "हैलो", "bye": "बाय", "welcome": "वेलकम", "special": "स्पेशल", "perfect": "परफ़ेक्ट",
    "simple": "सिंपल", "easy": "ईज़ी", "best": "बेस्ट", "good": "गुड", "super": "सुपर", "nice": "नाइस", "free": "फ़्री",
    "fresh": "फ्रेश", "fast": "फ़ास्ट", "slow": "स्लो", "full": "फ़ुल", "extra": "एक्स्ट्रा", "total": "टोटल",
    "number": "नंबर", "percent": "परसेंट", "average": "एवरेज", "sample": "सैंपल", "design": "डिज़ाइन",
    "photo": "फ़ोटो", "selfie": "सेल्फ़ी", "profile": "प्रोफ़ाइल", "post": "पोस्ट", "share": "शेयर", "like": "लाइक",
    "comment": "कमेंट", "channel": "चैनल", "subscribe": "सब्सक्राइब", "reel": "रील", "status": "स्टेटस",
    "soft": "सॉफ़्ट", "hard": "हार्ड", "ready": "रेडी", "cook": "कुक", "cooked": "कुक्ड", "done": "डन", "enough": "इनफ़", "add": "ऐड", "mix": "मिक्स", "wait": "वेट", "heat": "हीट", "hot": "हॉट", "cold": "कोल्ड", "normal": "नॉर्मल", "natural": "नैचुरल", "tight": "टाइट", "check": "चेक", "turn": "टर्न", "off": "ऑफ़", "force": "फ़ोर्स", "safe": "सेफ़", "safety": "सेफ़्टी", "valve": "वाल्व", "weight": "वेट", "jarvis": "जार्विस", "normal": "नॉर्मल", "actually": "एक्चुअली", "basically": "बेसिकली", "really": "रियली", "exactly": "एग्ज़ैक्टली", "definitely": "डेफ़िनेटली", "probably": "प्रोबेबली", "usually": "यूज़ुअली", "simply": "सिंपली", "directly": "डायरेक्टली", "easily": "ईज़िली", "slowly": "स्लोली", "quickly": "क्विकली", "especially": "एस्पेशली", "approximately": "अप्रॉक्सिमेटली", "about": "अबाउट", "around": "अराउंड", "between": "बिटवीन", "after": "आफ़्टर", "before": "बिफ़ोर", "also": "ऑल्सो", "only": "ओनली", "again": "अगेन", "same": "सेम", "different": "डिफ़रेंट", "important": "इम्पॉर्टेंट", "correct": "करेक्ट", "wrong": "रॉन्ग", "right": "राइट", "left": "लेफ़्ट", "size": "साइज़", "big": "बिग", "small": "स्मॉल", "large": "लार्ज", "piece": "पीस", "pieces": "पीसेज़", "cut": "कट", "pan": "पैन", "pot": "पॉट", "bowl": "बाउल", "spoon": "स्पून", "glass": "ग्लास", "plate": "प्लेट", "pressure-cooker": "प्रेशर कुकर", "kitchen": "किचन", "first": "फ़र्स्ट", "next": "नेक्स्ट", "last": "लास्ट", "final": "फ़ाइनल", "sure": "श्योर", "yes": "यस", "no": "नो", "ai": "ए.आई.", "tv": "टी.वी.", "pc": "पी.सी.", "ac": "ए.सी.", "id": "आई.डी.", "otp": "ओ.टी.पी.",
    "gb": "जी.बी.", "mb": "एम.बी.", "kg": "किलो", "km": "किलोमीटर",
}

# Everyday assistant words (calendar, bookings, tasks). The Indian pronunciation, not the spelling: "sign" is साइन,
# and "schedule" is said शेड्यूल in Indian English. Without these entries the rule-based fallback reads "signs" as
# "signas" and mangles "schedules".
_BASE.update({
    "sign": "साइन", "signs": "साइन्स", "signed": "साइन्ड", "signal": "सिग्नल", "signature": "सिग्नेचर",
    "schedule": "शेड्यूल", "schedules": "शेड्यूल्स", "scheduled": "शेड्यूल्ड", "scheduling": "शेड्यूलिंग",
    "reschedule": "रीशेड्यूल", "rescheduled": "रीशेड्यूल्ड", "appointment": "अपॉइंटमेंट", "appointments": "अपॉइंटमेंट्स",
    "event": "इवेंट", "events": "इवेंट्स", "agenda": "एजेंडा", "deadline": "डेडलाइन", "deadlines": "डेडलाइन्स",
    "priority": "प्रायोरिटी", "notification": "नोटिफ़िकेशन", "notifications": "नोटिफ़िकेशन्स", "confirm": "कन्फ़र्म",
    "confirmed": "कन्फ़र्म्ड", "confirmation": "कन्फ़र्मेशन", "cancel": "कैंसल", "cancelled": "कैंसल्ड", "canceled": "कैंसल्ड",
    "booking": "बुकिंग", "bookings": "बुकिंग्स", "book": "बुक", "booked": "बुक्ड", "available": "अवेलेबल", "busy": "बिज़ी",
    "invite": "इन्वाइट", "invitation": "इन्विटेशन", "attend": "अटेंड", "join": "जॉइन", "joined": "जॉइन्ड", "remind": "रिमाइंड",
    "reminders": "रिमाइंडर्स", "calendars": "कैलेंडर्स", "contact": "कॉन्टैक्ट", "contacts": "कॉन्टैक्ट्स", "draft": "ड्राफ़्ट",
    "send": "सेंड", "sent": "सेंट", "reply": "रिप्लाई", "forward": "फ़ॉरवर्ड", "attachment": "अटैचमेंट", "document": "डॉक्यूमेंट",
    "documents": "डॉक्यूमेंट्स", "summary": "समरी", "analysis": "एनालिसिस", "forecast": "फ़ोरकास्ट", "dashboard": "डैशबोर्ड",
    "available": "अवेलेबल", "unavailable": "अनअवेलेबल", "morning": "मॉर्निंग", "evening": "ईवनिंग", "tonight": "टुनाइट",
})

_extra: dict | None = None


def _load_extra() -> dict:
    global _extra
    if _extra is None:
        _extra = {}
        try:
            import config
            path = os.path.join(getattr(config, "BASE_DIR", os.path.dirname(__file__)), "hinglish_data", "loanwords.json")
            if not os.path.exists(path):
                path = os.path.join(os.path.dirname(__file__), "hinglish_data", "loanwords.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                _extra = {str(k).lower(): str(v) for k, v in data.items() if isinstance(data, dict)}
        except Exception as e:
            print("[loanwords] could not read loanwords.json:", e)
    return _extra


def _ly(w: str) -> str | None:
    """normally -> नॉर्मली, really -> रियली, especially -> ..."""
    if w.endswith("ly") and len(w) > 4:
        base = lookup(w[:-2]) or (lookup(w[:-3] + "al") if w.endswith("ally") else None)
        if base:
            return base + ("ी" if base.endswith("ल") else "ली")
    return None


def lookup(word: str) -> str | None:
    """Devanagari respelling of an English word, or None. Handles simple plurals (whistles, potatoes)."""
    w = (word or "").lower()
    extra = _load_extra()
    for cand in (w, w[:-1] if w.endswith("s") else "", w[:-2] if w.endswith("es") else "", w[:-3] + "y" if w.endswith("ies") else ""):
        if cand:
            if cand in extra:
                return extra[cand]
            if cand in _BASE:
                return _BASE[cand]
    return _ly(w)


def respell(text: str) -> str:
    """Swap every known English word in a sentence for its Devanagari spelling (other words are untouched)."""
    def swap(m):
        return lookup(m.group(0)) or m.group(0)
    return re.sub(r"[A-Za-z][A-Za-z\-]*", swap, text or "")
