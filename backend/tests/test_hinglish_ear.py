import hinglish_ear as ear
import lang
import loanwords


def test_ct_next_to_cooker_is_seeti():
    out, hints = ear.normalize("City ka matlab pressure kukar ki CT")
    assert "cooker" in out and out.lower().count("seeti") == 2 and "city" not in out.lower()
    assert hints and "सीटी" in hints[0]


def test_mis_hearings_of_seeti():
    for bad in ("ceete", "ct", "city", "cheete", "see tea"):
        out, _ = ear.normalize(f"aloo ke liye kitni {bad} deni hai")
        assert "seeti" in out, bad


def test_city_and_ct_scan_untouched_without_context():
    assert ear.normalize("which city is Delhi in")[0] == "which city is Delhi in"
    assert ear.normalize("what is a CT scan")[0] == "what is a CT scan"


def test_whistle_is_spoken_the_indian_way():
    spoken = lang.roman_hinglish_to_devanagari("Aloo ke liye 3 whistles dena, phir potato soft ho jayega")
    assert "सीटी" in spoken and "whistle" not in spoken
    assert "पोटैटो" in spoken and "सॉफ़्ट" in spoken


def test_loanword_plural_and_unknown():
    assert loanwords.lookup("Phones") == "फ़ोन"
    assert loanwords.lookup("xylophone") is None


def test_hindi_words_still_hindi():
    assert lang.roman_hinglish_to_devanagari("kya haal hai") == "क्या हाल है" or "क्या" in lang.roman_hinglish_to_devanagari("kya haal hai")


def test_hindi_words_that_look_english_are_hindi():
    out = lang.roman_hinglish_to_devanagari("Pressure cooker ka dhakkan band karke jaldi ban jayega, kafi thode sakht hain")
    assert "बन जाएगा" in out and "ढक्कन" in out and "काफ़ी" in out and "थोड़े" in out
    assert "ban" not in out.lower()


def test_ly_words_and_mein():
    assert "नॉर्मली" in lang.roman_hinglish_to_devanagari("Aloo ke liye normally 3 seeti kafi hai")
    assert "मैं बताऊँगा" in lang.roman_hinglish_to_devanagari("phir mein bataunga")
    assert "में" in lang.roman_hinglish_to_devanagari("ghar mein hai")


def test_big_word_list_loaded():
    assert lang._WORDS_LOADED > 300
    assert lang.roman_hinglish_to_devanagari("kal subah paratha aur chai banana, bahut bhookh lagi hai").count("पराठा") == 1
    assert lang.roman_hinglish_to_devanagari("Thank you sir") == "Thank you सर"
    for tok in open(__import__("os").path.join(__import__("os").path.dirname(lang.__file__), "hinglish_data", "hindi_words.txt"), encoding="utf-8").read().split():
        if "=" in tok and not tok.startswith("#"):
            assert not any(c.isascii() and c.isalpha() for c in tok.split("=", 1)[1]), tok


def test_do_to_me_next_to_hindi_words():
    assert "डाल दो" in lang.roman_hinglish_to_devanagari("cooker mein daal do")
    assert "आप तो" in lang.roman_hinglish_to_devanagari("aap to ghar jaoge")
    assert "Pune" not in lang.roman_hinglish_to_devanagari("kal Pune jaunga") and "पुणे" in lang.roman_hinglish_to_devanagari("kal Pune jaunga")


def test_generated_verbs_loaded():
    out = lang.roman_hinglish_to_devanagari("main dekhunga aur bulaiye, phir sunna padega")
    assert "देखूँगा" in out and "बुलाइए" in out and "सुनना" in out
