import fetch_hinglish_data as F

GOOD = [
    ("kya yaar, aaj traffic mein bahut fans gaya", "Arre, phir toh aap late ho gaye honge. Koi baat nahi, aaram se aaiye."),
    ("kaunsa movie dekha tumne kal", "Maine toh kuch nahi dekha, par aap batao, kaunsi dekhne ka mood hai aapka?"),
    ("aaj khana kya banaya hai ghar mein", "Aaj dal chawal aur sabzi bani hai, simple aur ghar jaisa. Aap kya khayenge?"),
]
BAD = [
    ("kya hua", "tu pagal hai kya bc"),                                       # rude + tu
    ("how are you doing today my friend", "just chilling at home watching a movie"),   # English
    ("kya haal hai bhai", "Main theek hoon, aaj mera kaam karti rahi hoon bahut"),    # feminine first person
    ("namaste", "namaste"),                                                   # echo, too short
    ("kya kar rahe ho abhi", "kya kar rahe ho abhi tum bolo"),                # echo
    ("aaj kya plan hai tumhara", "देखो कुछ नहीं है आज"),                       # devanagari
    ("kal milte hain kya phir", "dekho http://x.com pe aana kal subah"),      # link
]


def test_scoring_accepts_good_rejects_bad():
    for u, r in GOOD:
        assert F.score_pair(u, r) is not None, (u, r)
    for u, r in BAD:
        assert F.score_pair(u, r) is None, (u, r)


def test_select_dedupes_and_fixes_spelling():
    rows = GOOD + GOOD + BAD + [("kya haal hai aaj kal", "Sab nhi theek hai yaar, bas kaam bahut hai aaj kal")]
    out = F.select(rows, keep=10)
    users = [u for u, _ in out]
    assert len(users) == len(set(users)) == 4
    assert any("nahi" in r and "nhi" not in r for _, r in out)
