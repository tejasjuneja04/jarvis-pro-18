"""
Builds hinglish_data/verbs.words.txt: every common form of ~150 Hindi verbs, Roman -> Devanagari.
    python gen_verbs.py
Add a verb by appending (roman stem, devanagari stem) to C_STEMS (ends in a consonant sound: kar) or
A_STEMS (ends in the long 'aa' sound: bata, kha, ja).  Irregular verbs (jana, dena, lena, hona, pina) are listed by hand below.
"""
from pathlib import Path

C_STEMS = """kar कर|dekh देख|bol बोल|sun सुन|padh पढ़|likh लिख|chal चल|ruk रुक|rakh रख|mil मिल|samajh समझ|puch पूछ|poochh पूछ|soch सोच
khol खोल|bhej भेज|dhoondh ढूँढ|kharid खरीद|seekh सीख|sikh सीख|nikal निकल|daal डाल|dal डाल|uth उठ|baith बैठ|ghoom घूम|khel खेल|kaat काट
bhar भर|badal बदल|badh बढ़|maang माँग|bhool भूल|pehchan पहचान|sambhal संभाल|pakad पकड़|chhod छोड़|tod तोड़|jod जोड़|phenk फेंक|utar उतर
chadh चढ़|ban बन|pak पक|gir गिर|mar मर|ud उड़|jal जल|hans हँस|tair तैर|dar डर|nach नाच|lad लड़|jeet जीत|haar हार|bech बेच|gin गिन
ubaal उबाल|bhun भून|tal तल|pees पीस|sek सेक|kas कस|gal गल|khil खिल|pighal पिघल|thak थक|jaag जाग|bhaag भाग|daud दौड़|kud कूद
bhij भीग|bhigo भिगो|chun चुन|bun बुन|dhul धुल|chamak चमक|chhup छुप|chhip छिप|chhu छू|pahunch पहुँच|lout लौट|laut लौट|mod मोड़|jhuk झुक
ginwa गिनवा|likhwa लिखवा|bulwa बुलवा|bula बुला|dhak ढक|lipat लिपट|bandh बाँध|khich खींच|dhakel धकेल|mang माँग|rakhwa रखवा|ghus घुस
pad पड़|sambhal संभल|ghat घट|bachh बच|ruk रुक|thehar ठहर|thahar ठहर|tikk टिक|chak चख|sunaa सुना|khod खोद|jhad झाड़|saaf साफ़|sukha सुखा
mehsoos महसूस|intezaar इंतज़ार|koshish कोशिश|istemaal इस्तेमाल|shuru शुरू|khatam ख़त्म|band बंद|chalu चालू|pasand पसंद|yaad याद|maaf माफ़""".replace("\n", "|").split("|")
A_STEMS = """bata बता|bana बना|laga लगा|dikha दिखा|suna सुना|sikha सिखा|samjha समझा|hata हटा|mila मिला|jaga जगा|chala चला|utha उठा|gira गिरा
rula रुला|hansa हँसा|kha खा|ga गा|aa आ|ja जा|pa पा|sula सुला|khila खिला|pila पिला|dila दिला|jala जला|chhupa छुपा|dikhla दिखला|bhula भुला
nikala निकाला|dhoya धोया|baitha बैठा|sambhala संभाला|pakda पकड़ा|ghuma घुमा|ghumaa घुमा|badha बढ़ा|ghata घटा|bacha बचा|uda उड़ा|bhaga भगा|mita मिटा|sajaa सजा|sajja सजा|dhaka ढका|rakha रखा|kaata काटा""".replace("\n", "|").split("|")

# suffix: (roman, devanagari matra form for consonant stems)
C_SUF = [("na", "ना"), ("ta", "ता"), ("ti", "ती"), ("te", "ते"), ("ega", "ेगा"), ("egi", "ेगी"), ("enge", "ेंगे"), ("o", "ो"),
         ("iye", "िए"), ("unga", "ूँगा"), ("ungi", "ूँगी"), ("e", "े"), ("ein", "ें"), ("en", "ें"), ("ne", "ने"), ("ni", "नी"),
         ("ke", "के"), ("kar", "कर"), ("lo", "लो"), ("ti hai", ""), ("ta hai", "")]
C_SUF = [x for x in C_SUF if x[1]]
# for stems ending in the long 'aa' sound: roman suffix, devanagari
A_SUF = [("na", "ना"), ("ta", "ता"), ("ti", "ती"), ("te", "ते"), ("ya", "या"), ("yi", "यी"), ("ye", "ये"), ("yega", "एगा"), ("yegi", "एगी"),
         ("yenge", "एँगे"), ("ega", "एगा"), ("egi", "एगी"), ("enge", "एँगे"), ("o", "ओ"), ("iye", "इए"), ("unga", "ऊँगा"), ("ungi", "ऊँगी"),
         ("ein", "एँ"), ("en", "एँ"), ("ne", "ने"), ("ni", "नी"), ("ke", "के"), ("kar", "कर"), ("lo", "लो"), ("ye", "ये")]

