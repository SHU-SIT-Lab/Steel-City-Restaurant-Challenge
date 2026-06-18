"""Order-taking brain — self-contained

This is the LLM conversation logic. It only turns customer text into a confirmed order using
OpenAI tool calling.

    taker = OrderTaker()
    taker.reset()
    reply, order = taker.chat("I'd like a burger and a coke")   # -> (text, None)
    reply, order = taker.chat("yes that's right")                # -> (text, {"items": [...], "notes": ...})

When the customer confirms, the model calls the `record_order` tool and `chat`
returns the structured order. The caller (e.g. the take-order behavior) decides
what to do with it — navigate, save to the database, etc.
"""

import json
import os

from openai import OpenAI

MODEL = "gpt-4o-mini"
MAX_TOKENS = 300
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """\
You are ServerBot, a friendly and efficient robot waiter in a restaurant.

Take the customer's food and drink order:
1. Ask what they would like.
2. Repeat the order back and ask them to confirm.
3. Once they confirm, call the record_order tool with the items.
4. Thank them warmly.

Everything you say is spoken aloud, so keep replies SHORT and natural —
one or two sentences. Be warm, clear, and professional.
"""

RECORD_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "record_order",
        "description": (
            "Save the customer's confirmed food and drink order. "
            "Call this ONLY after the customer has explicitly confirmed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The ordered items, e.g. ['burger', 'coke'].",
                },
                "notes": {
                    "type": "string",
                    "description": "Dietary needs or special requests. Empty string if none.",
                },
            },
            "required": ["items"],
        },
    },
}


class OrderTaker:
    """Holds one customer's conversation and extracts the confirmed order."""

    def __init__(self, api_key: str | None = None, model: str = MODEL) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Set it in the environment before running."
            )
        self.client = OpenAI(api_key=key)
        self.model = model
        self.history: list[dict] = []

    def reset(self) -> None:
        """Clear history — call before each new customer."""
        self.history = []

    def chat(self, user_text: str) -> tuple[str, dict | None]:
        """One conversation turn.

        Returns (reply_text, order) where order is None until the customer
        confirms, then {"items": [...], "notes": "..."}.
        """
        self.history.append({"role": "user", "content": user_text})
        recorded: dict | None = None

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
                tools=[RECORD_ORDER_TOOL],
            )
            msg = response.choices[0].message

            assistant_msg: dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            self.history.append(assistant_msg)

            if not msg.tool_calls:
                return (msg.content or "").strip(), recorded

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if tc.function.name == "record_order":
                    recorded = {
                        "items": args.get("items", []),
                        "notes": args.get("notes", ""),
                    }
                    result = {"success": True}
                else:
                    result = {"success": False, "error": f"unknown tool: {tc.function.name}"}

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        return "Sorry, could you repeat that, please?", recorded
