# JARVIS

A voice-first AI assistant for Apple-Silicon Macs. It listens (English and Hindi), thinks on your Mac with an MLX
model, speaks back, and doubles as a data-science analyst: upload a CSV or Excel file and ask for analysis, charts,
forecasts, machine-learning models, clusters, anomalies and significance tests.

## Run it

```bash
./start.sh
```

First run creates `.venv`, installs `backend/requirements.txt` and `npm install`s the interface (a few minutes plus
model downloads). Afterwards it starts the Python brain (`ws://localhost:8765`) and the interface
(http://localhost:5173). In VS Code you can also run **Terminal → Run Task → JARVIS: start everything**.

Use **Chrome** (it is needed for the microphone), click **Start JARVIS**, and allow the microphone.

Manual start: `python backend/server.py` in one terminal, `cd frontend/jarvis-ui && npm run dev` in another.
Python 3.9+ works; 3.10+ also enables picture understanding.

## What it does

| Area | Examples |
|---|---|
| Talk | "Jarvis, what's the weather in Delhi", "दिल्ली का मौसम कैसा है", "पाँच मिनट का टाइमर लगाओ" |
| Hands-free | Turn on *Hands-free*, then say "Jarvis …" (you get a beep and a ripple). Say "stop", "chup" or "bas karo" to interrupt |
| Hindi | Hindi / Hinglish understood; replies in Hindi with a natural Indian neural voice; English sentences use a British voice, and Jarvis switches by itself with the language you speak |
| Data | Upload a file → "analyse this", "show the dashboard", "forecast revenue", "clean the data", "export a report" |
| Machine learning | "predict Churn", "train a model to predict revenue", then "what if tenure is 3 and contract is Month" |
| Groups & outliers | "find natural groups", "find unusual rows" (both also give you a CSV) |
| Statistics | "is Sales different by Region", "is Churn related to contract" (picks t-test, ANOVA, correlation or chi-square) |
| Files, docs, vision | Ask questions about PDFs and documents; "what's on my screen" |

## Better Hinglish

In Hindi/Hinglish chats JARVIS is shown a few relevant example conversations (`backend/hinglish_pack.py`, 50+
built in, plus 119 more in `backend/hinglish_data/conversations.jsonl`) so his replies sound like a real friend texting. Add your own in `backend/hinglish_data/` (jsonl, csv or txt;
see the README there). This steers the model; it does not retrain it.

## Hearing

Chrome's built-in speech recognition (free, needs internet). Allow the microphone when asked. Use the **🌐** pill in the top bar
to set the listening language (AUTO / EN / हिं); pick हिं when you speak Hindi. Hands-free beeps the moment it hears "Jarvis".

## Command palette and themes

**Ctrl/Cmd + K** opens a search over every action (new chat, hands-free, language, tone, ML commands...).
The coloured dots in the top bar switch the colour theme.

## Settings

Copy `backend/.env.example` to `backend/.env`. Voice gender can also be changed live in the Controls
panel. The brain model is chosen from your RAM (Qwen3 4B / 8B / 14B / 30B-A3B); a cloud brain is optional.

## Layout

```
backend/    server.py (WebSocket) · main.py (router) · voice.py · hindi_cmd.py
            data_assistant.py · analytics.py · ml.py + ml_report.py · charts.py · reports.py · tests/
frontend/jarvis-ui/   React + Vite interface (src/App.jsx, mic.js, audio.js)
```

Tests: `cd backend && python -m pytest tests`.

## Messaging, briefing and calendar

- **Email / WhatsApp:** say "email Rahul that the meeting moved to 5" or "WhatsApp mom I'll be late". JARVIS writes the message, shows the draft, and sends only after you say "send it" (or use the chips: Make it shorter, More formal, Cancel). Drafts expire after 15 minutes.
- **Contacts:** "save Rahul's number as 98xxxxxx12", "Rahul's email is rahul@x.com", "show contacts". On a Mac it also looks names up in the Contacts app.
- **Email setup:** default opens a draft in your mail app. For real sending set `JARVIS_EMAIL_MODE=smtp` plus address and a Gmail App Password in `backend/.env`.
- **WhatsApp:** opens the chat with text filled in. `JARVIS_WHATSAPP_MODE=auto` also presses Send; grant Accessibility permission to Terminal/VS Code in System Settings first.
- **Briefing:** "morning briefing" gives date, weather (set `JARVIS_CITY`), headlines and open tasks.
- **Calendar:** "schedule a meeting with Priya tomorrow 5pm for 1 hour about the launch" gives a downloadable `.ics` that opens in Apple, Google or Outlook calendar.
- **Chats:** search, pin, and tick several chats with Select to delete them together.

## Quick tools (offline, stored on your computer)

Type **/** in the message box for a quick-command menu (also in the ⌘K palette).

- **Notes:** "note: call the bank", "show my notes", "search notes for bank", "delete note 2"
- **Expenses:** "I spent 250 on lunch", "show expenses", "undo expense" (auto-categorised, monthly summary table)
- **Converter:** "convert 5 km to miles", "100 f to c", "10 kg in pounds"
- **World clock:** "time in Tokyo" · **Split bill:** "split 2400 among 4 with 10% tip"
- **Dice, coin, random number, password generator**

## Choosing the local model (Hindi / Hinglish)

Set `JARVIS_MODEL` in `backend/.env`: `gemma4` (Google Gemma 4 26B, recommended for 24 GB+ Macs), `gemma4-12b` (16 GB Macs),
`sarvam` (Sarvam-M, built for Indian languages), `qwen`, or any mlx-community model id. Newer models need
`pip install -U mlx-lm mlx-vlm` and Python 3.10+. If the chosen model cannot load, JARVIS starts on the backup model.
Not sure which sounds best? Run `python compare_models.py` in `backend/`. It asks each model the same everyday Hinglish
questions and writes the answers side by side to `model_comparison.md`.

## Better Hindi: data and voice

- **More Hinglish examples:** in `backend/` run `python fetch_hinglish_data.py`. It downloads a public 1M-row Hinglish dataset
  (MIT licence, machine-generated and noisy), filters it hard (no rude or English-heavy lines, "aap" not "tu", male forms,
  no repeats) and keeps the best ~4000 pairs in `hinglish_data/community_filtered.jsonl`. It prints 15 samples so you can judge.
- **Gemini's voice for Hindi:** set `JARVIS_GEMINI_TTS=1` in `backend/.env` (needs `GEMINI_API_KEY`). Run `python check_cloud.py` to
  save a test clip, `gemini_voice_test.wav`. Change the voice with `JARVIS_GEMINI_TTS_VOICE`.

## Hinglish voice, hearing and editing

- **Hinglish voice:** when JARVIS speaks Hindi, English words are respelled the Indian way ("whistle" is said "सीटी",
  "potato" "पोटैटो"). Add your own in `backend/hinglish_data/loanwords.json`, e.g. `{"laptop": "लैपटॉप"}`.
- **Hinglish hearing:** `backend/hinglish_data/glossary.json` fixes words the keyboard or mic gets wrong, but only next to a
  context word ("CT", "city" or "ceete" beside "pressure cooker" means सीटी; "which city" is left alone). Edits apply with no restart.
- **Edit a message:** hover your own message and press **✎ Edit** (works for spoken messages too). Everything after it
  is dropped and JARVIS answers the edited text. Enter sends, Esc cancels.

**Hindi word lists** (all in `backend/hinglish_data/`, read at startup): `hindi_words.txt` (hand-written, ~800 words),
`verbs.words.txt` (every common verb form, built by `python gen_verbs.py`), `places_and_more.words.txt` (cities, states,
festivals, daily words). Add your own as `anything.words.txt` with `roman=devanagari` pairs.
