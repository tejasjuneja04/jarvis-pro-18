"""
Messaging for JARVIS: write and send WhatsApp messages and emails to people you name, and keep a small contacts book.

    "WhatsApp Rahul that I will be 10 minutes late"        "Rahul ko whatsapp karo ki main late hoon"
    "write an email to Priya about the project delay"      "email boss@company.com asking for leave tomorrow"
    "save contact Rahul number 98765 43210 email rahul@x.com"   "Rahul's email is rahul@x.com"
    "what is Rahul's number"   "show my contacts"   "delete contact Rahul"

How it stays safe: JARVIS writes a DRAFT and shows it. Nothing leaves your Mac until you say "send it" (or "haan bhej do").
You can change the draft first: "make it shorter", "more formal", "add that I will bring the files", or "cancel".

How things are sent (set in backend/.env, see .env.example):
  email     smtp  - straight from your address (Gmail: use an App Password)      JARVIS_EMAIL_ADDRESS / JARVIS_EMAIL_PASSWORD
            mail  - through the Mail app on this Mac                              JARVIS_EMAIL_MODE=mail
            draft - opens a ready-to-send window in your mail app (default when no password is set)
  whatsapp  open  - opens that chat with the message typed in; you press send (default)
            auto  - Jarvis also presses send for you (macOS: needs Accessibility permission)   JARVIS_WHATSAPP_MODE=auto
"""

from __future__ import annotations

import json
import re
import smtplib
import subprocess
import sys
import threading
import time
import webbrowser
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import config

CONTACTS_FILE = config.DATA_DIR / "contacts.json"
DRAFT_TTL = 15 * 60                      # an unsent draft is forgotten after 15 minutes

_WA = r"(?:whats\s*app|watsapp|wa\b|व्हाट्सएप|व्हाट्सऐप)"
_MAIL = r"(?:e-?mail|mail|ईमेल|मेल)"
_EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w@])(\+?\d[\d\s-]{7,}\d)(?![\w@])")
_STOP = (r"(?:saying|say|that|about|regarding|asking|telling|tell|to\s+(?:say|tell|ask)|for|on|via|using|with|subject|"
         r"and\s+(?:tell|say|ask|send)|ki|ke\s+baare|ke\s+bare|bolo|kehna|batao|pooch|poocho|:|,|\.|$)")

SEND_RE = re.compile(r"^(?:yes|yeah|yep|yup|ok(?:ay)?|sure|send(?:\s+(?:it|that|this|now))?|go\s+ahead|do\s+it|confirm(?:ed)?|"
                     r"looks\s+good(?:\s+send)?|haan|han|ha|haan\s+bhej\s+do|bhej\s+do|bhej\s+de|bhejo|bhej\s+dijiye|kar\s+do|"
                     r"theek\s+hai\s+bhej\s+do|send\s+kar\s+do)\W*$", re.I)
CANCEL_RE = re.compile(r"^(?:no|nope|cancel|never\s*mind|don'?t\s+send|do\s+not\s+send|stop|discard|nahi|nahin|mat\s+bhejo|"
                       r"rehne\s+do|chhod\s+do|chhodo|cancel\s+kar\s+do)\W*$", re.I)
REVISE_RE = re.compile(r"\b(shorter|short|longer|detailed|formal|informal|casual|friendly|polite|professional|rewrite|redo|"
                       r"change|make\s+it|add|mention|include|remove|replace|translate|hindi|english|hinglish|warmer|firm|"
                       r"chhota|chhoti|lamba|badlo|badal|likho|jod|hata)\b", re.I)


# ---------------------------------------------------------------------------------------------- contacts

def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9ऀ-ॿ ]+", "", (s or "").lower()).strip()


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = config.COUNTRY_CODE + digits
    return digits


