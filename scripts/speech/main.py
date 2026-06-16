"""
EMSRC 2026 - Restaurant Challenge
LLM Voice Pipeline: Microphone → Whisper STT → OpenAI LLM → TTS

Usage:
    python main.py
"""

import difflib
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


def _fuzzy_find_trigger(words: list[str]) -> int:
    """Return the word index just AFTER a wake-word match, or -1 if none.

    Slides each trigger phrase over the spoken words and accepts a window if it
    is similar enough (handles Whisper hearing 'bot' as 'boot', 'vote', etc.).
    """
    best_end = -1
    for phrase in config.TRIGGER_PHRASES:
        phrase_words = _normalise_text(phrase).split()
        n = len(phrase_words)
        if n == 0 or n > len(words):
            continue

        target = " ".join(phrase_words)
        for i in range(len(words) - n + 1):
            window = " ".join(words[i:i + n])
            ratio = difflib.SequenceMatcher(None, window, target).ratio()
            if ratio >= config.TRIGGER_FUZZY_THRESHOLD:
                best_end = max(best_end, i + n)
    return best_end


def _extract_after_trigger(user_text: str) -> tuple[bool, str]:
    words = _normalise_text(user_text).split()
    if not words:
        return False, ""

    end = _fuzzy_find_trigger(words)
    if end == -1:
        return False, user_text.strip()

    after_trigger = " ".join(words[end:]).strip()
    return True, after_trigger


def start_customer() -> None:
    tts.speak("Hello! I am your robot waiter. How can I help you today?")


def sleep_message() -> None:
    print("[MAIN] Waiting for trigger phrase: Hey ServerBot")


def _courtesy_turn() -> None:
    """After an order, catch a single closing 'thanks/bye' without the wake word.

    Listens once. Replies warmly to a courtesy remark, otherwise stays silent
    (so ambient noise doesn't get a response). Keeps the robot polite without
    re-opening a full conversation.
    """
    closing = stt.listen()
    if not closing:
        return

    print(f"[USER] (closing) {closing!r}")
    text = _normalise_text(closing)

    if any(word in text for word in ("thank", "thanks", "cheers")):
        tts.speak("You're welcome! Enjoy your meal.")
    elif any(word in text for word in GOODBYE_WORDS):
        tts.speak("Goodbye!")


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
            # The LLM may call tools (navigation, record_order) before replying.
            reply, order_recorded = llm.chat(user_text)
            tts.speak(reply)

            # When an order has been saved, this customer is done.
            # Offer one brief courtesy turn, then go back to sleep.
            if order_recorded:
                llm.reset_conversation()
                active = False
                _courtesy_turn()
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