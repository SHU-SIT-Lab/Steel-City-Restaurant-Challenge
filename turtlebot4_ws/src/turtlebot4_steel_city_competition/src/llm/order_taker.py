"""Order-taking brain — self-contained.

This is the LLM conversation logic. It turns customer text into a confirmed
restaurant order using OpenAI tool calling.

Example:
    taker = OrderTaker()
    taker.reset()
    reply, order = taker.chat("I'd like Menu Two please")
    reply, order = taker.chat("yes that's right")

When the customer confirms, the model calls the `record_order` tool and `chat`
returns the structured order. The caller, for example TakeOrderBehavior,
decides what to do with the order: save to database, navigate, deliver, etc.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[5]
DATABASE_DIR = REPO_ROOT / "scripts" / "database"
if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))

try:
    from menu_catalog import menu_prompt_text
except ImportError:
    menu_prompt_text = lambda: (  # noqa: E731
        "Customers choose one set menu: Menu One through Menu Five."
    )

MODEL = "gpt-4o-mini"
MAX_TOKENS = 300
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = f"""\
You are ServerBot, a friendly and efficient robot waiter in a restaurant.

{menu_prompt_text()}

Your task:
1. Help the customer choose one set menu (Menu One through Menu Five).
2. Repeat the chosen menu and what it includes.
3. Ask the customer to confirm.
4. Only after the customer clearly confirms, call the record_order tool.
5. Thank the customer warmly after the order is recorded.

Rules:
- Keep replies short because they will be spoken aloud.
- Record menu ids in items, e.g. ["menu_two"] or ["Menu Two"].
- Customers choose one menu unless they clearly want a second set menu.
- Optional condiments go in notes, not in items.
- Do not call record_order until the customer explicitly confirms.
- If there are no notes, use an empty string.
"""

RECORD_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "record_order",
        "description": (
            "Record the customer's confirmed set-menu order. "
            "Call this only after the customer has explicitly confirmed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Confirmed menu ids or names, e.g. ['menu_two'] or ['Menu Two']."
                    ),
                },
                "notes": {
                    "type": "string",
                    "description": (
                        "Condiments, dietary needs, allergies, or special requests. "
                        "Empty string if none."
                    ),
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
        self.history: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear conversation history before each new customer."""
        self.history = []

    def chat(self, user_text: str) -> tuple[str, dict[str, Any] | None]:
        """Run one conversation turn.

        Returns:
            (reply_text, order)

        order is None until the customer confirms.
        Once confirmed, order is:
            {"items": [...], "notes": "..."}
        """
        self.history.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        recorded: dict[str, Any] | None = None

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    }
                ]
                + self.history,
                tools=[RECORD_ORDER_TOOL],
                tool_choice="auto",
            )

            msg = response.choices[0].message

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content,
            }

            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in msg.tool_calls
                ]

            self.history.append(assistant_msg)

            if not msg.tool_calls:
                return (msg.content or "").strip(), recorded

            for tool_call in msg.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if tool_call.function.name == "record_order":
                    items = args.get("items", [])
                    notes = args.get("notes", "")

                    if not isinstance(items, list):
                        items = [str(items)]

                    items = [str(item).strip() for item in items if str(item).strip()]
                    notes = str(notes).strip()

                    recorded = {
                        "items": items,
                        "notes": notes,
                    }

                    result = {
                        "success": True,
                        "recorded_order": recorded,
                    }

                else:
                    result = {
                        "success": False,
                        "error": f"unknown tool: {tool_call.function.name}",
                    }

                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

        return "Sorry, could you repeat that, please?", recorded
