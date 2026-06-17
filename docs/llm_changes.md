# LLM / Voice Workstream — Change Log

This documents every file the LLM/voice work created or modified, why, and its
status. It covers two areas:

- **`scripts/speech/`** — the standalone laptop app (dev/test tool, built on
  Paria's speech pipeline) used to prove the LLM logic quickly.
- **`turtlebot4_ws/.../turtlebot4_steel_city_competition/`** — the ROS package
  that runs on the robot (the "main script" Sam pointed to).

---

## 1. Standalone app — `scripts/speech/`

Used for fast testing on a laptop (direct mic/speaker). Tool calling was added
and verified here by voice before moving into the ROS package.

| File | New/Modified | What changed |
| --- | --- | --- |
| `tools.py` | **New** | Defines the tools the LLM can call: `navigate_to` (placeholder, returns success) and `record_order`. Schemas + implementations + `execute_tool` dispatch. |
| `llm.py` | Modified | Rewrote as a **tool-calling loop**: calls the model, runs any requested tools, feeds results back, repeats until a final reply. Returns `(reply, order_recorded)`. |
| `config.py` | Modified | System prompt updated for natural speech + tool use. Added **fuzzy wake-word matching** (`TRIGGER_FUZZY_THRESHOLD`) and extra trigger-phrase variants. |
| `main.py` | Modified | Wake word now uses **fuzzy matching** (handles Whisper hearing "server boot/vote"). Added a one-turn **courtesy window** after an order. Order flow is tool-driven. |
| `order.py` | Modified | Added `get_latest_order()` to read back the most recent saved order. |
| `test_tools.py` | **New** | Text-only harness to test the tool-calling LLM without a mic. |

---

## 2. ROS package — robot code

### New files

| File | Purpose |
| --- | --- |
| `src/llm/__init__.py` | Makes `llm` an importable subpackage. |
| `src/llm/order_taker.py` | **Self-contained, audio-free order-taking brain.** `OrderTaker` class: OpenAI tool calling (`record_order`), no mic/Whisper/TTS. Reads the API key from the environment only. `chat(text) -> (reply, order)`. This is the robot's source of truth for order logic. |

### Modified files

| File | What changed |
| --- | --- |
| `src/behaviors/take_order_behavior.py` | Implemented the behavior. Steps 3 & 4 (greet + take order) are **real** via `OrderTaker`. Navigation, database, and speech I/O are placeholders. **Non-blocking by design** (team decision): `_ask` has a timeout, gives up after `max_no_reply` silent turns, and the whole `plan()` is wrapped in try/except so a broken step never freezes the robot. Also fixed a pre-existing indentation bug. |
| `src/actions/speech_to_text.py` | Filled `todo_run_whisper`: buffers streamed mic chunks, segments utterances by silence (RMS VAD), transcribes with Whisper (`transcribe_array`, model "base", numpy array → no ffmpeg). Added `get_next_utterance(timeout)` (the request-with-timeout the behavior calls) and publishes transcripts to `/speech_text`. |
| `src/actions/text_to_speech.py` | Filled `todo_run_tts`: real offline speech via `synthesize_to_array` (pyttsx3 — SAPI on Windows, espeak on Linux → 16 kHz float array). Guarded the continuous white-noise generator behind `SPEECH_CONFIG["white_noise"]` (default off) so it no longer drowns real speech. |

### Docs

| File | What changed |
| --- | --- |
| `docs/speech.md` | Documented the tool-calling design and how to add new tools. |
| `docs/llm_changes.md` | This file. |

---

## How it fits together (on the robot)

```
mic → /audio topic → SpeechToText.todo_run_whisper (VAD + Whisper)
                          → get_next_utterance(timeout)
                                    ↑
take_order_behavior.plan():        |
   _get_table_awaiting_order()  (DB stub)
   _navigate_to("table_N")      (Nav placeholder → success)
   _take_order():  loop  _ask() ─┘  →  OrderTaker.chat()  →  _say()
   _save_order_to_db(table, items, notes)  (DB stub)
                                    |
   _say(text) → TextToSpeech.todo_run_tts (pyttsx3) → /audio_output → speaker
```

---

## Status

**Done & tested (off the robot):**
- LLM order-taking + tool calling (voice-tested in the standalone app)
- `OrderTaker` (tested in isolation)
- `take_order_behavior.py` order logic (tested in isolation)
- STT + TTS nodes: **TTS→STT round-trip verified** ("I would like a burger and a coke" came back correctly)

**Placeholders to swap when other teams deliver:**
- `navigate_to(location_id) -> bool` (Navigation)
- `get_table_awaiting_order()`, `save_order(table_id, items, notes)`, `set_table_ordered(table_id)` (Database)

**To do on robot day:**
- Run live in ROS/Docker; tune STT thresholds (`speech_rms_threshold`, `silence_seconds`) to the real mic
- Confirm Docker has: `openai-whisper`, `pyttsx3` + `espeak`, `scipy`, `openai`
- Set `OPENAI_API_KEY` in the robot environment
- Rotate the exposed API key