class Contacts:
    """A tiny address book in jarvis_data/contacts.json: {"rahul": {"name": "Rahul", "phone": "919...", "email": "..."}}."""

    def __init__(self, path: Path | None = None, use_macos: bool = True):
        self.path = path or CONTACTS_FILE
        self.use_macos = use_macos and sys.platform == "darwin"
        self._lock = threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.data = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, name: str) -> dict | None:
        key = _norm_name(name)
        if not key:
            return None
        with self._lock:
            if key in self.data:
                return dict(self.data[key])
            for k, v in self.data.items():                       # "rahul" finds "rahul sharma", and the other way round
                if k.startswith(key) or key.startswith(k) or key in k.split() or k in key.split():
                    return dict(v)
        return self._macos_lookup(name) if self.use_macos else None

    def put(self, name: str, phone: str = "", email: str = "") -> dict:
        key = _norm_name(name)
        with self._lock:
            cur = self.data.get(key, {"name": name.strip().title()})
            if phone:
                cur["phone"] = _clean_phone(phone)
            if email:
                cur["email"] = email.strip().lower()
            self.data[key] = cur
            self._save()
            return dict(cur)

    def remove(self, name: str) -> bool:
        key = _norm_name(name)
        with self._lock:
            hit = next((k for k in self.data if k == key or k.startswith(key) or key in k.split()), None)
            if hit:
                del self.data[hit]
                self._save()
            return bool(hit)

    def all(self) -> list:
        with self._lock:
            return sorted((dict(v) for v in self.data.values()), key=lambda v: v.get("name", ""))

    @staticmethod
    def _macos_lookup(name: str) -> dict | None:
        """Ask the Contacts app (you may be asked to allow it once). Returns None when nothing is found."""
        safe = re.sub(r'[^A-Za-z0-9 .ऀ-ॿ-]', "", name)[:40]
        if not safe:
            return None
        script = (f'tell application "Contacts"\nset ps to every person whose name contains "{safe}"\n'
                  'if (count of ps) is 0 then return ""\nset p to item 1 of ps\nset ph to ""\nset em to ""\n'
                  'if (count of phones of p) > 0 then set ph to value of item 1 of phones of p\n'
                  'if (count of emails of p) > 0 then set em to value of item 1 of emails of p\n'
                  'return (name of p) & "|" & ph & "|" & em\nend tell')
        try:
            out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8).stdout.strip()
        except Exception:
            return None
        if not out or "|" not in out:
            return None
        n, ph, em = (out.split("|") + ["", ""])[:3]
        found = {"name": n.strip()}
        if ph.strip():
            found["phone"] = _clean_phone(ph)
        if em.strip():
            found["email"] = em.strip().lower()
        return found if len(found) > 1 else None


# ---------------------------------------------------------------------------------------------- parsing

def _strip_wake(text: str) -> str:
    return re.sub(r"^\s*(?:hey\s+|ok\s+|okay\s+)?(?:jarvis|जार्विस)\b[\s,.:!-]*", "", text.strip(), flags=re.I).strip()


