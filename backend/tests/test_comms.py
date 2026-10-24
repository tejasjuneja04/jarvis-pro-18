import comms
from models import Session


def fake_gen(system, user, n):
    if "WhatsApp" in system:
        return "Hey Rahul, I'll be 10 minutes late."
    if "edit a draft" in system:
        return "SUBJECT: Project delay\nBODY:\nHi Priya,\n\nShort version.\n\nTejas" if "SUBJECT" in system else "Running late, sorry!"
    return "SUBJECT: Project delay\nBODY:\nHi Priya,\n\nThe project is delayed by a week.\n\nRegards,\nTejas"


def make(tmp_path):
    sent = []
    c = comms.Comms(comms.Contacts(tmp_path / "c.json", use_macos=False),
                    sender_email=lambda to, s, b: sent.append(("mail", to, s, b)) or f"Email sent to {to}.",
                    sender_wa=lambda p, t: sent.append(("wa", p, t)) or "Sent through WhatsApp.")
    return c, Session(), sent


def test_parse_variants():
    p = comms.parse_request("Rahul ko whatsapp karo ki main late hoon")
    assert p["kind"] == "whatsapp" and p["name"] == "Rahul" and p["message"] == "main late hoon"
    p = comms.parse_request("email boss@company.com asking for leave tomorrow")
    assert p["kind"] == "email" and p["email"] == "boss@company.com"
    assert comms.parse_request("open whatsapp") is None
    assert comms.parse_request("what's the weather") is None


def test_nothing_is_sent_without_confirmation(tmp_path):
    c, s, sent = make(tmp_path)
    c.contacts.put("Rahul", phone="9876543210")
    body, speech, chips = c.handle(s, "WhatsApp Rahul that I will be 10 minutes late", fake_gen)
    assert "Rahul" in body and "10 minutes late" in body and "Send it" in chips
    assert sent == [] and s.draft
    body, *_ = c.handle(s, "send it", fake_gen)
    assert sent == [("wa", "919876543210", "Hey Rahul, I'll be 10 minutes late.")] and s.draft is None


def test_email_flow_with_missing_address(tmp_path):
    c, s, sent = make(tmp_path)
    body, *_ = c.handle(s, "write an email to Priya about the project delay", fake_gen)
    assert "Subject: Project delay" in body and "don't have Priya's email" in body
    body, *_ = c.handle(s, "send it", fake_gen)
    assert "still need" in body and sent == []
    c.handle(s, "Priya's email is priya@example.com", fake_gen)
    c.handle(s, "yes", fake_gen)
    assert sent and sent[0][:2] == ("mail", "priya@example.com")


def test_cancel_and_revise(tmp_path):
    c, s, sent = make(tmp_path)
    c.handle(s, "text mom that I reached", fake_gen)
    body, *_ = c.handle(s, "make it more casual", fake_gen)
    assert "Running late, sorry!" in body
    body, *_ = c.handle(s, "cancel", fake_gen)
    assert "Nothing was sent" in body and s.draft is None and sent == []


def test_contacts_book(tmp_path):
    c, s, _ = make(tmp_path)
    assert "Saved Rahul" in c.handle(s, "save contact Rahul number 98765 43210 email rahul@x.com", None)[0]
    assert "+919876543210" in c.handle(s, "what is Rahul's number", None)[0]
    assert "rahul@x.com" in c.handle(s, "show my contacts", None)[0]
    assert "Removed" in c.handle(s, "delete contact Rahul", None)[0]


def test_no_model_still_drafts(tmp_path):
    c, s, _ = make(tmp_path)
    body, *_ = c.handle(s, "email priya@x.com about tomorrow's meeting", None)
    assert "priya@x.com" in body and "Subject" in body
