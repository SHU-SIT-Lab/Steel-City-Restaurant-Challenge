#!/bin/bash
set -eo pipefail

TEMPLATE="/etc/turtlebot4/setup.bash.template"
SETUP="/etc/turtlebot4/setup.bash"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
NAV_ENV="/root/docker-ws/docker/nav.env"
FASTDDS_PROFILE="/etc/turtlebot4/fastdds_wifi.xml"

TB4_PACKAGES=(
    ros-jazzy-turtlebot4-desktop
    ros-jazzy-turtlebot4-description
    ros-jazzy-turtlebot4-msgs
    ros-jazzy-turtlebot4-navigation
    ros-jazzy-turtlebot4-node
)

validate_ipv4() {
    local ip="$1"
    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

prompt_robot_ip() {
    local ip=""
    while true; do
        read -r -p "Discovery Server IP (TurtleBot4 RPi Wi-Fi IP): " ip
        if validate_ipv4 "$ip"; then
            ROBOT_IP="$ip"
            break
        fi
        echo "Invalid IP address. Example: 192.168.1.150"
    done
}

# Pin FastDDS to the interface on the robot's subnet. The laptop usually has
# several interfaces (Docker bridge, VPNs, corporate Wi-Fi); FastDDS otherwise
# advertises all of them as locators and the robot's discovery server tries to
# reply on ones it cannot route to, so discovery silently fails over Wi-Fi.
# See docs/troubleshooting_dds_wsl.md.
write_fastdds_profile() {
    local subnet local_ip
    subnet="$(echo "$ROBOT_IP" | cut -d. -f1-3)."
    local_ip="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep "^${subnet//./\\.}" | head -1)"
    if [[ -z "$local_ip" ]]; then
        echo "[WARN] No local IP found on ${subnet}0/24; DDS may fail to discover the robot over Wi-Fi." >&2
        return
    fi
    cat > "$FASTDDS_PROFILE" <<EOF
<?xml version="1.0" encoding="UTF-8" ?>
<dds xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <profiles>
    <transport_descriptors>
      <transport_descriptor>
        <transport_id>udp_wifi</transport_id>
        <type>UDPv4</type>
        <interfaceWhiteList>
          <address>${local_ip}</address>
          <address>127.0.0.1</address>
        </interfaceWhiteList>
      </transport_descriptor>
    </transport_descriptors>
    <participant profile_name="wifi_only" is_default_profile="true">
      <rtps>
        <userTransports>
          <transport_id>udp_wifi</transport_id>
        </userTransports>
        <useBuiltinTransports>false</useBuiltinTransports>
      </rtps>
    </participant>
  </profiles>
</dds>
EOF
    export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_PROFILE"
    echo "[OK] FastDDS pinned to interface ${local_ip} (profile ${FASTDDS_PROFILE})"
}

print_startup_confirmation() {
    echo ""
    echo "=== Steel City Docker startup ==="
    echo ""
    echo "[OK] /etc/turtlebot4/setup.bash configured:"
    sed 's/^/  /' "$SETUP"
    echo ""
    echo "[OK] /root/.bashrc configured with:"
    grep -E 'turtlebot4/setup.bash|turtlebot4_ws/install/setup.bash' /root/.bashrc | sed 's/^/  /'
    echo ""
    echo "[OK] TurtleBot4 ROS packages:"
    for pkg in "${TB4_PACKAGES[@]}"; do
        if dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "  [installed] $pkg"
        else
            echo "  [missing]  $pkg"
        fi
    done
    echo ""
    echo "ROS 2 Jazzy ready."
    echo "  ROS_DISCOVERY_SERVER=${ROS_DISCOVERY_SERVER}"
    echo "  FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE:-<none>}"
    echo "  MAP_FILE=${MAP_FILE:-/root/docker-ws/maps/restaurant.yaml}"
    echo "  Test connectivity: ros2 topic list   (run twice if the list looks incomplete)"
    echo "  Navigation guide:  docs/navigation.md"
    echo ""
}

if [[ -z "${ROBOT_IP:-}" ]]; then
    if [[ -t 0 ]]; then
        prompt_robot_ip
    else
        echo "ROBOT_IP is not set and no TTY is available for prompting." >&2
        exit 1
    fi
fi

if ! validate_ipv4 "$ROBOT_IP"; then
    echo "Invalid ROBOT_IP: $ROBOT_IP" >&2
    exit 1
fi

sed \
    -e "s/__ROBOT_IP__/${ROBOT_IP}/g" \
    -e "s/__ROS_DOMAIN_ID__/${ROS_DOMAIN_ID}/g" \
    "$TEMPLATE" > "$SETUP"

if ! grep -q "${ROBOT_IP}:11811" "$SETUP"; then
    echo "[WARN] /etc/turtlebot4/setup.bash does not contain ROBOT_IP=${ROBOT_IP}." >&2
    echo "       Recreate the container with ./docker/run_container.sh ${ROBOT_IP}" >&2
fi

# shellcheck disable=SC1091
source "$SETUP"

if [[ -f "$NAV_ENV" ]]; then
    # shellcheck disable=SC1091
    set -a
    source "$NAV_ENV"
    set +a
fi

write_fastdds_profile

ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start

print_startup_confirmation

exec "$@"
