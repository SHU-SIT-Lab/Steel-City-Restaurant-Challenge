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

try:
    from behaviors.database_bridge import RestaurantDatabase, shared_state
except Exception as exc:
    print(f"[TAKE_ORDER] database bridge unavailable ({exc}).")
    RestaurantDatabase = None
    shared_state = None

try:
    from llm.order_taker import OrderTaker
except Exception as exc:
    print(f"[TAKE_ORDER] OrderTaker unavailable ({exc}). Conversation disabled.")
    OrderTaker = None


class TakeOrderBehavior(DeliberativeBehavior):
    def __init__(self) -> None:
        super().__init__(name="take_order")

        self.wait_time = 5.0
        self.order = 5
        self.max_dialogue_turns = 8
        self.ask_timeout = 8.0
        self.max_no_reply = 3

        self._order_taker: Optional[OrderTaker] = None
        self._database: Any = None
        self.speech_to_text: Any = None
        self.text_to_speech: Any = None
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

        for method_name in ("navigate_to", "go_to", "go_to_location", "send_goal", "navigate"):
            method = getattr(navigator, method_name, None)

            if callable(method):
                try:
                    result = method(location_id)
                    return bool(result) if result is not None else True
                except Exception as exc:
                    print(f"[TAKE_ORDER] navigation method {method_name} failed ({exc}).")
                    return False

        print(f"[TAKE_ORDER] no compatible navigation method found for {location_id!r}.")
        return False

    def _get_database(self) -> Any:
        if self._database is not None:
            return self._database

        if RestaurantDatabase is None:
            return None

        try:
            self._database = RestaurantDatabase()
            return self._database
        except Exception as exc:
            print(f"[TAKE_ORDER] could not create RestaurantDatabase ({exc}).")
            return None

    def _get_table_awaiting_order(self) -> Optional[int]:
        table_id = self._get_table_from_shared_state()

        if table_id is not None:
            return table_id

        db = self._get_database()

        if db is not None:
            for method_name in (
                "get_table_awaiting_order",
                "get_waiting_table",
                "get_table_waiting_for_order",
                "find_table_awaiting_order",
                "next_table_awaiting_order",
            ):
                method = getattr(db, method_name, None)

                if callable(method):
                    try:
                        result = method()
                        parsed = self._parse_table_id(result)

                        if parsed is not None:
                            return parsed

                    except Exception as exc:
                        print(f"[TAKE_ORDER] database method {method_name} failed ({exc}).")

        test_table = os.environ.get("TAKE_ORDER_TEST_TABLE")

        if test_table:
            try:
                return int(test_table)
            except ValueError:
                print(f"[TAKE_ORDER] invalid TAKE_ORDER_TEST_TABLE={test_table!r}")

        return None

    def _get_table_from_shared_state(self) -> Optional[int]:
        if shared_state is None:
            return None

        candidate_names = (
            "table_awaiting_order",
            "waiting_order_table",
            "current_table",
            "assigned_table",
        )

        for name in candidate_names:
            try:
                value = getattr(shared_state, name, None)
                parsed = self._parse_table_id(value)

                if parsed is not None:
                    return parsed

            except Exception:
                pass

        if isinstance(shared_state, dict):
            for name in candidate_names:
                parsed = self._parse_table_id(shared_state.get(name))

                if parsed is not None:
                    return parsed

        return None

    def _parse_table_id(self, value: Any) -> Optional[int]:
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            cleaned = value.strip().lower()

            if cleaned.startswith("table_"):
                cleaned = cleaned.replace("table_", "", 1)

            if cleaned.startswith("table "):
                cleaned = cleaned.replace("table ", "", 1)

            if cleaned.isdigit():
                return int(cleaned)

            return None

        if isinstance(value, dict):
            for key in ("table_id", "id", "table", "number"):
                if key in value:
                    parsed = self._parse_table_id(value[key])

                    if parsed is not None:
                        return parsed

        return None

    def _save_order_to_db(self, table_id: int, items: list, notes: str) -> bool:
        db = self._get_database()

        if db is not None:
            for method_name in (
                "save_order",
                "create_order",
                "add_order",
                "record_order",
                "save_order_for_table",
                "set_order_for_table",
            ):
                method = getattr(db, method_name, None)

                if callable(method):
                    try:
                        self._call_save_method(method, table_id, items, notes)
                        print(f"[TAKE_ORDER] saved order for table {table_id}: {items} notes={notes!r}")
                        return True
                    except TypeError:
                        continue
                    except Exception as exc:
                        print(f"[TAKE_ORDER] database save method {method_name} failed ({exc}).")
                        return False

        try:
            import order

            if hasattr(order, "save_order_for_table"):
                order.save_order_for_table(table_id=table_id, items=items, notes=notes)
                print(f"[TAKE_ORDER] saved order locally for table {table_id}: {items} notes={notes!r}")
                return True

        except Exception as exc:
            print(f"[TAKE_ORDER] local order fallback failed ({exc}).")

        print(f"[TAKE_ORDER] no database writer available for table {table_id}: {items} notes={notes!r}")
        return False

    def _call_save_method(self, method: Any, table_id: int, items: list, notes: str) -> Any:
        try:
            return method(table_id=table_id, items=items, notes=notes)
        except TypeError:
            pass

        try:
            return method(table_id, items, notes)
        except TypeError:
            pass

        try:
            return method(table_id=table_id, order={"items": items, "notes": notes})
        except TypeError:
            pass

        return method({"table_id": table_id, "items": items, "notes": notes})
