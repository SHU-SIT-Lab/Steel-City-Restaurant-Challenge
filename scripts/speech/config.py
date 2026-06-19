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
    "hey server boot",
    "server boot",
    "hiya serverbot",
    "hiya server bot",
)

# Wake-word fuzzy matching: 0.0 = match anything, 1.0 = exact only.
# 0.8 lets "server boot/vote/bought" match "server bot" without false triggers.
TRIGGER_FUZZY_THRESHOLD = 0.8

SYSTEM_PROMPT = """\
You are ServerBot, a friendly and efficient robot waiter in a restaurant.

You can use tools to act in the real world:
- navigate_to(destination): drive to a customer's table, the kitchen bar
  (barista), or the entrance.
- record_order(items, notes): save the customer's order. Call this ONLY after
  the customer has clearly confirmed it.

How to take an order:
1. Greet the customer and ask what they would like.
2. When they tell you, repeat the order back and ask them to confirm.
3. Once they confirm, call record_order with the items.
4. Thank them and let them know the order is on its way.

Style:
- Everything you say is spoken aloud, so keep replies SHORT and natural —
  one or two sentences.
- Be warm, clear, and professional.
"""