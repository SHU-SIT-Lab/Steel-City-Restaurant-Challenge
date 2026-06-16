"""Quick text-only test of the tool-calling LLM (no microphone/speaker).

Type what a customer would say; the robot's spoken reply is printed.
Watch the [LLM] Tool call / [NAV] / [ORDER] lines to see tools firing.

Run:
    python test_tools.py
"""

import llm


def main() -> None:
    print("Text test — type as if you were a customer. Type 'quit' to exit.\n")

    while True:
        user_text = input("You: ").strip()
        if user_text.lower() in {"quit", "exit"}:
            break
        if not user_text:
            continue

        reply, order_recorded = llm.chat(user_text)
        print(f"Robot: {reply}")

        if order_recorded:
            print("  >>> (order was saved — conversation would now reset)\n")
            llm.reset_conversation()


if __name__ == "__main__":
    main()
