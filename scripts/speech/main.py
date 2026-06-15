"""
EMSRC 2026 - Restaurant Challenge
LLM Voice Pipeline: Microphone → Whisper STT → OpenAI LLM → TTS

Usage:
    python main.py
"""

import re
import sys

import config
import stt
import llm
import tts
import order


GOODBYE_WORDS = {"goodbye", "bye", "exit", "quit", "stop", "thank you goodbye"}


def _normalise_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_after_trigger(user_text: str) -> tuple[bool, str]:
    normalised = _normalise_text(user_text)

    for phrase in config.TRIGGER_PHRASES:
        phrase = _normalise_text(phrase)

        if phrase in normalised:
            index = normalised.find(phrase)
            after_trigger = normalised[index + len(phrase):].strip()
            return True, after_trigger

    return False, user_text.strip()


def start_customer() -> None:
    tts.speak("Hello! I am your robot waiter. How can I help you today?")


def sleep_message() -> None:
    print("[MAIN] Waiting for trigger phrase: Hey ServerBot")


def main() -> None:
    print("=" * 50)
    print("  EMSRC 2026 — Robot Waiter Voice Assistant")
    print("  Say 'Hey ServerBot' to activate")
    print("  Press Ctrl+C to quit")
    print("=" * 50)

    stt._load_model()

    active = False
    sleep_message()

    while True:
        user_text = stt.listen()

        if user_text is None:
            if active:
                tts.speak("Sorry, I didn't catch that. Could you please repeat?")
            continue

        print(f"[USER] {user_text!r}")

        triggered, text_after_trigger = _extract_after_trigger(user_text)

        if not active:
            if not triggered:
                print("[MAIN] Trigger phrase not detected. Ignoring utterance.")
                continue

            active = True
            llm.reset_conversation()

            if not text_after_trigger:
                start_customer()
                continue

            user_text = text_after_trigger
            print(f"[MAIN] Trigger detected. Processing: {user_text!r}")

        else:
            if triggered and text_after_trigger:
                user_text = text_after_trigger
                print(f"[MAIN] Trigger repeated. Processing: {user_text!r}")

        if any(word in _normalise_text(user_text) for word in GOODBYE_WORDS):
            tts.speak("Thank you! Have a wonderful meal.")

            if order.is_confirmed():
                order.save_and_reset()

            llm.reset_conversation()
            active = False
            sleep_message()
            continue

        try:
            reply, order_data = llm.chat(user_text)
            tts.speak(reply)

            if order_data:
                order.update(order_data)

                if order.is_confirmed():
                    saved = order.save_and_reset()
                    tts.speak(
                        f"Perfect! I have placed your order for "
                        f"{', '.join(saved['items'])}. "
                        f"It will be with you shortly!"
                    )

                    llm.reset_conversation()
                    active = False
                    sleep_message()

        except EnvironmentError as e:
            print(f"\n[ERROR] {e}\n")
            sys.exit(1)

        except Exception as e:
            print(f"[ERROR] {e}")
            tts.speak("I'm sorry, I encountered an error. Could you repeat that?")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down.")