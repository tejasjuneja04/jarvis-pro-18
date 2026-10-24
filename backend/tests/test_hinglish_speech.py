"""Hindi speech text: the Roman Hinglish a reply is shown in is respelled in Devanagari only for the Hindi voice.

Regression tests for: "signs" said "signas", "hzir hona" mangled, "schedules" in a strange accent.
Expected outputs are explicit. Rule-based fallback output is only asserted where it is known to be right.
"""
import pytest

import lang
import loanwords
import voice as V

conv = lang.roman_hinglish_to_devanagari


# ---------------------------------------------------------------- the reported words
@pytest.mark.parametrize("raw,expect", [
    ("signs", "साइन्स"),
    ("sign", "साइन"),
    ("schedule", "शेड्यूल"),
    ("schedules", "शेड्यूल्स"),
    ("scheduled", "शेड्यूल्ड"),
    ("hazir hona", "हाज़िर होना"),
    ("hzir hona", "हाज़िर होना"),
    ("hajir hona hai", "हाज़िर होना है"),
    ("haazir hone", "हाज़िर होने"),
])
def test_reported_words(raw, expect):
    assert conv(raw) == expect


def test_reported_sentences():
    assert conv("kal ka schedule dekhein") == "कल का शेड्यूल देखें"
    assert conv("Your signs and schedules are ready") == "Your साइन्स and शेड्यूल्स are रेडी"
    assert conv("Aapko meeting mein hazir hona hai") == "आपको मीटिंग में हाज़िर होना है"


# ---------------------------------------------------------------- word-initial clusters
def test_word_cannot_start_with_a_halant_cluster():
    assert lang.transliterate("hzir") == "हज़िर"      # no "ह्ज़": Hindi keeps the vowel here
    assert lang.transliterate("kzir") == "कज़िर"


def test_valid_word_initial_clusters_still_join():
    assert lang.transliterate("kya") == "क्या"          # consonant + y
    assert lang.transliterate("stri") == "स्त्री"       # s + consonant
    assert lang.transliterate("hindi") == "हिंदी"       # mid-word nasal and cluster unchanged
    assert lang.transliterate("baatein") == "बातें"


# ---------------------------------------------------------------- English must stay English
@pytest.mark.parametrize("word", ["mention", "nightly", "watching"])
def test_unknown_english_words_stay_latin(word):
    assert conv(f"aap {word} karo") == f"आप {word} करो"


def test_english_inflections_are_recognised():
    for w in ("signed", "scheduling", "booked", "bookings"):
        assert lang._is_english(w) or loanwords.lookup(w), w


def test_hindi_words_that_look_english_are_not_blocked():
    assert conv("kaise ho") == "कैसे हो"
    assert conv("aise hi jaise") == "ऐसे ही जैसे"
    assert conv("bhai pan lao") == "भाई पैन लाओ"


def test_abbreviations_urls_emails_code_and_accents_are_untouched():
    assert conv("ABC XYZ ho gaya") == "ABC XYZ हो गया"
    assert conv("link: https://example.com/signs?x=1 dekho") == "लिंक: https://example.com/signs?x=1 देखो"
    assert conv("mail rahul@signs.com ko bhejo") == "मेल rahul@signs.com को भेजो"
    assert conv("run `pip install signs` karo") == "run `pip install signs` करो"
    assert conv("Café ☕ चाय bhi") == "Café ☕ चाय भी"


def test_known_abbreviations_still_use_the_dictionary():
    assert conv("OK sir, AI ka kaam hai") == "ओके सर, ए.आई. का काम है"
    assert conv("KYA hua") == "क्या हुआ"


# ---------------------------------------------------------------- empty and odd input
@pytest.mark.parametrize("raw", ["", "   ", "\n\t", "😀", "12345", "!!! ???", "५ बजे"])
def test_nothing_to_convert_is_returned_unchanged(raw):
    assert conv(raw) == raw


def test_punctuation_numbers_and_emoji_survive():
    assert conv("😀 mujhe 5 baje call karo!") == "😀 मुझे 5 बजे call करो!"
    assert conv("Meeting at 5pm, hazir hona.") == "मीटिंग at 5pm, हाज़िर होना."


def test_conversion_never_raises_on_odd_input():
    for raw in ("a" * 5000, "\u0000\u200d", "ǅ ǆ ß ñ", "kya\u0301 hai", "-" * 50, "I", "a b c d"):
        assert isinstance(conv(raw), str)


# ---------------------------------------------------------------- dictionary overrides and fallbacks
def test_existing_dictionary_overrides_still_win():
    assert conv("whistle") == "सीटी"
    assert conv("potato") == "पोटैटो"
    assert loanwords.lookup("laptop") == "लैपटॉप"
    assert conv("Hi sir") == "Hi सर"                      # a greeting, not "ही"


def test_unknown_hinglish_word_falls_back_to_rules():
    assert conv("seekhna") != "seekhna"                   # transliterated, not left in Latin letters


def test_loanword_json_overrides_builtin():
    saved = loanwords._extra
    try:
        loanwords._extra = {"signs": "साइंस"}
        assert loanwords.lookup("signs") == "साइंस"
    finally:
        loanwords._extra = saved
    assert loanwords.lookup("signs") == "साइन्स"


# ---------------------------------------------------------------- display text stays Roman, speech text is separate
def test_hindi_voice_gets_devanagari_but_the_original_text_is_not_touched():
    shown = "Kal ka schedule dekhein, hazir hona hai"
    keep = str(shown)
    lang_code, spoken = V.Voice.pick_language(None, shown, "hi")
    assert lang_code == "hi"
    assert spoken == "कल का शेड्यूल देखें, हाज़िर होना है"
    assert shown == keep                                   # what the chat displays is unchanged


def test_english_sentences_are_not_respelled():
    for hint in ("hi", "en"):
        code, spoken = V.Voice.pick_language(None, "Your schedule is ready", hint)
        assert spoken == "Your schedule is ready"
        assert code in ("en", "en-in")


def test_devanagari_text_goes_to_the_hindi_voice_as_is():
    assert V.Voice.pick_language(None, "आपका शेड्यूल तैयार है", "en") == ("hi", "आपका शेड्यूल तैयार है")
