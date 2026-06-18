"""LLM with OpenAI tool calling for the restaurant waiter.

The model can call tools (navigate_to, record_order) defined in tools.py.
`chat()` runs an agentic loop: it keeps calling the model and executing any
tools the model asks for, until the model produces a final spoken reply.
"""

import json
import openai

import config
import tools

_client: openai.OpenAI | None = None
_history: list[dict] = []

# Safety cap so a misbehaving model can't loop forever calling tools.
MAX_TOOL_ROUNDS = 5


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set.\n"
                "In PowerShell run:  $env:OPENAI_API_KEY = 'sk-...your-key...'\n"
                "Then relaunch the script."
            )
        _client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def chat(user_text: str) -> tuple[str, bool]:
    """Process one customer turn.

    The model may call tools (navigation, order recording) before replying.

    Returns:
        (reply_text, order_recorded)
        - reply_text:    what the robot should say out loud.
        - order_recorded: True if an order was saved during this turn
                          (so the caller can end/reset the conversation).
    """
    _history.append({"role": "user", "content": user_text})
    order_recorded = False

    for _ in range(MAX_TOOL_ROUNDS):
        response = _get_client().chat.completions.create(
            model=config.OPENAI_MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[{"role": "system", "content": config.SYSTEM_PROMPT}] + _history,
            tools=tools.TOOLS,
        )
        msg = response.choices[0].message

        # Record the assistant turn (may include tool calls) in history.
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
        _history.append(assistant_msg)

        # No tool calls -> this is the final spoken reply.
        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            print(f"[LLM] Reply : {reply!r}")
            return reply, order_recorded

        # Execute each requested tool and feed the result back to the model.
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            print(f"[LLM] Tool call : {name}({args})")
            result = tools.execute_tool(name, args)
            print(f"[LLM] Tool result: {result}")

            if name == "record_order" and result.get("success"):
                order_recorded = True

            _history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })
        # Loop again so the model can respond to the tool results.

    # Safety fallback if the model never stops calling tools.
    print("[LLM] Warning: hit MAX_TOOL_ROUNDS without a final reply.")
    return "Sorry, let me try that again.", order_recorded


def reset_conversation() -> None:
    _history.clear()
    print("[LLM] Conversation reset.")