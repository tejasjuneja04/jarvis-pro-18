from datetime import datetime

import briefing as B

NOW = datetime(2026, 10, 23, 18, 0)      # a Friday


def test_when_variants():
    assert B.parse_when("tomorrow at 5pm", NOW) == datetime(2026, 10, 24, 17, 0)
    assert B.parse_when("on monday 9:30 am", NOW) == datetime(2026, 10, 26, 9, 30)
    assert B.parse_when("kal shaam 5 baje", NOW) == datetime(2026, 10, 24, 17, 0)
    assert B.parse_when("25 december at 10am", NOW) == datetime(2026, 12, 25, 10, 0)
    assert B.parse_when("nothing here", NOW) is None


def test_event_title_and_length():
    ev = B.parse_event("schedule a meeting with Rahul tomorrow at 5pm for 90 minutes about the launch", NOW)
    assert ev["minutes"] == 90 and "Rahul" in ev["title"] and "launch" in ev["title"]
    assert B.parse_event("what's the weather tomorrow", NOW) is None


def test_ics_is_valid():
    ev = B.parse_event("add a call with Priya today at 8pm", NOW)
    ics = B.build_ics(ev)
    assert ics.startswith("BEGIN:VCALENDAR") and "DTSTART:20261023T200000" in ics and "SUMMARY:Call with Priya" in ics


def test_briefing_phrases():
    for t in ("morning briefing", "brief me", "what's my day look like", "give me my daily briefing"):
        assert B.BRIEF_RE.search(t), t
    assert not B.BRIEF_RE.search("make a briefing note about sales")
