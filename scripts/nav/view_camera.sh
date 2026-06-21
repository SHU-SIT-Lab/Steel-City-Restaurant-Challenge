#!/usr/bin/env bash
# View OAK-D camera outside RViz (avoids RViz Image display crashes in Docker).
set -euo pipefail

if ! command -v ros2 >/dev/null 2>&1; then
  echo "Run inside Docker with ROS sourced." >&2
  exit 1
fi

TOPIC="${1:-/oakd/rgb/preview/image_raw}"
COMPRESSED="${TOPIC}/compressed"

if ! ros2 topic list 2>/dev/null | grep -q "oakd"; then
  echo "No /oakd topics found — start robot bringup and undock the robot." >&2
  exit 1
fi

if ! ros2 topic list 2>/dev/null | grep -qx "$TOPIC"; then
  if ros2 topic list 2>/dev/null | grep -qx "$COMPRESSED"; then
    echo "Raw topic missing; using compressed stream ${COMPRESSED}" >&2
    TOPIC="$COMPRESSED"
  fi
fi

echo "Opening camera viewer on ${TOPIC}"
echo "Alternative: ./scripts/nav/run_record_waypoints.sh"
exec ros2 run rqt_image_view rqt_image_view "${TOPIC}"
