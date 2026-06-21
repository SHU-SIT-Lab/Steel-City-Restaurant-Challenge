#!/usr/bin/env bash
# Verify Docker can run Nav2 (TF, scan, costmap publishers) vs robot-only baseline.
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash

# CLI diagnostics need super client to see all discovery-server participants.
export ROS_SUPER_CLIENT=true
export FASTRTPS_DEFAULT_PROFILES_FILE="${REPO_ROOT}/configs/fastdds_discovery_super_client.xml"

fail=0
pass() { echo "[OK] $1"; }
fail_msg() { echo "[FAIL] $1"; fail=1; }
warn_msg() { echo "[WARN] $1"; }

echo "=== Docker navigation connectivity ==="
echo "ROBOT_IP=${ROBOT_IP:-unset}"
echo "ROS_DISCOVERY_SERVER=${ROS_DISCOVERY_SERVER:-unset}"
echo "ROS_SUPER_CLIENT=${ROS_SUPER_CLIENT:-unset}"
echo "FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE:-unset}"
echo ""

if [[ "${ROS_SUPER_CLIENT:-}" == "true" || "${ROS_SUPER_CLIENT:-}" == "True" ]]; then
  warn_msg "Shell is SUPER_CLIENT — fine for ros2 CLI; launch scripts must set ROS_SUPER_CLIENT=false for Nav2 nodes"
fi

if [[ ! -f "$REPO_ROOT/configs/fastdds_discovery_client.xml" ]]; then
  fail_msg "Missing configs/fastdds_discovery_client.xml — recreate container: ./docker/run_container.sh <robot-ip>"
fi

if ! timeout 6 ros2 topic hz /scan --window 3 2>&1 | grep -q "average rate"; then
  fail_msg "/scan not publishing — robot bringup running? Same Wi-Fi? ping ROBOT_IP?"
else
  pass "/scan publishing from robot"
fi

if timeout 4 ros2 topic echo /odom --once >/dev/null 2>&1; then
  pass "/odom reachable"
else
  fail_msg "/odom not received — discovery-server / Create3 republisher issue"
fi

if timeout 4 ros2 run tf2_ros tf2_echo odom base_link 2>&1 | grep -q "At time"; then
  pass "TF odom -> base_link"
else
  fail_msg "TF odom -> base_link missing — Nav2 and AMCL cannot run in Docker"
fi

if ros2 topic list 2>/dev/null | grep -q '^/map$'; then
  pass "/map topic present"
else
  warn_msg "/map missing — launch localization first"
fi

if timeout 4 ros2 run tf2_ros tf2_echo map base_link 2>&1 | grep -q "At time"; then
  pass "TF map -> base_link (set 2D Pose Estimate if this fails after localization)"
else
  warn_msg "TF map -> base_link missing — normal until AMCL converges + initial pose set"
fi

pubs="$(ros2 topic info /global_costmap/costmap 2>/dev/null | awk '/Publisher count/{print $3}' || echo 0)"
if [[ "${pubs:-0}" -ge 1 ]]; then
  pass "global_costmap publishing ($pubs publisher(s))"
else
  warn_msg "global_costmap has 0 publishers — launch Nav2 with scripts/nav/launch_nav2.sh (CLIENT profile)"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Docker navigation prerequisites look good."
  exit 0
fi
echo "Fix FAIL items above. Root cause is usually discovery-server client config, not duplicate launches."
exit 1
