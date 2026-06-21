#!/usr/bin/env bash
# Launch AMCL + map server + RViz (run inside Docker only — not on the robot).
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source /etc/turtlebot4/setup.bash 2>/dev/null || source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/turtlebot4_ws/install/setup.bash" 2>/dev/null || true
# shellcheck disable=SC1091
source "$REPO_ROOT/scripts/nav/nav_ros_env.sh"
nav_ros_env "$REPO_ROOT"

export MAP_FILE="${MAP_FILE:-$REPO_ROOT/maps/home.yaml}"
export RVIZ_CONFIG="${RVIZ_CONFIG:-$REPO_ROOT/configs/competition_navigation.rviz}"
export REPO_ROOT="$REPO_ROOT"

python3 "$REPO_ROOT/scripts/nav/apply_nav2_competition.py"

count="$(ros2 node list 2>/dev/null | grep -c controller_server || true)"
if [[ "${count:-0}" -gt 0 ]]; then
  echo "[FAIL] Nav2 is already running ($count controller_server nodes)." >&2
  echo "       Run only ONE navigation stack. Stop extras:" >&2
  echo "         $REPO_ROOT/scripts/nav/stop_navigation_stack.sh" >&2
  exit 1
fi

loc_count="$(ros2 node list 2>/dev/null | grep -c map_server || true)"
if [[ "${loc_count:-0}" -gt 0 ]]; then
  echo "[FAIL] Localization already running ($loc_count map_server nodes)." >&2
  echo "       Stop first: $REPO_ROOT/scripts/nav/stop_navigation_stack.sh" >&2
  exit 1
fi

echo "MAP_FILE=$MAP_FILE"
echo "Launching localization + RViz..."
exec ros2 launch turtlebot4_steel_city_competition competition_localization.launch.py \
  "map:=$MAP_FILE"
