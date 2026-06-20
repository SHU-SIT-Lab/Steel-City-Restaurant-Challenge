#!/usr/bin/env bash
# §15 pre-flight quick verify (2 minutes)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

fail=0

check() {
  if eval "$2"; then
    echo "[OK] $1"
  else
    echo "[FAIL] $1"
    fail=1
  fi
}

check "maps/restaurant.yaml" "test -f maps/restaurant.yaml"
check "maps/restaurant.pgm" "test -f maps/restaurant.pgm"
check "configs/security_key.json" "test -f configs/security_key.json"
check "configs/config.yaml" "test -f configs/config.yaml"
check "waypoint keys" "grep -q '^entrance:' configs/waypoints.yaml && grep -q '^table_5:' configs/waypoints.yaml"

if command -v ros2 >/dev/null 2>&1; then
  check "ROS topics" "ros2 topic list 2>/dev/null | grep -q scan"
  check "nav service" "ros2 service list 2>/dev/null | grep -q navigate_to_waypoint"
else
  echo "[SKIP] ros2 not in PATH (run inside Docker for full check)"
fi

if python3 scripts/database/test_connection.py >/dev/null 2>&1; then
  echo "[OK] database test_connection"
else
  echo "[FAIL] database test_connection (credentials?)"
  fail=1
fi

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "[OK] OPENAI_API_KEY set"
else
  echo "[WARN] OPENAI_API_KEY not set (speech disabled)"
fi

exit "$fail"
