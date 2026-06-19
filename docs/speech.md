# Speech

Voice pipeline for the robot waiter: **microphone → denoising → Whisper STT →
OpenAI LLM (with tool calling) → TTS**.

Code lives in `scripts/speech/`.

## Modules

| File         | Role                                                                 |
| ------------ | -------------------------------------------------------------------- |
| `config.py`  | All settings (audio, Whisper, OpenAI, trigger phrases, system prompt).|
| `stt.py`     | Microphone capture, denoising, Whisper speech-to-text.               |
| `llm.py`     | OpenAI chat **with tool calling** (agentic loop).                    |
| `tools.py`   | Tool definitions the LLM can call (navigation, order recording).     |
| `order.py`   | Persists confirmed orders to `orders.json`.                          |
| `tts.py`     | Text-to-speech playback.                                             |
| `main.py`    | Runs the loop: wake on "Hey ServerBot", listen, think, speak.        |

## Tool calling

The LLM does not just talk — it can **call tools** to act in the world. Tools are
defined in `tools.py`: each has a JSON *schema* (sent to the model) and a Python
*implementation* (run when the model asks for it).

Current tools:

| Tool                      | Effect                                                        |
| ------------------------- | ------------------------------------------------------------ |
| `navigate_to(destination)`| Drive to `table_1`, `kitchen_bar`, `entrance`, etc.          |
| `record_order(items, notes)`| Save a confirmed order via `order.py`.                     |

`llm.chat(user_text)` runs an agentic loop: it calls the model, executes any
tools the model requests, feeds the results back, and repeats until the model
returns a final spoken reply. It returns `(reply_text, order_recorded)`.

### Navigation

`navigate_to` calls the competition navigation ROS service
(`/navigation/navigate_to_waypoint`) when the navigation server is running.
If ROS or the service is unavailable, it logs a warning and returns success so
speech development can continue offline.

### Adding a new tool

1. Write the Python function in `tools.py`.
2. Add its JSON schema to the `TOOLS` list.
3. Register it in the `_DISPATCH` dict.

## Setup

Set the API key as an environment variable (do **not** hardcode it in `config.py`):

```powershell
$env:OPENAI_API_KEY = "sk-...your-key..."
```

Run:

```bash
python scripts/speech/main.py
```

Say **"Hey ServerBot"** to activate, then place an order.
