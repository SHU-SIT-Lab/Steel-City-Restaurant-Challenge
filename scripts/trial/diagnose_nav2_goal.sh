#!/usr/bin/env bash
# Diagnose Nav2 goal rejection (no path / goal fails immediately).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

fail=0
warn=0

pass() { echo "[OK] $1"; }
fail_msg() { echo "[FAIL] $1"; fail=1; }
warn_msg() { echo "[WARN] $1"; warn=1; }

echo "=== Nav2 goal diagnostics ==="
echo "MAP_FILE=${MAP_FILE:-/root/docker-ws/maps/home.yaml}"

nav2_count="$(ros2 node list 2>/dev/null | grep -c controller_server || true)"
if [[ "${nav2_count:-0}" -gt 1 ]]; then
  fail_msg "Duplicate Nav2 stack ($nav2_count controller_server nodes) — run scripts/nav/stop_navigation_stack.sh and launch Nav2 only ONCE in Docker"
elif [[ "${nav2_count:-0}" -eq 1 ]]; then
  pass "single Nav2 stack (1 controller_server)"
fi

map_srv_count="$(ros2 node list 2>/dev/null | grep -c map_server || true)"
if [[ "${map_srv_count:-0}" -gt 1 ]]; then
  fail_msg "Duplicate localization ($map_srv_count map_server nodes) — stop extra localization launches"
fi
if [[ "${MAP_FILE:-}" == *restaurant* ]]; then
  warn_msg "MAP_FILE is restaurant.yaml — waypoints were recorded on home.yaml; use: export MAP_FILE=/root/docker-ws/maps/home.yaml"
fi
echo ""

if ! command -v ros2 >/dev/null 2>&1; then
  fail_msg "ros2 not in PATH — run inside Docker"
  exit 1
fi

echo "--- Action server ---"
if ros2 action list 2>/dev/null | grep -q navigate_to_pose; then
  pass "/navigate_to_pose action available"
elif ros2 action list 2>/dev/null | grep -q navigate_to_position; then
  fail_msg "/navigate_to_pose missing (only navigate_to_position found) — launch competition_nav2.launch.py in a separate terminal"
else
  fail_msg "/navigate_to_pose missing — launch competition_nav2.launch.py"
fi

echo "--- Localization ---"
if ros2 topic list 2>/dev/null | grep -q '^/map$'; then
  pass "/map topic present"
else
  fail_msg "/map not published — launch competition_localization.launch.py FIRST (Terminal 1)"
fi

echo "--- TF map -> base_link ---"
if timeout 8 ros2 run tf2_ros tf2_echo map base_link 2>&1 | grep -q "At time"; then
  pass "TF map -> base_link available"
else
  fail_msg "TF map->base_link missing — click 2D Pose Estimate in RViz until laser scan aligns with walls"
fi

echo "--- Initial pose ---"
if timeout 8 ros2 topic echo /amcl_pose --once >/dev/null 2>&1; then
  pass "/amcl_pose publishing"
else
  fail_msg "/amcl_pose not publishing — localization running? Set 2D Pose Estimate in RViz"
fi

echo "--- Map file ---"
map_path="${MAP_FILE:-/root/docker-ws/maps/home.yaml}"
if [[ -f "$map_path" ]]; then
  pass "Map file exists: $map_path"
else
  fail_msg "Map file missing: $map_path"
fi

echo "--- Costmaps ---"
if ros2 topic list 2>/dev/null | grep -q global_costmap; then
  if ros2 topic list 2>/dev/null | grep -q '^/map$'; then
    pass "global_costmap topics present (with /map — good)"
  else
    warn_msg "global_costmap present but /map missing — Nav2 without localization; stop Nav2, start localization first"
  fi
else
  warn_msg "global_costmap topics missing — launch competition_nav2.launch.py (Terminal 2, after localization)"
fi

echo "--- Nav2 lifecycle ---"
for node in bt_navigator planner_server controller_server; do
  state="$(ros2 lifecycle get "/$node" 2>/dev/null | awk '{print $1}' || echo missing)"
  if [[ "$state" == "active" ]]; then
    pass "$node active"
  else
    fail_msg "$node is $state (not active) — run scripts/nav/activate_nav2.sh; goals are rejected until bt_navigator is active"
  fi
done

echo "--- cmd_vel topic types ---"
if ros2 topic list 2>/dev/null | grep -q '^/cmd_vel$'; then
  types=$(ros2 topic info /cmd_vel -v 2>/dev/null | grep -E 'Type:' || true)
  if echo "$types" | grep -q TwistStamped && echo "$types" | grep -q 'Twist[^S]'; then
    warn_msg "/cmd_vel has mixed Twist and TwistStamped publishers — robot may not move"
  else
    pass "/cmd_vel topic info looks consistent"
  fi
else
  warn_msg "/cmd_vel not listed yet (normal until Nav2 sends velocity)"
fi

echo "--- Competition params ---"
for f in configs/nav2_competition.yaml configs/localization_competition.yaml; do
  if [[ -f "$f" ]]; then
    pass "$f present"
  else
    warn_msg "$f missing — run: python3 scripts/nav/apply_nav2_competition.py"
  fi
done

echo "--- Waypoint keys ---"
if python3 scripts/trial/validate_waypoints.py >/dev/null 2>&1; then
  pass "waypoints.yaml has required keys"
else
  warn_msg "waypoint keys incomplete — run: python3 scripts/nav/normalize_waypoints.py"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Diagnostics passed core checks."
  if [[ "$warn" -ne 0 ]]; then
    echo "Review warnings above before sending Nav2 goals."
  fi
  echo ""
  echo "If goals still produce NO PATH:"
  echo "  1. Confirm laser scan aligns with map walls (2D Pose Estimate)"
  echo "  2. Click Nav2 Goal in a WHITE (free) cell, not near walls"
  echo "  3. Ensure MAP_FILE matches the map used when waypoints were recorded"
  echo "  4. Read Nav2 terminal for 'Failed to create plan' or 'Start pose in collision'"
  echo ""
  echo "If goal is accepted but robot does not move (Nav2 aborts with error 105):"
  echo "  - Re-run: python3 scripts/nav/apply_nav2_competition.py && restart Nav2"
  echo "  - Undock the robot; confirm /cmd_vel publishes during the goal"
  echo "  - Set 2D Pose Estimate again so scan overlays map walls"
  exit 0
fi

echo "Fix FAIL items above, then retry Nav2 Goal in RViz."
exit 1
