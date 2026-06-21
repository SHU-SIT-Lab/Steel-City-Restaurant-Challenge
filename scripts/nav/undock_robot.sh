#!/usr/bin/env bash
# Undock TurtleBot4 so the OAK-D camera driver starts (camera is off while docked).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/turtlebot4_ws/install/setup.bash" 2>/dev/null || true

export ROS_SUPER_CLIENT=true
export ROS_LOCALHOST_ONLY=0
if [[ -f /etc/turtlebot4/fastdds_wifi.xml ]]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE=/etc/turtlebot4/fastdds_wifi.xml
elif [[ -f "$REPO_ROOT/configs/fastdds_discovery_super_client.xml" ]]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE="$REPO_ROOT/configs/fastdds_discovery_super_client.xml"
fi

ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true

if ! ros2 action list 2>/dev/null | grep -q '/undock'; then
  echo "[FAIL] /undock action not found — is robot bringup running?" >&2
  echo "       On robot: ros2 launch turtlebot4_bringup robot.launch.py" >&2
  exit 1
fi

echo "Sending undock goal (robot must be on the dock) ..."
ros2 action send_goal /undock irobot_create_msgs/action/Undock "{}" --feedback

echo ""
echo "Waiting 10s for OAK-D to start ..."
sleep 10

if ros2 topic list 2>/dev/null | grep -q oakd; then
  echo "[OK] /oakd topics visible:"
  ros2 topic list 2>/dev/null | grep oakd | sed 's/^/  /'
  echo ""
  echo "Verify stream: ros2 topic hz /oakd/rgb/preview/image_raw --window 5"
  echo "Or launch GUI:  ./scripts/nav/run_record_waypoints.sh"
else
  echo "[WARN] Still no /oakd topics after undock." >&2
  echo "       Run: ./scripts/nav/diagnose_camera.sh" >&2
  echo "       On robot SSH: sudo turtlebot4-service-restart" >&2
  exit 1
fi
