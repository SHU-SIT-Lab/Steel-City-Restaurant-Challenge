"""LLM integration using OpenAI API — returns (spoken_reply, order_dict)."""

import json
import openai
import config

_client: openai.OpenAI | None = None
_history: list[dict] = []


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


def chat(user_text: str) -> tuple[str, dict | None]:
    """Send user_text to the LLM.

    Returns:
        (reply_text, order_dict)  — order_dict is None until items are mentioned,
        and has confirmed=True once the customer says yes.
    """
    _history.append({"role": "user", "content": user_text})

    response = _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        max_tokens=config.MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": config.SYSTEM_PROMPT}] + _history,
    )

    raw = response.choices[0].message.content.strip()
    _history.append({"role": "assistant", "content": raw})

    try:
        data = json.loads(raw)
        reply = data.get("reply", "")
        order = data.get("order", None)
    except json.JSONDecodeError:
        print(f"[LLM] Warning: could not parse JSON — {raw!r}")
        reply = raw
        order = None

    print(f"[LLM] Reply : {reply!r}")
    if order:
        print(f"[LLM] Order : {order}")

    return reply, order


def reset_conversation() -> None:
    _history.clear()
    print("[LLM] Conversation reset.")
