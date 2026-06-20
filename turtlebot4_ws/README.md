# turtlebot4_ws

ROS 2 workspace for the Steel City Restaurant Challenge. Only the competition package is built from source; TurtleBot4 upstream packages come from apt (`ros-jazzy-turtlebot4-*`) inside Docker.

> **Running from a Windows/WSL2 laptop?** Start with the operator runbook: [docs/OPERATIONS.md](../docs/OPERATIONS.md) — host setup, connecting to the robot over Wi-Fi, and the "ping works but ROS sees nothing" fix.

## Navigation

**Start here:** [docs/navigation.md](../docs/navigation.md)

Navigation (localization, Nav2, waypoints) runs from Docker on the PC. The TurtleBot4 only needs robot bringup. The navigation guide explains the competition-day workflow and how to use the waypoint GUI.

## Build

Inside the Docker container (after `./docker/run_container.sh <robot-ip>`):

```bash
source /etc/turtlebot4/setup.bash
cd /root/docker-ws/turtlebot4_ws
colcon build --symlink-install
source install/setup.bash
```

## Run (after Nav2 + localization are up)

On the robot: start robot bringup.

From Docker: follow [docs/navigation.md](../docs/navigation.md) to load the saved map, start Nav2, set initial pose, and launch the competition stack.

Ensure Nav2 and localization are running before navigation behaviors execute.
