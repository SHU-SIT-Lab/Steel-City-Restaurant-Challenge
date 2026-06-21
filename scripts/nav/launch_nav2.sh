#!/usr/bin/env bash
# Launch Nav2 (run inside Docker only — after localization and 2D pose estimate).
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/turtlebot4_ws/install/setup.bash" 2>/dev/null || true
# shellcheck disable=SC1091
source "$REPO_ROOT/scripts/nav/nav_ros_env.sh"
nav_ros_env "$REPO_ROOT"
export REPO_ROOT="$REPO_ROOT"

python3 "$REPO_ROOT/scripts/nav/apply_nav2_competition.py"

count="$(ros2 node list 2>/dev/null | grep -c controller_server || true)"
if [[ "${count:-0}" -gt 0 ]]; then
  echo "[FAIL] Nav2 already running ($count controller_server nodes)." >&2
  echo "       Only launch Nav2 ONCE. Stop duplicates:" >&2
  echo "         $REPO_ROOT/scripts/nav/stop_navigation_stack.sh" >&2
  exit 1
fi

if ! ros2 topic list 2>/dev/null | grep -q '^/map$'; then
  echo "[FAIL] /map not published. Launch localization first:" >&2
  echo "         $REPO_ROOT/scripts/nav/launch_localization.sh" >&2
  exit 1
fi

echo "Launching Nav2..."
ros2 launch turtlebot4_steel_city_competition competition_nav2.launch.py &
nav_pid=$!

echo "Waiting for Nav2 nodes to start (discovery server may need extra time)..."
sleep 25
if "$REPO_ROOT/scripts/nav/activate_nav2.sh"; then
  echo "[OK] Nav2 stack active — set 2D Pose Estimate in RViz, then send Nav2 Goal."
else
  echo "[WARN] Some Nav2 nodes did not activate. Retry: $REPO_ROOT/scripts/nav/activate_nav2.sh"
fi

wait "$nav_pid"