def parse_request(text: str) -> dict | None:
    """Understand "WhatsApp Rahul that ...", "email Priya about ...", "Rahul ko whatsapp karo ki ...".
    Returns {"kind": "whatsapp"|"email", "name", "phone", "email", "message", "topic"} or None if it is not a send request."""
    t = _strip_wake(text)
    if not t or len(t) > 600:
        return None
    low = t.lower()
    has_wa = bool(re.search(_WA, low, re.I))
    has_mail = bool(re.search(rf"\b{_MAIL}\b|{_MAIL}", low, re.I)) or bool(_EMAIL_ADDR.search(t))
    verb = re.search(r"\b(send|write|draft|compose|text|message|msg|tell|ask|inform|notify|bhej|bhejo|likho|likh|bol|bolo|"
                     r"batao|karo|kar\s+do|ping|mail|email|whatsapp)\b|भेज|लिखो|बोलो", low)
    if not (has_wa or has_mail) and not re.match(r"^(?:send\s+(?:a\s+)?(?:message|msg|text)|(?:message|text|msg)\s+\w)", low):
        return None
    if not verb:
        return None
    if has_wa and has_mail and low.find("mail") < low.find("whats"):
        kind = "email"
    else:
        kind = "whatsapp" if (has_wa or not has_mail) else "email"
    if re.search(r"\b(open|kholo|khol)\s+" + _WA + r"\s*$", low):
        return None                                          # just "open WhatsApp": the app opener handles that

    em = _EMAIL_ADDR.search(t)
    ph = _PHONE.search(t) if not em else None
    name = ""
    m = (re.search(rf"\b(?:to|for)\s+(?!me\b|my\b|the\b|a\b|an\b)(?P<w>[A-Za-zऀ-ॿ][\wऀ-ॿ.'-]*(?:\s+[A-Za-zऀ-ॿ][\wऀ-ॿ.'-]*){{0,2}})(?=\s+{_STOP})", t, re.I)
         or re.search(r"(?P<w>[A-Za-zऀ-ॿ][\wऀ-ॿ.'-]*(?:\s+[A-Za-zऀ-ॿ][\wऀ-ॿ.'-]*)?)\s+(?:ko|को)\b", t, re.I)
         or re.search(rf"\b(?:{_WA}|{_MAIL}|message|msg|text|ping|tell|ask|inform|notify)\s+(?!to\b|a\b|an\b|the\b|my\b|that\b|about\b)(?P<w>[A-Za-zऀ-ॿ][\wऀ-ॿ.'-]*)", t, re.I))
    if m:
        name = m.group("w").strip()
        name = re.sub(r"\s+(?:on|via|using|about|that|saying|for)$", "", name, flags=re.I)
        if name.lower() in ("whatsapp", "email", "mail", "message", "him", "her", "them", "someone", "somebody", "me", "up"):
            name = ""
    name = re.sub(rf"\b{_WA}\b|\b{_MAIL}\b", "", name, flags=re.I).strip()

    message = topic = ""
    s = re.search(r"(?:\bsaying\b|\bsay\b|\bthat\b|\bki\b|कि|\bbolo\b|:)\s*(?P<m>.+)$", t, re.I)
    if s:
        message = s.group("m").strip().strip("\"'“”")
    a = re.search(r"\b(?:about|regarding|asking(?:\s+(?:him|her|them|for))?|requesting|informing(?:\s+\w+)?|for\s+(?:a|an|the)\b|"
                  r"subject)\s*:?\s*(?P<t>.+)$", t, re.I)
    if a:
        topic = a.group("t").strip().strip("\"'“”")
    if not (message or topic):
        # "tell Rahul I'll call tonight" / "whatsapp 98765 43210 hello": whatever follows the person is the message
        tail = ""
        if m and re.search(r"\b(?:tell|ask|inform|notify|ping|message|msg|text)\b", t[:m.start("w")], re.I):
            tail = t[m.end("w"):]
        elif ph:
            tail = t[ph.end():]
        tail = re.sub(r"\s*\b(?:on|via|by|using)\s+(?:" + _WA + "|" + _MAIL + r")\b\W*$", "", tail.strip(), flags=re.I)
        tail = re.sub(r"^(?:that|to|ki)\s+", "", tail.strip(), flags=re.I).strip(" :,-")
        if len(tail.split()) >= 2:
            message = tail
    if kind == "email" and not (message or topic):
        w = re.search(r"\b(?:write|draft|compose|send)\s+(?:an?\s+)?(?:e-?mail|mail)\s+(?:to\s+\S+(?:\s+\S+)?\s+)?(?P<t>.+)$", t, re.I)
        if w:
            topic = w.group("t").strip()
    if not name and not em and not ph:
        return None
    return {"kind": kind, "name": name, "phone": _clean_phone(ph.group(1)) if ph else "",
            "email": em.group(0).lower() if em else "", "message": message, "topic": topic, "raw": t}


# ---------------------------------------------------------------------------------------------- writing

def _first_name_of_user() -> str:
    return getattr(config, "USER_NAME", "") or ""


