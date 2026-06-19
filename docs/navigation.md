# Navigation

Competition navigation uses Nav2 via `RestaurantNavigator` (`nav2_simple_commander`) and named poses in [`configs/waypoints.yaml`](../configs/waypoints.yaml).

## Prerequisites

On the **TurtleBot4 Raspberry Pi**:

1. Robot bringup: `ros2 launch turtlebot4_bringup robot.launch.py`
2. Localization: `ros2 launch turtlebot4_navigation localization.launch.py map:=<your_map>.yaml`
3. Nav2: `ros2 launch turtlebot4_navigation nav2.launch.py`

On the **dev machine / Docker container**, discovery must point at the robot RPi (handled automatically by `./docker/run_container.sh`).

## Waypoints

Edit [`configs/waypoints.yaml`](../configs/waypoints.yaml) after mapping the arena. Keys used by behaviors:

| Key        | Used for                    |
| ---------- | --------------------------- |
| `entrance` | Customer check / queue      |
| `barista`  | Order pickup                |
| `table_1`…`table_5` | Table service        |

Each entry has `x`, `y`, `yaw` in the **map** frame.

## Mapping

From Docker (sync SLAM on PC recommended):

```bash
ros2 launch turtlebot4_navigation slam.launch.py
# Drive the robot, then save:
ros2 run nav2_map_server map_saver_cli -f restaurant_map
```

## Competition stack

Navigation is wired into `turtlebot4_run.py` via `ctx["navigation"]`. Behaviors call `navigate_to("table_1")` etc.

Launch competition nodes:

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
# In another terminal after Nav2 is active, test a goal via the competition navigator or RViz Nav2 Goal tool.
```
