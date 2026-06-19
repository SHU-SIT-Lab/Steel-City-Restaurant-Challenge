import os

SAMPLE_RATE = 16000
CHANNELS = 1

NOISE_CALIBRATION_SECONDS = 0.8
SPEECH_THRESHOLD_MULTIPLIER = 1.5
MIN_SPEECH_THRESHOLD = 0.006
MAX_SPEECH_THRESHOLD = 0.025
MAX_WAIT_FOR_SPEECH_SECONDS = 5

SILENCE_DURATION = 1.4
MAX_RECORD_SECONDS = 15
MIN_AUDIO_SECONDS = 0.4

ENABLE_DENOISING = True
DENOISE_BACKEND = "huggingface"

HF_DENOISE_MODEL = "speechbrain/metricgan-plus-voicebank"
HF_DENOISE_SAVEDIR = "pretrained_models/metricgan-plus-voicebank"

WHISPER_MODEL = "small"
WHISPER_LANGUAGE = "en"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"   
MAX_TOKENS = 300  

TTS_RATE = 175
TTS_VOLUME = 1.0

TRIGGER_PHRASES = (
    "hey serverbot",
    "hey server bot",
    "serverbot",
    "server bot",
)

SYSTEM_PROMPT = """\
You are a friendly and efficient robot waiter in a restaurant.
You MUST always respond with valid JSON in exactly this format — no extra text outside the JSON:

{
  "reply": "<one or two sentences spoken aloud to the customer>",
  "order": {
    "confirmed": <true | false>,
    "items": ["<item1>", "<item2>", ...],
    "notes": "<dietary needs or special requests, empty string if none>"
  }
}

Rules:
- "reply" is spoken aloud — keep it SHORT and natural.
- "order.items" lists everything the customer wants so far.
- "order.confirmed" is true ONLY after the customer explicitly confirms.
- Always repeat the order back before setting confirmed to true.
- If no order yet, use an empty items list and confirmed: false.
- Be warm, clear, and professional.
"""