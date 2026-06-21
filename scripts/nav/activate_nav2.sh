#!/usr/bin/env bash
# Retry Nav2 lifecycle activation when FastDDS discovery-server service calls time out.
set -eo pipefail

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ROS_SUPER_CLIENT=true
export FASTRTPS_DEFAULT_PROFILES_FILE="${REPO_ROOT}/configs/fastdds_discovery_super_client.xml"

NODES=(
  controller_server
  smoother_server
  planner_server
  route_server
  behavior_server
  bt_navigator
  waypoint_follower
  velocity_smoother
  collision_monitor
  docking_server
)

activate_node() {
  local node="$1"
  local state
  state="$(ros2 lifecycle get "/$node" 2>/dev/null | awk '{print $1}' || echo missing)"
  case "$state" in
    active) return 0 ;;
    inactive)
      ros2 lifecycle set "/$node" activate >/dev/null 2>&1 || true
      ;;
    unconfigured)
      ros2 lifecycle set "/$node" configure >/dev/null 2>&1 || true
      sleep 0.5
      ros2 lifecycle set "/$node" activate >/dev/null 2>&1 || true
      ;;
    missing) return 1 ;;
  esac
  sleep 0.3
  state="$(ros2 lifecycle get "/$node" 2>/dev/null | awk '{print $1}' || echo missing)"
  [[ "$state" == "active" ]]
}

echo "=== Nav2 lifecycle activation retry ==="
for attempt in $(seq 1 5); do
  ok=0
  for node in "${NODES[@]}"; do
    if activate_node "$node"; then
      echo "[OK] $node active"
      ok=$((ok + 1))
    else
      echo "[..] $node not active yet (attempt $attempt)"
    fi
  done
  if [[ "$ok" -ge 8 ]]; then
    echo "Nav2 stack activated ($ok/${#NODES[@]} nodes)."
    exit 0
  fi
  sleep 3
done

echo "[WARN] Some Nav2 nodes did not reach active state. Check /tmp/nav2.log and run stop_navigation_stack.sh before relaunching."
exit 1
