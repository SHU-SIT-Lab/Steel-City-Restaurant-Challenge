#!/usr/bin/env bash
# Diagnose why /oakd/* camera topics are missing or not publishing.
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

PREFERRED="/oakd/rgb/preview/image_raw"
COMPRESSED="${PREFERRED}/compressed"

warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; }
ok() { echo "[OK] $*"; }
info() { echo "      $*"; }

echo "=== Camera diagnostics ==="
echo "ROS_DISCOVERY_SERVER=${ROS_DISCOVERY_SERVER:-unset}"
echo "ROBOT_IP=${ROBOT_IP:-unset}"
echo ""

topic_count="$(ros2 topic list 2>/dev/null | wc -l | tr -d ' ')"
echo "=== ROS graph (${topic_count} topics) ==="
if [[ "${topic_count:-0}" -lt 5 ]]; then
  fail "Almost no ROS topics visible — discovery server / robot bringup problem"
  info "On robot: ros2 launch turtlebot4_bringup robot.launch.py"
  info "Recreate Docker: ./docker/run_container.sh <robot-wifi-ip>"
  exit 1
fi
ok "ROS discovery looks connected (${topic_count} topics)"

echo ""
echo "=== Robot sensor topics ==="
for t in /scan /odom /battery_state /dock_status; do
  if ros2 topic list 2>/dev/null | grep -qx "$t"; then
    ok "$t listed"
  else
    warn "$t not listed"
  fi
done

echo ""
echo "=== OAK-D topics ==="
oakd_topics="$(ros2 topic list 2>/dev/null | grep -i oakd || true)"
if [[ -z "$oakd_topics" ]]; then
  fail "No /oakd/* topics in the graph"
  echo ""
  echo "Most common causes:"
  echo "  1. Robot is DOCKED — OAK-D is powered off while charging"
  echo "  2. Camera driver crashed (Jazzy power_save bug after dock/undock)"
  echo ""
  echo "Fix steps:"
  echo "  A. Undock: ./scripts/nav/undock_robot.sh"
  echo "  B. Wait 10s, re-run this script"
  echo "  C. On robot SSH, check: ros2 topic list | grep oakd"
  echo "  D. If still missing after undock, on robot run:"
  echo "       sudo turtlebot4-service-restart"
  echo "     or disable power_saver in turtlebot4.yaml (see docs/demo_run.md)"
  exit 1
fi
echo "$oakd_topics" | sed 's/^/  /'
ok "OAK-D topics present"

echo ""
echo "=== Camera publish rate (5s window) ==="
camera_ok=0
for topic in "$PREFERRED" "$COMPRESSED"; do
  if ! ros2 topic list 2>/dev/null | grep -qx "$topic"; then
    info "$topic — not listed, skipping"
    continue
  fi
  echo -n "  $topic ... "
  if timeout 8 ros2 topic hz "$topic" --window 5 2>/dev/null | grep -q "average rate"; then
    ok "publishing"
    camera_ok=1
    break
  else
    warn "listed but no messages in 5s"
  fi
done

if [[ "$camera_ok" -eq 0 ]]; then
  fail "Camera topic(s) exist but nothing is publishing"
  echo ""
  if ros2 topic list 2>/dev/null | grep -qx /dock_status; then
    echo "Checking /dock_status ..."
    dock_msg="$(timeout 3 ros2 topic echo /dock_status --once 2>/dev/null || true)"
    if echo "$dock_msg" | grep -qi "is_docked: true"; then
      fail "Robot reports DOCKED — undock first: ./scripts/nav/undock_robot.sh"
      exit 1
    fi
    if echo "$dock_msg" | grep -qi "is_docked: false"; then
      warn "Robot is undocked but camera still silent — likely Jazzy OAK-D driver hang"
      info "On robot: sudo turtlebot4-service-restart"
      info "Or set power_saver: false in turtlebot4_bringup config and restart services"
      exit 1
    fi
  fi
  warn "Undock the robot, wait 10s, run: ./scripts/nav/undock_robot.sh"
  exit 1
fi

echo ""
ok "Camera is publishing — launch GUI: ./scripts/nav/run_record_waypoints.sh"
