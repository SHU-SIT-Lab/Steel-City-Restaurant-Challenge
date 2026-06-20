#!/usr/bin/env bash
# §4 navigation acceptance checks (run inside Docker with robot connected)
set -euo pipefail

echo "=== ROS topics (scan/odom/camera) ==="
ros2 topic list | grep -E "scan|odom|camera" || { echo "FAIL: missing robot topics"; exit 1; }

echo "=== AMCL pose ==="
timeout 10 ros2 topic echo /amcl_pose --once || { echo "FAIL: /amcl_pose not publishing"; exit 1; }

echo "=== Navigation service ==="
ros2 service list | grep navigate_to_waypoint || { echo "FAIL: nav service missing"; exit 1; }

for dest in entrance barista table_1; do
  echo "=== Service call: $dest ==="
  ros2 service call /navigation/navigate_to_waypoint \
    turtlebot4_steel_city_competition/srv/NavigateToWaypoint \
    "{destination: '$dest'}" || { echo "FAIL: $dest"; exit 1; }
done

echo "Navigation acceptance checks PASSED"
