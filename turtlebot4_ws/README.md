# turtlebot4_ws

ROS 2 workspace for the Steel City Restaurant Challenge. Only the competition package is built from source; TurtleBot4 upstream packages come from apt (`ros-jazzy-turtlebot4-*`) inside Docker.

## Build

Inside the Docker container (after `./docker/run_container.sh`):

```bash
source /etc/turtlebot4/setup.bash
cd /root/docker-ws/turtlebot4_ws
colcon build --symlink-install
source install/setup.bash
```

## Run

```bash
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

Ensure Nav2 and localization are running on the robot before navigation behaviors execute.
