#!/usr/bin/env bash
# Competition-day startup guide and quick diagnostics (run inside steel-city-dev).
set -euo pipefail

REPO="/root/docker-ws"
cd "$REPO"

echo "=============================================="
echo " Steel City — Competition Stack Startup"
echo "=============================================="
echo ""
echo "ROBOT_IP=${ROBOT_IP:-unset}"
echo "MAP_FILE=${MAP_FILE:-/root/docker-ws/maps/home.yaml}"
echo ""

"$REPO/scripts/nav/fix_map_names.sh" || true
python3 "$REPO/scripts/nav/apply_nav2_competition.py" 2>/dev/null || echo "[WARN] Run apply_nav2_competition.py after sourcing ROS"
python3 "$REPO/scripts/nav/normalize_waypoints.py" 2>/dev/null || true

echo ""
echo "--- Step 1: Robot (SSH ubuntu@192.168.4.239) ---"
echo "  ros2 launch turtlebot4_bringup robot.launch.py"
echo "  (Undock the robot so the OAK-D camera is active.)"
echo ""
echo "--- Step 2: Docker terminal 1 — Localization + RViz ---"
echo "  $REPO/scripts/nav/launch_localization.sh"
echo ""
echo "--- Step 3: RViz — set initial pose ---"
echo "  Use '2D Pose Estimate' until the laser scan aligns with map walls."
echo ""
echo "--- Step 4: Docker terminal 2 — Nav2 (ONLY ONCE) ---"
echo "  $REPO/scripts/nav/stop_navigation_stack.sh   # if Nav2 was launched twice before"
echo "  $REPO/scripts/nav/launch_nav2.sh"
echo "  # If costmaps stay empty after 30s: $REPO/scripts/nav/activate_nav2.sh"
echo ""
echo "--- Step 4b: If Nav2 goals fail ---"
echo "  $REPO/scripts/trial/diagnose_nav2_goal.sh"
echo ""
echo "--- Step 5: Docker terminal 3 — Full competition stack ---"
echo "  export OPENAI_API_KEY=...   # required for LLM order-taking"
echo "  ros2 launch turtlebot4_steel_city_competition steel_city.launch.py enable_laptop_audio:=true"
echo ""
echo "--- Step 6: Validate ---"
echo "  python3 $REPO/scripts/trial/run_unit_tests.py"
echo "  $REPO/scripts/trial/preflight_verify.sh"
echo "  $REPO/scripts/trial/diagnose_nav2_goal.sh"
echo "  $REPO/scripts/nav/run_record_waypoints.sh           # camera GUI (recommended)"
echo "  python3 $REPO/scripts/nav/record_waypoints.py   # or run Python directly"
echo "  $REPO/scripts/nav/view_camera.sh                # or use this for camera"
echo ""

if command -v ros2 >/dev/null 2>&1; then
  echo "--- Live diagnostics ---"
  ros2 topic list 2>/dev/null | grep -E "scan|oakd|amcl_pose" || echo "  [WARN] Missing robot topics — check ROBOT_IP and robot bringup"
  ros2 action list 2>/dev/null | grep navigate_to_pose || echo "  [WARN] Nav2 action missing — launch competition_nav2.launch.py"
  ros2 service list 2>/dev/null | grep navigate_to_waypoint || echo "  [WARN] Nav service missing — launch steel_city.launch.py"
  echo ""
fi

echo "Full guide: docs/demo_run.md"
