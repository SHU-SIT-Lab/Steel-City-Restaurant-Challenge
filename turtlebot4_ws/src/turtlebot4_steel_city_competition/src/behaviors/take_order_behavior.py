#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import Any, Optional

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import RestaurantDatabase, shared_state

try:
    from llm.order_taker import OrderTaker
except Exception as exc:
    print(f"[TAKE_ORDER] OrderTaker unavailable ({exc}). Conversation disabled.")
    OrderTaker = None


class TakeOrderBehavior(DeliberativeBehavior):
    """Go to a waiting table, take the order, and record it."""

    def __init__(self) -> None:
        super().__init__(name="take_order")
        self.wait_time = 5.0            # cooldown before this behavior re-runs
        self.order = 5                 # priority weight when a table is waiting
        self.max_dialogue_turns = 8    # safety cap on back-and-forth per order
        self.ask_timeout = 8.0         # seconds to wait for a spoken reply
        self.max_no_reply = 3          # give up after this many silent turns
        self._order_taker: Optional[OrderTaker] = None  
        self.db = RestaurantDatabase()
        

    # ------------------------------------------------------------------ #
    #  Main plan
    # ------------------------------------------------------------------ #
    def plan(self, ctx: Any) -> None:
        # Wrap the whole sequence so a broken step never freezes the robot.
        try:
            # 1. Database: which table needs an order?
            table_id = self._get_table_awaiting_order()
            if table_id is None:
                return
            shared_state(ctx)["current_table_id"] = table_id

            # 2. Navigation (placeholder): go to the table.
            if not self._navigate_to(f"table_{table_id}"):
                return  # couldn't get there — move on, run again later

            # 3 & 4. LLM: greet, ask, and take the order.
            result = self._take_order()
            if result is None:
                self._say("No problem, I'll come back in a little while.")
                return

            # 5. Database: persist the order, assigned to this table.
            self._save_order_to_db(table_id, result.get("items", []), result.get("notes", ""))

        except Exception as exc:
            # Never let one bad turn hang the behavior; log and move on.
            print(f"[TAKE_ORDER] step failed ({exc}); abandoning this attempt.")

    def compute_priority(self) -> float:
        elapsed_time = time.monotonic() - self.last_run_time
        if elapsed_time < self.wait_time:
            self.priority = 0.0
        else:
            # TODO (Database): 1.0 if a table has customers who haven't ordered.
            has_table = self._get_table_awaiting_order() is not None
            self.priority = 1.0 * self.order if has_table else 0.0
        return self.priority

    # ------------------------------------------------------------------ #
    #  Step 3 & 4 — the order-taking conversation
    # ------------------------------------------------------------------ #
    def _take_order(self) -> Optional[dict]:
        """Run the order dialogue via the LLM. Returns {"items", "notes"} or None.

        each `_ask` has a timeout. Too many silent
        replies (customer left / mic dead) ends the attempt instead of looping.
        """
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

            no_reply = 0  # got speech — reset the silence counter
            reply, recorded_order = taker.chat(answer)
            self._say(reply)

            if recorded_order is not None:
                return recorded_order  # {"items": [...], "notes": "..."}

        # Ran out of turns without a confirmed order.
        return None

    def _get_order_taker(self) -> Optional[OrderTaker]:
        """Create the OrderTaker on first use (needs OPENAI_API_KEY)."""
        if self._order_taker is None and OrderTaker is not None:
            try:
                self._order_taker = OrderTaker()
            except Exception as exc:
                print(f"[TAKE_ORDER] LLM unavailable ({exc}).")
                return None
        return self._order_taker

    # ------------------------------------------------------------------ #
    #  Speech I/O — thin clients onto the speech action nodes
    # ------------------------------------------------------------------ #
    def _say(self, text: str) -> None:
        """Speak text through the text_to_speech action node."""
        print(f"[TAKE_ORDER] say: {text!r}")
        try:
            self.text_to_speech.generate_speech(text)
        except Exception as exc:
            print(f"[TAKE_ORDER] TTS unavailable ({exc}); printed only.")

    def _ask(self, prompt: Optional[str] = None, timeout: float = 8.0) -> Optional[str]:
        """Ask a question and get the customer's transcribed reply, or None.

        Request-with-TIMEOUT. On the robot this should be
        a ROS *service* call to the speech_to_text node: speak the prompt, then
        ask for the next finished transcript, waiting at most `timeout` seconds.
        ROS handles the waiting via its executor — we do not spawn threads.

        Expected service-backed method on the node, e.g.:
            return self.speech_to_text.get_next_utterance(timeout)

        Returns None on timeout/no speech so the caller can move on.
        """
        if prompt:
            self._say(prompt)

        getter = getattr(self.speech_to_text, "get_next_utterance", None)
        if callable(getter):
            try:
                return getter(timeout)
            except Exception as exc:
                print(f"[TAKE_ORDER] speech request failed ({exc}).")
                return None

        print("[TAKE_ORDER] (speech service not wired yet) no transcript.")
        return None

    # ------------------------------------------------------------------ #
    #  Navigation (PLACEHOLDER — Navigation team)
    # ------------------------------------------------------------------ #
    def _navigate_to(self, location_id: str) -> bool:
        # TODO (Navigation): replace with the real call, e.g. navigate_to(location_id).
        # Confirmed in meeting: pass a name ("table_3" / "kitchen" / "entrance");
        # for now it returns success immediately (no movement).
        print(f"[TAKE_ORDER] (placeholder) navigate to {location_id!r} ... success")
        return True


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
