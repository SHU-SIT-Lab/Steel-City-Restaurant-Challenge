#!/bin/bash
# Native (no-Docker) launch: source ROS 2 Jazzy + the competition workspace,
# configure the discovery server + FastDDS interface whitelist (the same fix the
# Docker entrypoint applies), then drop into a shell or run "$@".
#
# Run from the repo root INSIDE the Ubuntu 24.04 distro:
#   ROBOT_IP=192.168.8.111 bash scripts/native/run_native.sh
#   (or set ROBOT_IP in docker/nav.env and just run it)
set -eo pipefail

ROBOT_IP="${ROBOT_IP:-$(sed -n 's/^ROBOT_IP=//p' docker/nav.env 2>/dev/null | tail -1)}"
if [[ ! "$ROBOT_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Set ROBOT_IP (env or docker/nav.env). e.g. ROBOT_IP=192.168.8.111" >&2
    exit 1
fi

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_SUPER_CLIENT=True
export ROS_DISCOVERY_SERVER="${ROBOT_IP}:11811"

# Pin FastDDS to the interface on the robot subnet (avoids docker0/VPN locator
# pollution that breaks discovery over Wi-Fi). See docs/troubleshooting_dds_wsl.md.
SUBNET="$(echo "$ROBOT_IP" | cut -d. -f1-3)."
LOCAL_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep "^${SUBNET//./\\.}" | head -1)"
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
    echo "[OK] FastDDS pinned to ${LOCAL_IP}"
else
    echo "[WARN] no local IP on ${SUBNET}0/24 — join the robot's Wi-Fi; DDS may not discover it." >&2
fi

# shellcheck disable=SC1091
source turtlebot4_ws/install/setup.bash 2>/dev/null || true

echo "ROS 2 Jazzy ready (native, no Docker). ROBOT_IP=${ROBOT_IP}"
echo "  Test: ros2 topic list   (expect /scan, /oakd/*, /battery_state)"
if [[ "$#" -gt 0 ]]; then exec "$@"; else exec bash; fi
