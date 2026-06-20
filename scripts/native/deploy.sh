#!/usr/bin/env bash
# Turn-key deploy: install AIF deps, build the workspace, configure DDS for the
# robot, pick the brain, and launch — one command. Run INSIDE a ROS 2 Jazzy env
# (the native Ubuntu 24.04 WSL distro, or Docker) from the repo root.
#
#   scripts/native/deploy.sh                 # active inference (default)
#   scripts/native/deploy.sh reactive        # original reactive coordinator
#   scripts/native/deploy.sh aif             # active inference, no law (FIFO)
#   scripts/native/deploy.sh aif-law         # active inference + law-as-code ordering
#
#   BUILD=0 scripts/native/deploy.sh aif     # skip colcon build (already built)
#   DEPS=0  scripts/native/deploy.sh aif     # skip the pip install
#   NO_LAUNCH=1 scripts/native/deploy.sh aif # set everything up but don't launch
#
# ROBOT_IP defaults to docker/nav.env (192.168.8.111). Needs the laptop on the
# robot's Wi-Fi. Prereq: ROS 2 Jazzy installed (scripts/native/install_jazzy.sh).
set -eo pipefail

MODE="${1:-aif}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WS="$REPO_ROOT/turtlebot4_ws"
ROBOT_IP="${ROBOT_IP:-$(sed -n 's/^ROBOT_IP=//p' "$REPO_ROOT/docker/nav.env" 2>/dev/null | tail -1)}"
ROBOT_IP="${ROBOT_IP:-192.168.8.111}"

echo "== deploy: mode=$MODE  robot=$ROBOT_IP =="

# 1) source ROS 2 Jazzy. Some fresh WSL distros mis-apply setup.bash (it generates
#    the right exports but the wrapper drops them), so eval the exports directly.
if [[ -f /opt/ros/jazzy/_local_setup_util.py ]]; then
    eval "$(python3 /opt/ros/jazzy/_local_setup_util.py sh | grep '^export ')"
    export ROS_DISTRO=jazzy ROS_VERSION=2 ROS_PYTHON_VERSION=3
elif [[ -f /opt/ros/jazzy/setup.bash ]]; then
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
else
    echo "ERROR: ROS 2 Jazzy not found at /opt/ros/jazzy." >&2
    echo "Install it first: bash scripts/native/install_jazzy.sh" >&2
    exit 1
fi

# 2) AIF deps (jax + pymdp) into the ROS python env. One-time; slow first run.
if [[ "${DEPS:-1}" != "0" ]]; then
    echo "== installing AIF deps (jax + pymdp) =="
    python3 -m pip install --break-system-packages -q -r "$REPO_ROOT/scripts/aif/requirements.txt"
fi

# 3) build the workspace. --symlink-install so aif_run.py resolves scripts/aif via
#    the source tree (and so .py edits don't need a rebuild).
if [[ "${BUILD:-1}" != "0" ]]; then
    echo "== colcon build (packages-up-to turtlebot4_steel_city_competition) =="
    ( cd "$WS" && colcon build --symlink-install --packages-up-to turtlebot4_steel_city_competition )
fi
if [[ -f "$WS/install/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "$WS/install/setup.bash"
else
    echo "ERROR: $WS/install/setup.bash missing — build failed or BUILD=0 with no prior build." >&2
    exit 1
fi

# 4) DDS: discovery server + FastDDS interface whitelist (same fix the Docker
#    entrypoint applies; avoids docker0/VPN locator pollution over Wi-Fi).
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_SUPER_CLIENT=True
export ROS_DISCOVERY_SERVER="${ROBOT_IP}:11811"
SUBNET="$(echo "$ROBOT_IP" | cut -d. -f1-3)."
LOCAL_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep "^${SUBNET//./\\.}" | head -1 || true)"
if [[ -n "$LOCAL_IP" ]]; then
    cat > /tmp/fastdds_wifi.xml <<EOF
<?xml version="1.0" encoding="UTF-8" ?>
<dds xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <profiles>
    <transport_descriptors>
      <transport_descriptor>
        <transport_id>udp_wifi</transport_id>
        <type>UDPv4</type>
        <interfaceWhiteList>
          <address>${LOCAL_IP}</address>
          <address>127.0.0.1</address>
        </interfaceWhiteList>
      </transport_descriptor>
    </transport_descriptors>
    <participant profile_name="wifi_only" is_default_profile="true">
      <rtps>
        <userTransports><transport_id>udp_wifi</transport_id></userTransports>
        <useBuiltinTransports>false</useBuiltinTransports>
      </rtps>
    </participant>
  </profiles>
</dds>
EOF
    export FASTRTPS_DEFAULT_PROFILES_FILE=/tmp/fastdds_wifi.xml
    echo "== FastDDS pinned to ${LOCAL_IP} =="
else
    echo "WARN: no interface on ${SUBNET}x — are you on the robot's Wi-Fi?" >&2
fi

# 5) select the brain (the AIF flags documented in docs/aif_ros_integration.md)
case "$MODE" in
    reactive) echo "== brain: reactive (argmax priorities) ==" ;;
    aif)      export AIF_COORDINATOR=1; echo "== brain: active inference (no law / FIFO) ==" ;;
    aif-law)  export AIF_COORDINATOR=1 AIF_LAW=1; echo "== brain: active inference + law-as-code ==" ;;
    *) echo "ERROR: unknown mode '$MODE' (use: reactive | aif | aif-law)" >&2; exit 1 ;;
esac

# 6) sanity: is the robot visible? (non-fatal)
echo "== checking robot topics (5s) =="
if timeout 5 ros2 topic list 2>/dev/null | grep -qE "battery_state|scan|oakd"; then
    echo "   robot topics visible — good."
else
    echo "   WARN: no robot topics yet. Check Wi-Fi/firewall — docs/troubleshooting_dds_wsl.md" >&2
fi

# 7) launch (unless NO_LAUNCH=1, for a setup-only dry run)
if [[ "${NO_LAUNCH:-0}" == "1" ]]; then
    echo "== setup complete (NO_LAUNCH=1); env ready in this shell. =="
    exit 0
fi
echo "== launching steel_city.launch.py =="
exec ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