def compose(gen, req: dict, who: str, hindi: bool = False) -> dict:
    """Write the draft. `gen(system, user, max_tokens)` is the language model; if it fails a plain template is used."""
    me = _first_name_of_user()
    if req["kind"] == "whatsapp":
        if req["message"] and not re.search(r"^\s*(?:tell|ask|inform)\b", req["raw"], re.I) and len(req["message"].split()) <= 3:
            return {"body": req["message"][:1].upper() + req["message"][1:], "subject": ""}
        brief = req["message"] or req["topic"] or req["raw"]
        system = ("You write WhatsApp messages for the user, in the user's own voice, first person. "
                  "Short, natural, friendly, like a real text. No quotes, no explanations, no 'Here is'. "
                  + ("Write in casual Hinglish (Hindi in English letters). " if hindi else "Write in English unless asked otherwise. ")
                  + "Output ONLY the message text.")
        user = f"Message for {who or 'a contact'}. What to say: {brief}"
        try:
            out = gen(system, user, 160).strip().strip("\"'“”")
            if out:
                return {"body": out, "subject": ""}
        except Exception:
            pass
        fallback = req["message"] or req["topic"] or req["raw"]
        return {"body": fallback[:1].upper() + fallback[1:], "subject": ""}

    brief = req["message"] or req["topic"] or req["raw"]
    system = ("You write emails for the user, in the user's own voice. Clear, polite, to the point. "
              f"Start with a greeting to {who or 'the recipient'}, end with a short sign-off and the name '{me or 'the sender'}'. "
              "Never invent facts, dates or numbers the user did not give. "
              "Reply in EXACTLY this format and nothing else:\nSUBJECT: <short subject>\nBODY:\n<the email body>")
    try:
        out = gen(system, f"Recipient: {who or 'unknown'}\nWhat the email should say: {brief}", 420).strip()
        sm = re.search(r"SUBJECT:\s*(?P<s>.+?)\s*\n+\s*BODY:\s*\n?(?P<b>.+)$", out, re.S | re.I)
        if sm and sm.group("b").strip():
            return {"subject": sm.group("s").strip().strip("\"'"), "body": sm.group("b").strip()}
    except Exception:
        pass
    subject = (req["topic"] or req["message"] or "Quick note")[:70]
    subject = subject[:1].upper() + subject[1:]
    body = f"Hi {who or 'there'},\n\n{(req['message'] or req['topic'] or req['raw'])[:1].upper() + (req['message'] or req['topic'] or req['raw'])[1:]}\n\nRegards,\n{me}".strip()
    return {"subject": subject, "body": body}


def revise(gen, draft: dict, instruction: str) -> dict:
    kind = draft["kind"]
    system = ("You edit a draft message exactly as the user asks, keeping everything else. "
              + ("Output ONLY the new message text." if kind == "whatsapp"
                 else "Reply in EXACTLY this format:\nSUBJECT: <subject>\nBODY:\n<body>"))
    current = draft["body"] if kind == "whatsapp" else f"SUBJECT: {draft['subject']}\nBODY:\n{draft['body']}"
    out = gen(system, f"Current draft:\n{current}\n\nChange requested: {instruction}", 420).strip()
    if kind == "whatsapp":
        return {**draft, "body": out.strip("\"'“”") or draft["body"]}
    sm = re.search(r"SUBJECT:\s*(?P<s>.+?)\s*\n+\s*BODY:\s*\n?(?P<b>.+)$", out, re.S | re.I)
    if sm:
        return {**draft, "subject": sm.group("s").strip(), "body": sm.group("b").strip()}
    return {**draft, "body": out or draft["body"]}


# ---------------------------------------------------------------------------------------------- sending

def _run_osascript(script: str, timeout: int = 20) -> bool:
    try:
        return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=timeout).returncode == 0
    except Exception:
        return False


