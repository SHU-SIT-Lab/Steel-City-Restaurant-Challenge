#!/usr/bin/env bash
# Launch the waypoint GUI with the same ROS/FastDDS env as the competition stack.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/turtlebot4_ws/install/setup.bash" 2>/dev/null || true

# Interactive GUI tools need super-client visibility over the discovery server.
export ROS_SUPER_CLIENT=true
export ROS_LOCALHOST_ONLY=0

if [[ -f /etc/turtlebot4/fastdds_wifi.xml ]]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE=/etc/turtlebot4/fastdds_wifi.xml
elif [[ -f "$REPO_ROOT/configs/fastdds_discovery_super_client.xml" ]]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE="$REPO_ROOT/configs/fastdds_discovery_super_client.xml"
fi

ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true

exec python3 "$REPO_ROOT/scripts/nav/record_waypoints.py" "$@"
