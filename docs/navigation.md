# Navigation

Competition navigation uses the **navigation bridge** (`navigation_server.py`) and `RestaurantNavigator` (TurtleBot4 Navigator + Nav2) with named poses in [`configs/waypoints.yaml`](../configs/waypoints.yaml).

For full setup steps, GUI usage, and troubleshooting, see the local operator guide [`docs/navigation_waypoints_guide.md`](navigation_waypoints_guide.md) (gitignored — create it locally from the template in the repo or copy from a teammate).

## Prerequisites

On the **TurtleBot4 Raspberry Pi**:

1. Robot bringup: `ros2 launch turtlebot4_bringup robot.launch.py`
2. Localization: `ros2 launch turtlebot4_navigation localization.launch.py map:=<your_map>.yaml`
3. Nav2: `ros2 launch turtlebot4_navigation nav2.launch.py`

On the **dev machine / Docker container**, discovery must point at the robot RPi (handled automatically by `./docker/run_container.sh`).

## Waypoints

Edit [`configs/waypoints.yaml`](../configs/waypoints.yaml) after mapping the arena. Keys used by behaviors:

| Key               | Used for                    |
| ----------------- | --------------------------- |
| `entrance`        | Customer check / queue      |
| `barista`         | Order pickup                |
| `table_1`…`table_5` | Table service            |
| `docking_station` | Dock approach pose + dock   |

Each entry has `x`, `y`, `yaw` in the **map** frame.

Use `scripts/helper/waypoint_recorder.py` to record poses interactively (see the local guide above).

## Navigation service

The bridge exposes:

- **Service:** `/navigation/navigate_to_waypoint`
- **Type:** `turtlebot4_steel_city_competition/srv/NavigateToWaypoint`
- **Request:** `destination` (waypoint name from YAML)
- **Response:** `success`, `message`

Launch the server:

```bash
ros2 launch turtlebot4_steel_city_competition navigation_server.launch.py
```

Test:

```bash
ros2 service call /navigation/navigate_to_waypoint \
  turtlebot4_steel_city_competition/srv/NavigateToWaypoint \
  "{destination: 'table_1'}"
```

When `destination` is `docking_station`, the robot navigates to the approach pose and then docks.

## Navigating from another script

When your code runs inside the competition stack, navigation is already wired. You do not call Nav2 or TurtleBot4 APIs directly — you call the shared navigation object, which forwards the request to `/navigation/navigate_to_waypoint`.

### How it is wired

[`turtlebot4_run.py`](../turtlebot4_ws/src/turtlebot4_steel_city_competition/src/turtlebot4_run.py) creates a `NavigationClient` and places it in the behavior context:

```python
coordinator.ctx["navigation"] = navigator
```

[`steel_city.launch.py`](../turtlebot4_ws/src/turtlebot4_steel_city_competition/launch/steel_city.launch.py) starts both the navigation server and the behavior coordinator, so behaviors can navigate as long as Nav2 is active on the robot.

### Pattern for competition behaviors

Follow the same approach as [`take_order_behavior.py`](../turtlebot4_ws/src/turtlebot4_steel_city_competition/src/behaviors/take_order_behavior.py):

1. Read `navigation` from `ctx` (a dict passed into `plan()`).
2. Call `navigate_to("<waypoint_name>")` with a key from [`configs/waypoints.yaml`](../configs/waypoints.yaml).
3. Check the returned `bool` before continuing the rest of the behavior.

### Example: `check_customer_behavior.py` — TODO 1

[`check_customer_behavior.py`](../turtlebot4_ws/src/turtlebot4_steel_city_competition/src/behaviors/check_customer_behavior.py) has this placeholder:

```python
# TODO 1: Navigation
# Move robot to entrance.
```

To implement it, bind navigation from `ctx` and drive to the `entrance` waypoint:

```python
def plan(self, ctx: Any) -> None:
    navigation = ctx.get("navigation") if isinstance(ctx, dict) else None

    if navigation is None:
        print("[CHECK_CUSTOMER] navigation not wired; skipping move to entrance.")
        return

    if not navigation.navigate_to("entrance"):
        print("[CHECK_CUSTOMER] could not navigate to entrance.")
        return

    # TODO 2: Vision — check camera for new customers.
    # TODO 3: Database — update if a new customer is detected.
    ...
```

`navigate_to("entrance")` blocks until the robot reaches the pose or navigation fails. On success it returns `True`; on failure (unknown waypoint, timeout, Nav2 error) it returns `False`.

Other aliases work too: `go_to()`, `go_to_location()`, `send_goal()`, and `navigate()`.

### Waypoint names to use

| Task | Typical `destination` |
|------|------------------------|
| Check customers at the door | `entrance` |
| Pick up an order | `barista` |
| Serve a table | `table_1` … `table_5` |
| Return to charger | `docking_station` |

### Standalone scripts (outside the behavior stack)

If your script is not launched via `turtlebot4_run.py`, call the ROS service directly. The navigation server must be running first.

**Python (blocking):**

```python
import rclpy
from rclpy.node import Node
from turtlebot4_steel_city_competition.srv import NavigateToWaypoint

rclpy.init()
node = Node("my_script_nav_client")
client = node.create_client(NavigateToWaypoint, "/navigation/navigate_to_waypoint")
client.wait_for_service()

request = NavigateToWaypoint.Request()
request.destination = "entrance"
future = client.call_async(request)
rclpy.spin_until_future_complete(node, future)
response = future.result()
print(response.success, response.message)
```

**Shell:**

```bash
ros2 service call /navigation/navigate_to_waypoint \
  turtlebot4_steel_city_competition/srv/NavigateToWaypoint \
  "{destination: 'entrance'}"
```

[`scripts/speech/tools.py`](../scripts/speech/tools.py) uses the same service pattern for LLM-driven `navigate_to(destination)` calls.

## Mapping

From Docker (sync SLAM on PC recommended):

```bash
ros2 launch turtlebot4_navigation slam.launch.py
# Drive the robot, then save:
ros2 run nav2_map_server map_saver_cli -f restaurant_map
```

## Competition stack

Behaviors in `turtlebot4_run.py` use `NavigationClient`, which calls the navigation service. Launch the full stack (navigation server + behaviors):

```bash
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

Or:

```bash
ros2 launch turtlebot4_steel_city_competition restaurant_bringup.launch.py
```

## Verify

```bash
ros2 topic echo /amcl_pose
ros2 service list | grep navigate
```