def send_email(to: str, subject: str, body: str) -> str:
    """Send or open an email. Returns a short sentence telling what happened. Raises RuntimeError on failure."""
    mode = config.EMAIL_MODE
    if mode == "auto":
        mode = "smtp" if (config.EMAIL_ADDRESS and config.EMAIL_PASSWORD) else "draft"
    if mode == "smtp":
        if not (config.EMAIL_ADDRESS and config.EMAIL_PASSWORD):
            raise RuntimeError("Email sending is not set up. Add JARVIS_EMAIL_ADDRESS and JARVIS_EMAIL_PASSWORD "
                               "(an app password) to backend/.env.")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = config.EMAIL_ADDRESS, to, subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=25) as s:
                s.starttls()
                s.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
                s.send_message(msg)
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError("The email server refused the login. With Gmail you need an App Password, not your normal password.")
        except Exception as e:
            raise RuntimeError(f"I couldn't send it: {type(e).__name__}: {e}")
        return f"Email sent to {to}."
    if mode == "mail" and sys.platform == "darwin":
        esc = lambda x: x.replace("\\", "\\\\").replace('"', '\\"')
        script = (f'tell application "Mail"\nset m to make new outgoing message with properties '
                  f'{{subject:"{esc(subject)}", content:"{esc(body)}", visible:false}}\n'
                  f'tell m to make new to recipient with properties {{address:"{esc(to)}"}}\nsend m\nend tell')
        if _run_osascript(script):
            return f"Email sent to {to} from the Mail app."
        raise RuntimeError("The Mail app did not accept it. Open Mail once, add your account, and allow automation.")
    url = f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}"
    if sys.platform == "darwin":
        subprocess.run(["open", url], capture_output=True)
    else:
        webbrowser.open(url)
    return f"I opened a ready-to-send email to {to} in your mail app. Press send there."


def send_whatsapp(phone: str, text: str) -> str:
    """Open WhatsApp with the message typed in (and press send when JARVIS_WHATSAPP_MODE=auto)."""
    q = ([f"phone={phone}"] if phone else []) + [f"text={quote(text)}"]
    url = "whatsapp://send?" + "&".join(q)
    opened = False
    if sys.platform == "darwin":
        opened = subprocess.run(["open", url], capture_output=True).returncode == 0
    if not opened:
        webbrowser.open("https://web.whatsapp.com/send?" + "&".join(q))
        return "WhatsApp Web is open with the message typed in. Press send there."
    if config.WHATSAPP_MODE == "auto" and phone:
        def press():
            time.sleep(3.5)
            _run_osascript('tell application "WhatsApp" to activate')
            time.sleep(0.8)
            _run_osascript('tell application "System Events" to key code 36')
        threading.Thread(target=press, daemon=True).start()
        return "Sent through WhatsApp."
    return ("WhatsApp is open with the message typed in. Press send."
            if phone else "WhatsApp is open with the message typed in. Pick the chat and press send.")


# ---------------------------------------------------------------------------------------------- the handler

