#!/usr/bin/env bash
# Discovery-server env for Nav2/localization *nodes* (CLIENT, not SUPER_CLIENT).
# Source after /etc/turtlebot4/setup.bash in launch scripts.
nav_ros_env() {
  local repo_root="${1:-/root/docker-ws}"
  export ROS_LOCALHOST_ONLY=0
  export ROS_SUPER_CLIENT=false
  export FASTRTPS_DEFAULT_PROFILES_FILE="${repo_root}/configs/fastdds_discovery_client.xml"
  if [[ ! -f "$FASTRTPS_DEFAULT_PROFILES_FILE" ]]; then
    echo "[WARN] Missing $FASTRTPS_DEFAULT_PROFILES_FILE — recreate container with ./docker/run_container.sh <robot-ip>" >&2
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  nav_ros_env "$(cd "$(dirname "$0")/../.." && pwd)"
  echo "ROS_SUPER_CLIENT=$ROS_SUPER_CLIENT"
  echo "FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE"
fi
