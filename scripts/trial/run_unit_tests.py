#!/usr/bin/env python3
"""Offline unit tests for behavior navigation targets and shared helpers.

Run before competition demo (no robot required):
    python3 scripts/trial/run_unit_tests.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
BEHAVIORS_SRC = (
    REPO_ROOT
    / "turtlebot4_ws"
    / "src"
    / "turtlebot4_steel_city_competition"
    / "src"
)
sys.path.insert(0, str(BEHAVIORS_SRC))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "database"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "vision"))

from behaviors.database_bridge import (  # noqa: E402
    BARISTA_LOCATION,
    ENTRANCE_LOCATION,
    get_bool,
    get_int,
    set_navigation_target,
    shared_state,
    table_empty_status,
    table_id_to_location,
)
from behaviors.speech_utils import parse_party_size  # noqa: E402
from models import TableStatus  # noqa: E402


def make_ctx() -> dict:
    return {"shared_state": {}}


class DatabaseBridgeTests(unittest.TestCase):
    def test_table_id_to_location(self) -> None:
        self.assertEqual(table_id_to_location(0), "table_1")
        self.assertEqual(table_id_to_location(4), "table_5")

    def test_shared_state_from_dict(self) -> None:
        ctx = make_ctx()
        state = shared_state(ctx)
        self.assertIs(state, ctx["shared_state"])

    def test_shared_state_missing(self) -> None:
        self.assertEqual(shared_state({}), {})
        self.assertEqual(shared_state(None), {})

    def test_set_navigation_target_entrance(self) -> None:
        ctx = make_ctx()
        set_navigation_target(ctx, ENTRANCE_LOCATION)
        state = shared_state(ctx)
        self.assertEqual(state["target_location"], ENTRANCE_LOCATION)
        self.assertNotIn("current_table_id", state)
        self.assertNotIn("next_target_location", state)

    def test_set_navigation_target_table(self) -> None:
        ctx = make_ctx()
        set_navigation_target(ctx, "table_3", table_id=2)
        state = shared_state(ctx)
        self.assertEqual(state["target_location"], "table_3")
        self.assertEqual(state["current_table_id"], 2)

    def test_set_navigation_target_barista_with_next(self) -> None:
        ctx = make_ctx()
        set_navigation_target(
            ctx,
            BARISTA_LOCATION,
            table_id=1,
            next_location="table_2",
        )
        state = shared_state(ctx)
        self.assertEqual(state["target_location"], BARISTA_LOCATION)
        self.assertEqual(state["delivery_table_id"], 1)
        self.assertEqual(state["next_target_location"], "table_2")
        self.assertNotIn("current_table_id", state)

    def test_get_bool(self) -> None:
        self.assertTrue(get_bool("yes"))
        self.assertTrue(get_bool("ready"))
        self.assertFalse(get_bool("no"))
        self.assertFalse(get_bool(None, default=False))
        self.assertTrue(get_bool(None, default=True))

    def test_get_int(self) -> None:
        self.assertEqual(get_int("party of 4"), 4)
        self.assertEqual(get_int(3), 3)
        self.assertEqual(get_int(None, default=1), 1)

    def test_table_empty_status(self) -> None:
        self.assertEqual(table_empty_status("empty"), TableStatus.EMPTY)
        self.assertEqual(table_empty_status("occupied"), TableStatus.OCCUPIED)
        self.assertEqual(table_empty_status(True), TableStatus.EMPTY)


class SpeechUtilsTests(unittest.TestCase):
    def test_parse_party_size_digits(self) -> None:
        self.assertEqual(parse_party_size("4"), 4)
        self.assertEqual(parse_party_size("We are 3 people"), 3)

    def test_parse_party_size_words(self) -> None:
        self.assertEqual(parse_party_size("two"), 2)
        self.assertEqual(parse_party_size(None, default=1), 1)


class OrderVerificationTests(unittest.TestCase):
    def test_normalize_menu_reference(self) -> None:
        from menu_catalog import normalize_menu_reference

        self.assertEqual(normalize_menu_reference("Menu One"), "menu_one")
        self.assertEqual(normalize_menu_reference("menu 2"), "menu_two")
        self.assertEqual(normalize_menu_reference("Menu Five"), "menu_five")

    def test_menu_bundle_expands_to_items(self) -> None:
        from order_verification import order_items_to_required_counts

        required = order_items_to_required_counts(["menu_one"])
        self.assertEqual(dict(required), {"sandwich": 1, "slice_of_pie": 1})

        required_name = order_items_to_required_counts(["Menu Two"])
        self.assertEqual(
            dict(required_name),
            {"hot_dog": 1, "crisps": 1, "chocolate_chip_cookie": 1},
        )

    def test_verify_correct_order(self) -> None:
        from order_verification import verify_order

        result = verify_order(
            ["Menu Three"],
            {"waffle": 1, "bacon": 1},
        )
        self.assertTrue(result.is_correct)
        self.assertEqual(dict(result.missing), {})
        self.assertEqual(dict(result.extra), {})

    def test_verify_missing_and_extra(self) -> None:
        from order_verification import verify_order

        result = verify_order(
            ["menu_one"],
            {"sandwich": 1, "hot_dog": 1},
        )
        self.assertFalse(result.is_correct)
        self.assertEqual(dict(result.missing), {"slice_of_pie": 1})
        self.assertEqual(dict(result.extra), {"hot_dog": 1})


class BehaviorNavigationTests(unittest.TestCase):
    def test_check_customer_sets_entrance(self, mock_db_cls: MagicMock) -> None:
        from behaviors.check_customer_behavior import CheckCustomerBehavior

        mock_db_cls.return_value = MagicMock()
        ctx = make_ctx()
        ctx["shared_state"]["customer_present"] = True

        CheckCustomerBehavior().run(ctx)

        self.assertEqual(shared_state(ctx)["target_location"], ENTRANCE_LOCATION)

    @patch("behaviors.update_customer_number_behavior.RestaurantDatabase")
    def test_check_customer_number_sets_entrance(self, mock_db_cls: MagicMock) -> None:
        from behaviors.update_customer_number_behavior import CheckCustomerNumberBehavior

        mock_db = MagicMock()
        mock_db.customers_detected_at_entrance.return_value = False
        mock_db_cls.return_value = mock_db

        ctx = make_ctx()
        CheckCustomerNumberBehavior().run(ctx)

        self.assertEqual(shared_state(ctx)["target_location"], ENTRANCE_LOCATION)

    @patch("behaviors.introduce_table_behavior.RestaurantDatabase")
    def test_introduce_table_entrance_then_table(self, mock_db_cls: MagicMock) -> None:
        from behaviors.introduce_table_behavior import IntroduceTableBehavior

        mock_db = MagicMock()
        mock_db.should_guide_customer_to_table.return_value = True
        mock_db.find_empty_table.return_value = 2
        mock_db_cls.return_value = mock_db

        ctx = make_ctx()
        IntroduceTableBehavior().run(ctx)

        state = shared_state(ctx)
        self.assertEqual(state["target_location"], ENTRANCE_LOCATION)
        self.assertEqual(state["next_target_location"], "table_3")
        self.assertEqual(state["assigned_table_id"], 2)

    @patch("behaviors.take_order_behavior.RestaurantDatabase")
    def test_take_order_sets_table_target(self, mock_db_cls: MagicMock) -> None:
        from behaviors.take_order_behavior import TakeOrderBehavior

        mock_db = MagicMock()
        mock_db.find_table_needing_order.return_value = 0
        mock_db_cls.return_value = mock_db

        behavior = TakeOrderBehavior()
        behavior._get_table_awaiting_order = MagicMock(return_value=0)  # type: ignore[method-assign]
        behavior._take_order = MagicMock(return_value=None)  # type: ignore[method-assign]

        ctx = make_ctx()
        behavior.run(ctx)

        state = shared_state(ctx)
        self.assertEqual(state["target_location"], "table_1")
        self.assertEqual(state["current_table_id"], 0)

    @patch("behaviors.collect_order_behavior.RestaurantDatabase")
    def test_collect_order_first_leg_barista(self, mock_db_cls: MagicMock) -> None:
        from behaviors.collect_order_behavior import CollectOrderBehavior

        mock_db = MagicMock()
        mock_db.find_table_with_ready_order.return_value = 1
        mock_db_cls.return_value = mock_db

        ctx = make_ctx()
        CollectOrderBehavior().run(ctx)

        state = shared_state(ctx)
        self.assertEqual(state["target_location"], BARISTA_LOCATION)
        self.assertEqual(state["next_target_location"], "table_2")
        self.assertEqual(state["delivery_table_id"], 1)

    @patch("behaviors.check_empty_table_behavior.RestaurantDatabase")
    def test_check_empty_table_sets_table_target(self, mock_db_cls: MagicMock) -> None:
        from behaviors.check_empty_table_behavior import CheckEmptyTableBehavior

        mock_db_cls.return_value = MagicMock()
        ctx = make_ctx()
        ctx["shared_state"]["current_table_id"] = 3

        CheckEmptyTableBehavior().run(ctx)

        self.assertEqual(shared_state(ctx)["target_location"], "table_4")


class WaypointValidationTests(unittest.TestCase):
    def test_waypoints_yaml_has_required_keys(self) -> None:
        import yaml

        waypoints = REPO_ROOT / "configs" / "waypoints.yaml"
        data = yaml.safe_load(waypoints.read_text())
        required = (
            "entrance",
            "barista",
            "table_1",
            "table_2",
            "table_3",
            "table_4",
            "table_5",
            "docking_station",
        )
        missing = [key for key in required if key not in data]
        self.assertEqual(missing, [], f"missing waypoint keys: {missing}")


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(DatabaseBridgeTests))
    suite.addTests(loader.loadTestsFromTestCase(SpeechUtilsTests))
    suite.addTests(loader.loadTestsFromTestCase(OrderVerificationTests))
    suite.addTests(loader.loadTestsFromTestCase(BehaviorNavigationTests))
    suite.addTests(loader.loadTestsFromTestCase(WaypointValidationTests))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("\nAll unit tests passed.")
        return 0

    print(f"\n{len(result.failures)} failure(s), {len(result.errors)} error(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