class Comms:
    def __init__(self, contacts: Contacts | None = None, sender_email=send_email, sender_wa=send_whatsapp):
        self.contacts = contacts or Contacts()
        self.send_email, self.send_wa = sender_email, sender_wa

    # -- contacts commands ---------------------------------------------------------
    def _contact_command(self, t: str) -> str | None:
        low = t.lower().strip().rstrip("?.!")
        if re.match(r"^(?:show|list|open|dikhao|batao)\s+(?:me\s+)?(?:my\s+|all\s+|saare\s+|mere\s+)?contacts?$", low) or low in ("contacts", "my contacts"):
            rows = self.contacts.all()
            if not rows:
                return "Your contact book is empty. Say: save contact Rahul number 98765 43210 email rahul@example.com"
            return "Your contacts:\n" + "\n".join(
                f"• {r['name']}" + (f"  📱 +{r['phone']}" if r.get("phone") else "") + (f"  ✉ {r['email']}" if r.get("email") else "")
                for r in rows)
        m = re.match(r"^(?:delete|remove|hatao|hata\s+do)\s+(?:the\s+)?contact\s+(?P<n>.+)$", low)
        if m:
            return f"Removed {m.group('n').title()} from your contacts." if self.contacts.remove(m.group("n")) \
                else f"I don't have a contact called {m.group('n').title()}."
        m = re.match(r"^(?:what(?:'s| is)|kya hai|batao)\s+(?P<n>[\w ]+?)(?:'s|s)\s+(?P<f>number|phone|email|mail|e-mail|no)$", low) or \
            re.match(r"^(?P<n>[\w ]+?)\s+ka\s+(?P<f>number|phone|email|mail)(?:\s+(?:kya hai|batao))?$", low)
        if m:
            c = self.contacts.get(m.group("n"))
            f = "email" if "mail" in m.group("f") else "phone"
            if c and c.get(f):
                return f"{c['name']}'s {f if f == 'email' else 'number'} is {('+' if f == 'phone' else '') + c[f]}."
            return f"I don't have {m.group('n').title()}'s {f if f == 'email' else 'number'} yet. Say: {m.group('n').title()}'s {f if f == 'email' else 'number'} is …"
        m = (re.match(r"^(?:save|add|remember|store)\s+(?:a\s+)?(?:new\s+)?contact\s+(?P<n>[A-Za-zऀ-ॿ][\wऀ-ॿ ]*?)\s+(?:with\s+)?(?:(?:phone|number|mobile|no\.?|email|mail)\b|\+?\d|[\w.+-]+@)(?P<rest>.*)$", t.strip(), re.I)
             or re.match(r"^(?P<n>[A-Za-zऀ-ॿ][\wऀ-ॿ]*)(?:'s|s)?\s+(?:phone\s+|mobile\s+)?(?P<kind>number|phone|mobile|email|mail|e-mail)\s+(?:is|=|:)\s*(?P<rest>.+)$", t.strip(), re.I)
             or re.match(r"^(?P<n>[A-Za-zऀ-ॿ][\wऀ-ॿ]*)\s+ka\s+(?P<kind>number|phone|email|mail)\s+(?P<rest>.+?)(?:\s+(?:save|yaad)\s+\w+)?$", t.strip(), re.I))
        if m:
            name = m.group("n").strip()
            if name.lower() in ("my", "your", "the", "this", "that", "his", "her", "our", "their", "whose", "jarvis", "phone", "email"):
                return None
            blob = t[t.lower().find(name.lower()) + len(name):] if "kind" not in m.groupdict() else m.group("rest")
            em = _EMAIL_ADDR.search(blob)
            ph = _PHONE.search(re.sub(_EMAIL_ADDR, "", blob))
            if not em and not ph:
                return None
            c = self.contacts.put(name, ph.group(1) if ph else "", em.group(0) if em else "")
            parts = ([f"number +{c['phone']}"] if ph else []) + ([f"email {c['email']}"] if em else [])
            return f"Saved {c['name']}: {', and '.join(parts)}."
        return None

    # -- drafting ---------------------------------------------------------------------
    def _preview(self, d: dict, hindi: bool) -> str:
        if d["kind"] == "whatsapp":
            where = f"+{d['phone']}" if d.get("phone") else "pick the chat in WhatsApp"
            head = f"📱 WhatsApp draft to {d['name'] or where}" + (f" ({where})" if d["name"] and d.get("phone") else "")
            return f"{head}\n────────────────────────────────────────────\n{d['body']}\n────────────────────────────────────────────"
        to = d.get("to") or "(no address yet)"
        return (f"✉ Email draft to {d['name'] or to}" + (f" <{to}>" if d["name"] and d.get("to") else "")
                + f"\n────────────────────────────────────────────\nSubject: {d['subject']}\n\n{d['body']}\n"
                  "────────────────────────────────────────────")

    def _new_draft(self, gen, req: dict, hindi: bool):
        c = self.contacts.get(req["name"]) if req["name"] else None
        who = (c or {}).get("name") or req["name"]
        d = {"kind": req["kind"], "name": who, "created": time.time()}
        if req["kind"] == "whatsapp":
            d["phone"] = req["phone"] or (c or {}).get("phone", "")
        else:
            d["to"] = req["email"] or (c or {}).get("email", "")
        d.update(compose(gen, req, who or d.get("to") or "", hindi))
        return d

    def handle(self, session, text: str, gen=None):
        """Returns (reply_text, speech, suggestions) or None when this is not a messaging request."""
        t = _strip_wake(text)
        if not t:
            return None
        hindi = getattr(session, "lang", "en") == "hi"
        title = getattr(session, "title", "sir")
        draft = getattr(session, "draft", None)
        if draft and time.time() - draft.get("created", 0) > DRAFT_TTL:
            session.draft = draft = None

        # 1) answers to a draft that is waiting
        if draft:
            if SEND_RE.match(t):
                return self._send(session, draft, title, hindi)
            if CANCEL_RE.match(t):
                session.draft = None
                return ("Cancelled. Nothing was sent.", "Theek hai, kuch nahi bheja." if hindi else "Cancelled. Nothing was sent.", [])
            c = self._contact_command(t)
            if c:                                                  # "Priya's email is ..." while a draft waits for it
                nm = _norm_name(draft.get("name", ""))
                if nm and nm in _norm_name(t) or (draft["kind"] == "email" and not draft.get("to")) or (draft["kind"] == "whatsapp" and not draft.get("phone")):
                    got = self.contacts.get(draft.get("name", ""))
                    if got:
                        draft["phone"] = draft.get("phone") or got.get("phone", "")
                        draft["to"] = draft.get("to") or got.get("email", "")
                return (c + "\n\n" + self._preview(draft, hindi), c, self._chips(draft))
            if REVISE_RE.search(t) and gen is not None and not parse_request(t):
                try:
                    session.draft = draft = revise(gen, draft, t)
                except Exception:
                    return ("I couldn't change it just now. Tell me the exact words you want and I'll use them.", None, self._chips(draft))
                return (self._preview(draft, hindi), "Maine badal diya. Bhej doon?" if hindi else "Updated. Shall I send it?", self._chips(draft))

        # 2) contacts book
        c = self._contact_command(t)
        if c:
            return (c, c if len(c) < 140 and "\n" not in c else None, [])

        # 3) a new message to write
        req = parse_request(t)
        if not req:
            return None
        if gen is None:
            gen = lambda s, u, n: (_ for _ in ()).throw(RuntimeError("no model"))
        d = self._new_draft(gen, req, hindi)
        session.draft = d
        notes = []
        if d["kind"] == "email" and not d.get("to"):
            n = d["name"] or "them"
            notes.append(f"I don't have {n}'s email yet. Say: “{n}'s email is name@example.com” and I'll remember it.")
        if d["kind"] == "whatsapp" and not d.get("phone"):
            n = d["name"] or "them"
            notes.append(f"I don't have {n}'s number, so I'll open WhatsApp with the text typed in and you pick the chat. "
                         f"(Save it once: “{n}'s number is 98765 43210”.)")
        body = self._preview(d, hindi) + ("\n\n" + "\n".join(notes) if notes else "")
        ask = "Bhej doon?" if hindi else "Shall I send it?"
        speech = f"{'Draft ready' if not hindi else 'Draft ready hai'}, {title}. {ask}"
        return (body + "\n\n" + ("Bolo “send it” ya badlav batao." if hindi else "Say “send it”, tell me what to change, or “cancel”."),
                speech, self._chips(d))

    @staticmethod
    def _chips(d: dict) -> list:
        return ["Send it", "Make it shorter", "More formal", "Cancel"] if d["kind"] == "email" else ["Send it", "Make it shorter", "More casual", "Cancel"]

    def _send(self, session, d: dict, title: str, hindi: bool):
        try:
            if d["kind"] == "email":
                if not d.get("to"):
                    n = d["name"] or "them"
                    return (f"I still need {n}'s email address. Say: “{n}'s email is name@example.com”.", None, [])
                msg = self.send_email(d["to"], d["subject"], d["body"])
            else:
                msg = self.send_wa(d.get("phone", ""), d["body"])
        except RuntimeError as e:
            return (f"{e}", None, ["Cancel"])
        session.draft = None
        return (f"✅ {msg}", ("Ho gaya." if hindi else f"Done, {title}. {msg}") if len(msg) < 90 else f"Done, {title}.", [])


# one shared instance per process
_shared: Comms | None = None


def shared() -> Comms:
    global _shared
    if _shared is None:
        _shared = Comms()
    return _shared
