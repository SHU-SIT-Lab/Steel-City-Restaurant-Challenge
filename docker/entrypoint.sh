#!/bin/bash
set -eo pipefail

TEMPLATE="/etc/turtlebot4/setup.bash.template"
SETUP="/etc/turtlebot4/setup.bash"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"

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
    echo "  Test connectivity: ros2 topic list   (run twice if the list looks incomplete)"
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

# shellcheck disable=SC1091
source "$SETUP"

ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start

print_startup_confirmation

exec "$@"