# irregular verbs, written out
EXTRA = """jana=जाना jaana=जाना gaya=गया gayi=गई gaye=गए gayee=गई jaaye=जाए jaye=जाए jaa=जा
dena=देना diya=दिया diye=दिए dijiye=दीजिए dega=देगा degi=देगी denge=देंगे dunga=दूँगा dungi=दूँगी deta=देता deti=देती dete=देते dein=दें de=दे deni=देनी
lena=लेना liya=लिया liye=लिए lijiye=लीजिए lega=लेगा legi=लेगी lenge=लेंगे lunga=लूँगा lungi=लूँगी leta=लेता leti=लेती lete=लेते lein=लें le=ले leni=लेनी
hona=होना hoon=हूँ hun=हूँ ho=हो hai=है hain=हैं tha=था thi=थी the=थे hua=हुआ hui=हुई hue=हुए hoga=होगा hogi=होगी honge=होंगे hota=होता hoti=होती hote=होते honi=होनी
pina=पीना piya=पिया piye=पिए piyo=पियो pijiye=पीजिए piyega=पिएगा piyegi=पिएगी piyenge=पिएँगे piyunga=पिऊँगा piyungi=पिऊँगी peeta=पीता peeti=पीती peete=पीते
kiya=किया kiye=किए ki=की kijiye=कीजिए kijie=कीजिए karna=करना karni=करनी kar=कर karke=करके
rehna=रहना raha=रहा rahi=रही rahe=रहे rahega=रहेगा rahegi=रहेगी rahenge=रहेंगे rahunga=रहूँगा rahungi=रहूँगी
sona=सोना soya=सोया soyi=सोई soye=सोए soiye=सोइए soyega=सोएगा soyegi=सोएगी soyenge=सोएँगे sounga=सोऊँगा sota=सोता soti=सोती sote=सोते
rona=रोना roya=रोया roye=रोए roiye=रोइए roega=रोएगा rota=रोता roti=रोती rote=रोते
dhona=धोना dhoya=धोया dhoye=धोए dhoiye=धोइए dhoega=धोएगा dhota=धोता dhoti=धोती dhote=धोते dho=धो
milna=मिलना milta=मिलता milti=मिलती milte=मिलते
aana=आना aaya=आया aayi=आई aaye=आए aaega=आएगा aayega=आएगा aayegi=आएगी aayenge=आएँगे aaunga=आऊँगा aaungi=आऊँगी aata=आता aati=आती aate=आते aao=आओ aaiye=आइए
khana=खाना khaya=खाया khaye=खाए khayega=खाएगा khayegi=खाएगी khaunga=खाऊँगा khata=खाता khati=खाती khate=खाते khao=खाओ khaiye=खाइए
dekhna=देखना dekhunga=देखूँगा dekhenge=देखेंगे dekha=देखा dekhi=देखी dekhe=देखे
pata=पता pta=पता""".replace("\n", " ")


def build():
    seen, out = set(), []

    def add(r, d):
        if r not in seen:
            seen.add(r)
            out.append(f"{r}={d}")

    for item in C_STEMS + A_STEMS:
        item = item.strip()
        if not item:
            continue
        r, d = item.split()
        if d[-1] == "ा":                                    # bata, kha, bula: long-aa stems
            for sr, sd in A_SUF:
                add(r + sr, d + sd)
            add(r, d)
        elif d[-1] in "ीूोेै":                              # chhu, dho, bhigo: other vowel stems
            for sr, sd in A_SUF:
                if not sr.startswith("y") and sr not in ("ya", "ye", "yi"):
                    add(r + sr, d + sd)
        else:                                              # kar, dekh: ends in a consonant
            for sr, sd in C_SUF:
                add(r + sr, d + sd)
    for tok in EXTRA.split():
        r, _, d = tok.partition("=")
        add(r, d)
    return out


if __name__ == "__main__":
    words = build()
    path = Path(__file__).resolve().parent / "hinglish_data" / "verbs.words.txt"
    body = "# generated by gen_verbs.py, do not edit by hand (add your own words to hindi_words.txt)\n"
    for i in range(0, len(words), 8):
        body += " ".join(words[i:i + 8]) + "\n"
    path.write_text(body, encoding="utf-8")
    print(f"{len(words)} verb forms -> {path}")
