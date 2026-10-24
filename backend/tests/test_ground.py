import tools


def test_looks_factual():
    assert tools.looks_factual("tell me about the Khubsurat movie in which Sonam Kapoor acted")
    assert tools.looks_factual("who directed Inception?")
    assert not tools.looks_factual("write an email to Rahul about the movie")
    assert not tools.looks_factual("summarise this document")
    assert not tools.looks_factual("hi")


def test_gather_evidence_uses_wikipedia_and_web():
    orig = (tools.wikipedia_search, tools.http_json, tools.web_search)
    seen = {}
    tools.wikipedia_search = lambda q, n=5: seen.setdefault("q", q) and [{"title": "Khoobsurat (2014 film)", "url": "https://w/k", "snippet": "s"}]
    tools.http_json = lambda url, timeout=None: {"extract": "Khoobsurat is a 2014 film starring Sonam Kapoor, produced by Disney.", "type": "standard"}
    tools.web_search = lambda q, n=4: [{"title": "Khoobsurat", "url": "https://x/y", "snippet": "Disney Pictures India film"}]
    try:
        ref, src = tools.gather_evidence("tell me about the Khubsurat movie in which Sonam Kapoor acted")
    finally:
        tools.wikipedia_search, tools.http_json, tools.web_search = orig
    assert seen["q"].startswith("Khubsurat movie")
    assert "Sonam Kapoor" in ref and len(src) == 2
