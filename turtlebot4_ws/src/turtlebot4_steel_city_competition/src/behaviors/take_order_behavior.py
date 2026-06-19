#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from typing import Any, Optional

from behaviors.behaviors import DeliberativeBehavior

try:
    from behaviors.database_bridge import RestaurantDatabase
except Exception as exc:
    print(f"[TAKE_ORDER] database bridge unavailable ({exc}). DB disabled.")
    RestaurantDatabase = None

try:
    from llm.order_taker import OrderTaker
except Exception as exc:
    print(f"[TAKE_ORDER] OrderTaker unavailable ({exc}). Conversation disabled.")
    OrderTaker = None


class TakeOrderBehavior(DeliberativeBehavior):
    def __init__(self) -> None:
        super().__init__(name="take_order")
        self.wait_time = 5.0            # cooldown before this behavior re-runs
        self.order = 5                 # priority weight when a table is waiting
        self.max_dialogue_turns = 8    # safety cap on back-and-forth per order
        self.ask_timeout = 8.0         # seconds to wait for a spoken reply
        self.max_no_reply = 3          # give up after this many silent turns
        self._order_taker: Optional[OrderTaker] = None
        self._database: Any = None
        # NOTE: self.speech_to_text and self.text_to_speech are wired by the base
        # class to the shared action nodes. Do NOT reset them to None here, or the
        # robot loses its voice/ears. Only navigation is added by this behavior.
        self.navigation: Any = None

    def plan(self, ctx: Any) -> None:
        self._bind_context_interfaces(ctx)

        try:
            table_id = self._get_table_awaiting_order()

            if table_id is None:
                print("[TAKE_ORDER] no table awaiting order.")
                return

            location_id = f"table_{table_id}"

            if not self._navigate_to(location_id):
                print(f"[TAKE_ORDER] could not navigate to {location_id!r}.")
                return
            shared_state(ctx)["current_table_id"] = table_id

            result = self._take_order()

            if result is None:
                self._say("No problem, I'll come back in a little while.")
                return

            saved = self._save_order_to_db(
                table_id=table_id,
                items=result.get("items", []),
                notes=result.get("notes", ""),
            )

            if saved:
                self._say("Thank you. I have sent your order to the kitchen.")
            else:
                self._say("I have taken your order, but I could not save it just now.")

        except Exception as exc:
            print(f"[TAKE_ORDER] step failed ({exc}); abandoning this attempt.")

    def compute_priority(self) -> float:
        elapsed_time = time.monotonic() - self.last_run_time

        if elapsed_time < self.wait_time:
            self.priority = 0.0
            return self.priority

        table_id = self._get_table_awaiting_order()
        self.priority = float(self.order) if table_id is not None else 0.0

        return self.priority

    def _bind_context_interfaces(self, ctx: Any) -> None:
        if ctx is None:
            return

        for name in ("speech_to_text", "stt", "speech"):
            value = getattr(ctx, name, None)
            if value is not None:
                self.speech_to_text = value
                break

        for name in ("text_to_speech", "tts"):
            value = getattr(ctx, name, None)
            if value is not None:
                self.text_to_speech = value
                break

        if isinstance(ctx, dict):
            for name in ("navigation", "navigator", "nav"):
                value = ctx.get(name)
                if value is not None:
                    self.navigation = value
                    break
        else:
            for name in ("navigation", "navigator", "nav"):
                value = getattr(ctx, name, None)
                if value is not None:
                    self.navigation = value
                    break

        for name in ("database", "db", "restaurant_database"):
            value = getattr(ctx, name, None)
            if value is not None:
                self._database = value
                break

    def _take_order(self) -> Optional[dict]:
        taker = self._get_order_taker()

        if taker is None:
            return None

        taker.reset()
        self._say("Hello! I'm ServerBot. What would you like to order?")

        no_reply = 0

        for _ in range(self.max_dialogue_turns):
            answer = self._ask(timeout=self.ask_timeout)

            if not answer:
                no_reply += 1

                if no_reply >= self.max_no_reply:
                    print("[TAKE_ORDER] no reply after several tries; giving up for now.")
                    return None

                self._say("Sorry, I didn't catch that. Could you repeat, please?")
                continue

            no_reply = 0

            reply, recorded_order = taker.chat(answer)
            self._say(reply)

            if recorded_order is not None:
                return recorded_order

        return None

    def _get_order_taker(self) -> Optional[OrderTaker]:
        if self._order_taker is None and OrderTaker is not None:
            try:
                self._order_taker = OrderTaker()
            except Exception as exc:
                print(f"[TAKE_ORDER] LLM unavailable ({exc}).")
                return None

        return self._order_taker

    def _say(self, text: str) -> None:
        print(f"[TAKE_ORDER] say: {text!r}")

        speaker = self.text_to_speech

        if speaker is None:
            print("[TAKE_ORDER] text_to_speech interface not wired; printed only.")
            return

        for method_name in ("generate_speech", "generate_and_publish_speech", "speak"):
            method = getattr(speaker, method_name, None)

            if callable(method):
                try:
                    method(text)
                    return
                except Exception as exc:
                    print(f"[TAKE_ORDER] TTS method {method_name} failed ({exc}).")
                    return

        print("[TAKE_ORDER] no compatible TTS method found; printed only.")

    def _ask(self, prompt: Optional[str] = None, timeout: float = 8.0) -> Optional[str]:
        if prompt:
            self._say(prompt)

        listener = self.speech_to_text

        if listener is None:
            print("[TAKE_ORDER] speech_to_text interface not wired.")
            return None

        getter = getattr(listener, "get_next_utterance", None)

        if callable(getter):
            try:
                return getter(timeout)
            except Exception as exc:
                print(f"[TAKE_ORDER] speech request failed ({exc}).")
                return None

        print("[TAKE_ORDER] speech_to_text has no get_next_utterance(timeout).")
        return None

    def _navigate_to(self, location_id: str) -> bool:
        navigator = self.navigation

        if navigator is None:
            print(f"[TAKE_ORDER] navigation not wired; pretending navigation to {location_id!r} succeeded.")
            return True

    # ------------------------------------------------------------------ #
    #  Database (STUB — Database team)
    # ------------------------------------------------------------------ #
    def _get_table_awaiting_order(self) -> Optional[int]:
        """Return first occupied table with no order yet, or None."""
        try:
            table_id = self.db.find_table_needing_order()
            if table_id is None:
                print("[TAKE_ORDER] DB: no table needs an order right now.")
            else:
                print(f"[TAKE_ORDER] DB: table {table_id} needs an order.")
            return table_id
        except Exception as exc:
            print(f"[TAKE_ORDER] DB read failed ({exc}).")
            return None

    def _save_order_to_db(self, table_id: int, items: list, notes: str) -> bool:
        """Save confirmed order to Firestore for this table."""
        try:
            clean_items = [str(item).strip() for item in items if str(item).strip()]
            clean_notes = str(notes or "").strip()
            if not clean_items:
                print(f"[TAKE_ORDER] DB: empty order for table {table_id}; not saving.")
                return False
            self.db.save_order(table_id, items=clean_items, notes=clean_notes)
            print(
                f"[TAKE_ORDER] DB saved for table {table_id}: "
                f"items={clean_items} notes={clean_notes!r}"
            )
            return True
        except Exception as exc:
            print(f"[TAKE_ORDER] DB save failed for table {table_id} ({exc}).")
            return False
