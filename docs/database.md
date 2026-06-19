# Database

Firestore-backed shared state for table status, orders, and entrance queue data.

## Collections

| Collection | Document ID | Purpose |
|------------|-------------|---------|
| `tables` | `0`, `1`, ... | Table status, order items, delivery flags |
| `restaurant_state` | `current` | Customers waiting at entrance (collaborator robots) |

## Order lifecycle

| Step | Behavior | Repository call | Firestore change |
|------|----------|-----------------|------------------|
| Seat customer | `introduce_table` | `assign_table()` | `status=occupied`, `has_ordered=false` |
| Take order | `take_order` | `save_order()` | `has_ordered=true`, `order_ready=false` |
| Mark ready | `mark_order_ready` | `mark_order_ready()` | `order_ready=true` |
| Deliver | `collect_order` | `mark_order_delivered()` | table reset to empty |

There is no separate kitchen team in this project. `mark_order_ready` behavior
simulates the kitchen step by promoting pending orders to ready in Firestore so
`collect_order` can pick them up.

## Table ID vs waypoint names

Firestore table documents use **zero-based** ids: `0`, `1`, …, `N-1`.

Navigation waypoints in `configs/waypoints.yaml` use **one-based** names:
`table_1`, `table_2`, …, `table_N`.

| Firestore `table_id` | Waypoint name |
|----------------------|---------------|
| `0` | `table_1` |
| `1` | `table_2` |
| `2` | `table_3` |
| … | … |

Use `table_id_to_location(table_id)` from `behaviors/database_bridge.py` — do
not hardcode the offset in each behavior.

Fixed location ids (not tied to a table document):

| Constant | Waypoint key |
|----------|--------------|
| `ENTRANCE_LOCATION` | `entrance` |
| `BARISTA_LOCATION` | `barista` |

## Navigation handoff (database team → navigation team)

Database behaviors do **not** call Nav2. They publish targets on the behavior
context so the navigation module can read them and call
`RestaurantNavigator.navigate_to(location_id)`.

### `shared_state` keys

| Key | Set by | Meaning |
|-----|--------|---------|
| `target_location` | database behaviors | Current nav goal: `entrance`, `barista`, or `table_N` |
| `next_target_location` | multi-leg behaviors | Second leg after the first completes (optional) |
| `current_table_id` | database behaviors | Firestore table id (`0`–`N-1`) for the active table |
| `assigned_table_id` | `introduce_table` | Table just assigned to a waiting party |
| `order_ready_table_id` | `mark_order_ready` | Table whose order was marked ready |
| `order_delivered` | speech / nav (later) | When `true`, `collect_order` calls `mark_order_delivered()` |

Use `set_navigation_target(ctx, location, table_id=..., next_location=...)`
from `database_bridge.py` instead of writing these keys manually.

### Which Firestore query triggers which navigation

| Behavior | Repository query | `target_location` | `next_target_location` |
|----------|------------------|-------------------|------------------------|
| `check_customer` | (always runs on timer) | `entrance` | — |
| `update_customer_number` | `customers_detected_at_entrance()` | `entrance` | — |
| `introduce_table` | `should_guide_customer_to_table()` | `entrance` | `table_{id+1}` |
| `take_order` | `find_table_needing_order()` | `table_{id+1}` | — |
| `mark_order_ready` | `find_table_with_pending_order()` | *(none — DB only)* | — |
| `collect_order` | `find_table_with_ready_order()` | `barista` | `table_{id+1}` |
| `check_empty_table` | loops `list_table_ids()` | each `table_{id+1}` in turn | — |

### Navigation team responsibilities

1. Wire `RestaurantNavigator` into `turtlebot4_run.py` as `ctx["navigation"]`.
2. Maintain real poses in `configs/waypoints.yaml`.
3. Read `ctx["shared_state"]["target_location"]` (and `next_target_location`
   for two-leg behaviors) and call `navigate_to()`.
4. After a leg completes, advance to `next_target_location` if present.
5. Set `order_delivered=true` in `shared_state` when the customer has the order
   so `collect_order` can reset the table in Firestore.

## Setup

1. Add your Firebase service account JSON to `configs/security_key.json`.
2. Install dependencies: `conda activate steel-city-restaurant` then `pip install firebase-admin pyyaml`.
3. Seed default documents: `python scripts/database/seed.py`.
4. Verify connection and full order loop: `python scripts/database/test_connection.py`.
5. Verify waypoint mapping (no robot): `python scripts/database/test_navigation_targets.py`.

### Firestore console vs launching the robot stack

These are **two different things**:

| What | Where | Purpose |
|------|-------|---------|
| **Firestore console** | [Firebase web UI](https://console.firebase.google.com) | View/edit `tables` and `restaurant_state` documents |
| **Competition stack** | Docker container + ROS 2 on your PC / robot | Runs behaviors that read/write Firestore and drive the robot |

You **cannot** launch the robot from the Firestore console. The console only shows database state. To run behaviors, use the launch steps below.

### Launch the competition stack

**On your laptop (inside Docker):**

```bash
cd turtlebot4_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

**On the TurtleBot4 (before Docker connects):**

```bash
ros2 launch turtlebot4_bringup robot.launch.py
ros2 launch turtlebot4_navigation localization.launch.py map:=your_map.yaml
ros2 launch turtlebot4_navigation nav2.launch.py
```

See the main [README](../README.md) for Docker setup and Create 3 discovery configuration.

**Database-only tests (no robot):** run from the repo root with conda active:

```bash
cd scripts/database
python seed.py
python test_connection.py
python test_navigation_targets.py
python reset_demo.py
```

### Red flags in Firestore and how to fix them

| Symptom | Cause | Fix |
|---------|-------|-----|
| `introduce_table` never runs | `customers_waiting` is `0` | Run `python scripts/database/reset_demo.py` or set `customers_waiting` to `1` in console |
| Table stuck `occupied` forever | Delivery never completed | Nav/speech must set `order_delivered=true` in shared_state, or run `reset_demo.py` |
| `has_ordered: true` but robot keeps taking orders | Stale doc from manual edits | Run `python scripts/database/seed.py --reset` or `reset_demo.py` |
| Missing `tables` docs `0`–`4` | Never seeded | Run `python scripts/database/seed.py` |
| `order_ready: true` but nothing collects | Robot stack not running, or nav not wired | Launch stack; nav team reads `target_location` |
| Re-running `seed.py` does not clear old orders | Seed uses merge by default | Use `seed.py --reset` or `reset_demo.py` |

**Quick clean slate for testing the full flow:**

```bash
cd scripts/database
python reset_demo.py
```

This clears all tables to empty and sets `customers_waiting=1`, `customers_detected_at_entrance=true`.

## Usage from behaviors

```python
from behaviors.database_bridge import (
    RestaurantDatabase,
    set_navigation_target,
    table_id_to_location,
)

db = RestaurantDatabase()
table_id = db.find_table_needing_order()
if table_id is not None:
    set_navigation_target(ctx, table_id_to_location(table_id), table_id=table_id)
    db.save_order(table_id, items=["coffee", "sandwich"], notes="no dairy")

pending = db.find_table_with_pending_order()
if pending is not None:
    db.mark_order_ready(pending)
```

See `scripts/database/repository.py` for the full Firestore API.
