#!/usr/bin/env bash
# Stop localization + Nav2 launched from this repo (Docker or robot).
set -eo pipefail

echo "Stopping Steel City navigation stack..."

patterns=(
  "competition_localization.launch.py"
  "competition_nav2.launch.py"
  "turtlebot4_navigation localization.launch.py"
  "turtlebot4_navigation nav2.launch.py"
  "localization_launch.py"
  "navigation_launch.py"
)

for pat in "${patterns[@]}"; do
  pkill -f "$pat" 2>/dev/null || true
done

sleep 2

if command -v ros2 >/dev/null 2>&1; then
  ros2 daemon stop >/dev/null 2>&1 || true
  ros2 daemon start >/dev/null 2>&1 || true
fi

count="$(ros2 node list 2>/dev/null | grep -c controller_server || true)"
if [[ "${count:-0}" -gt 0 ]]; then
  echo "[WARN] controller_server still listed ($count). Orphan nodes may remain until you close other launch terminals."
else
  echo "[OK] Navigation stack stopped."
fi
