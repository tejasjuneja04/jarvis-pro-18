"""
Two everyday helpers:

  Morning briefing   "morning briefing", "brief me", "what's my day look like", "aaj ka briefing"
                     -> date, weather, top headlines, your open tasks, in one reply (and a short spoken version).
  Calendar events    "schedule a meeting with Rahul tomorrow at 5pm for 1 hour about the launch", "add dentist friday 4pm"
                     -> a calendar file (.ics). Open it and Calendar, Google Calendar and Outlook all add it.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

import config
import tools
from models import Reply, _file_payload

BRIEF_RE = re.compile(
    r"^(?:(?:give|show|tell)\s+me\s+(?:my|the|a)\s+)?(?:(?:morning|daily|day|today'?s?)\s+)?(?:briefing|brief|summary of my day)\b|"
    r"\bbrief\s+me\b|\bwhat'?s\s+(?:my\s+day|on\s+today|the\s+plan\s+for\s+today)|\bmy\s+day\s+look|"
    r"\b(?:aaj\s+ka|subah\s+ka|mera)\s+(?:briefing|brief|din)\b|\bdaily\s+update\b", re.I)

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_HI_DAYS = {"kal": 1, "parso": 2, "aaj": 0}


def morning_briefing(client, session) -> Reply:
    title = session.title
    now = datetime.now()
    hour = now.hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    lines = [f"{greet}, {title}. It's {now.strftime('%A, %d %B')}, {now.strftime('%I:%M %p').lstrip('0')}.", ""]
    spoken = [f"{greet}, {title}."]

    city = config.HOME_CITY
    if city:
        w = tools.weather(city)
        if w:
            today = w["days"][0] if w.get("days") else None
            rng = f", {today['min']}° to {today['max']}°C today" if today else ""
            lines.append(f"🌤  {w['city']}: {w['desc']}, {w['temp_c']}°C (feels {w['feels_c']}°){rng}.")
            spoken.append(f"It's {w['temp_c']} degrees and {w['desc'].lower()} in {w['city']}.")
    else:
        lines.append("🌤  Set JARVIS_CITY in backend/.env to see your weather here.")

    items = tools.news(None, 5)
    if items:
        lines += ["", "📰  Headlines"] + [f"  • {n['title']}" for n in items[:5]]
        spoken.append("The top story is " + items[0]["title"].split(" - ")[0] + ".")

    tasks = [t for t in getattr(client.skills, "tasks", []) if not t.get("done")]
    if tasks:
        lines += ["", f"✅  {len(tasks)} open task{'s' if len(tasks) != 1 else ''}"] + [f"  • {t['text']}" for t in tasks[:6]]
        spoken.append(f"You have {len(tasks)} open task{'s' if len(tasks) != 1 else ''}.")
    else:
        lines += ["", "✅  No open tasks. A clear desk."]

    lines += ["", "Want me to set a timer, write an email, or open your data?"]
    return Reply("\n".join(lines), speech=" ".join(spoken),
                 suggestions=["Weather & news", "Show my tasks", "Set a timer for 25 minutes"])


# ----------------------------------------------------------------------------------------- calendar

def parse_when(text: str, now: datetime | None = None):
    """Find a date and a time in the sentence. Returns (start datetime, matched text spans) or None."""
    now = now or datetime.now()
    low = text.lower()
    day = None
    if re.search(r"\btoday\b|\baaj\b", low):
        day = now.date()
    elif re.search(r"\btomorrow\b|\bkal\b", low):
        day = (now + timedelta(days=1)).date()
    elif re.search(r"\bday after tomorrow\b|\bparso\b", low):
        day = (now + timedelta(days=2)).date()
    else:
        m = re.search(r"\b(?:next\s+|this\s+|on\s+)?(" + "|".join(d[:3] + r"[a-z]*" for d in _DAYS) + r")\b", low)
        if m:
            idx = next(i for i, d in enumerate(_DAYS) if d.startswith(m.group(1)[:3]))
            ahead = (idx - now.weekday()) % 7
            if ahead == 0 or (m.group(0).startswith("next") and ahead < 7):
                ahead = ahead or 7
            day = (now + timedelta(days=ahead)).date()
        else:
            m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(mn[:3] + r"[a-z]*" for mn in _MONTHS) + r")\b", low) or \
                re.search(r"\b(" + "|".join(mn[:3] + r"[a-z]*" for mn in _MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", low)
            if m:
                a, b = m.group(1), m.group(2)
                d_, mon = (int(a), b) if a.isdigit() else (int(b), a)
                mi = next(i for i, mn in enumerate(_MONTHS) if mn.startswith(mon[:3])) + 1
                year = now.year + (1 if (mi, d_) < (now.month, now.day) else 0)
                try:
                    day = datetime(year, mi, d_).date()
                except ValueError:
                    day = None
    tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", low) or re.search(r"\b(\d{1,2}):(\d{2})\b()", low) or \
        re.search(r"\b(\d{1,2})\s*(?:baje|bje)\b()()", low)
    hour = minute = None
    if tm:
        hour = int(tm.group(1))
        minute = int(tm.group(2) or 0) if tm.lastindex and tm.lastindex >= 2 and tm.group(2) else 0
        ap = (tm.group(3) or "").replace(".", "") if tm.lastindex and tm.lastindex >= 3 else ""
        if ap == "pm" and hour < 12:
            hour += 12
        elif ap == "am" and hour == 12:
            hour = 0
        elif not ap and hour <= 7 and "baje" in tm.group(0):
            hour += 12                                                # "5 baje" in the evening
    elif re.search(r"\bnoon\b|\bafternoon\b", low):
        hour, minute = 12 if "noon" in low else 15, 0
    elif re.search(r"\bmorning\b|\bsubah\b", low):
        hour, minute = 9, 0
    elif re.search(r"\bevening\b|\bshaam\b", low):
        hour, minute = 18, 0
    if day is None and hour is None:
        return None
    if day is None:
        day = now.date()
        if datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute or 0) < now:
            day = (now + timedelta(days=1)).date()
    start = datetime(day.year, day.month, day.day, 9 if hour is None else hour, minute or 0)
    return start


def parse_event(text: str, now: datetime | None = None) -> dict | None:
    low = text.lower().strip()
    if not re.search(r"\b(schedule|calendar|set up|setup|book|add)\b.*\b(meeting|call|event|appointment|reminder|calendar|lunch|dinner|interview|class)\b|"
                     r"\b(add|put)\b.*\b(to|in|on)\s+(?:my\s+)?calendar\b|\bschedule\s+(?:a|an|my)\b|\b(?:meeting|call)\s+(?:schedule|fix|set)\s+kar", low):
        return None
    start = parse_when(text, now)
    if start is None:
        return None
    mins = 60
    d = re.search(r"\bfor\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", low)
    if d:
        mins = int(float(d.group(1)) * (60 if d.group(2).startswith("h") else 1))
    elif re.search(r"\bhalf\s+an?\s+hour\b", low):
        mins = 30
    title = text.strip()
    title = re.sub(r"^(?:hey\s+)?jarvis[\s,]*", "", title, flags=re.I)
    about = re.search(r"\b(?:about|regarding|titled|called|named|for the)\s+(?P<t>.+?)(?:\s+(?:tomorrow|today|at|on|for\s+\d)\b|$)", title, re.I)
    withp = re.search(r"\bwith\s+(?P<p>[A-Z][\w.]*(?:\s+[A-Z][\w.]*)?)", title)
    kind = re.search(r"\b(meeting|call|appointment|lunch|dinner|interview|class|event|reminder|demo|review|standup)\b", low)
    name = (kind.group(1).title() if kind else "Event")
    if about:
        name = f"{name}: {about.group('t').strip(' .')}"
    if withp:
        name += f" with {withp.group('p')}"
    if name == "Event":
        name = re.sub(r"\b(schedule|add|put|to|in|on|my|calendar|tomorrow|today|at|please)\b", "", title, flags=re.I).strip(" ,.") or "Event"
    return {"title": name[:90], "start": start, "end": start + timedelta(minutes=mins), "minutes": mins}


def build_ics(ev: dict) -> str:
    f = lambda d: d.strftime("%Y%m%dT%H%M%S")
    esc = lambda s: s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//JARVIS//EN", "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
        f"UID:{uuid.uuid4().hex}@jarvis", f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{f(ev['start'])}", f"DTEND:{f(ev['end'])}", f"SUMMARY:{esc(ev['title'])}",
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "TRIGGER:-PT15M", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])


def calendar_reply(session, text: str) -> Reply | None:
    ev = parse_event(text)
    if not ev:
        return None
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / (re.sub(r"[^A-Za-z0-9]+", "_", ev["title"])[:40].strip("_") + ".ics")
    path.write_text(build_ics(ev), encoding="utf-8")
    when = ev["start"].strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
    mins = ev["minutes"]
    dur = f"{mins // 60} h" + (f" {mins % 60} min" if mins % 60 else "") if mins >= 60 else f"{mins} min"
    f = _file_payload(path, "text/calendar")
    return Reply(f"📅 {ev['title']}\n{when} · {dur}\n\nDownload the file below and open it: it adds to Apple Calendar, Google Calendar "
                 "or Outlook, with a reminder 15 minutes before.",
                 speech=f"Done. {ev['title']}, {when}. Open the file to add it to your calendar.",
                 files=[f] if f else [], suggestions=["Set a timer for 25 minutes", "Show my tasks"])


def handle(client, session, text: str):
    t = re.sub(r"^\s*(?:hey\s+)?jarvis[\s,]*", "", text.strip(), flags=re.I)
    if BRIEF_RE.search(t) and len(t) < 90:
        return morning_briefing(client, session)
    if len(t) < 220:
        return calendar_reply(session, t)
    return None
