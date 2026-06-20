#!/bin/bash
# WSL2 variant of run_container.sh.
#
# Differences from the native-Linux script:
#   - GUI via WSLg: no xhost/xauth dance; mount /mnt/wslg and pass DISPLAY +
#     WAYLAND_DISPLAY + XDG_RUNTIME_DIR so RViz / the waypoint GUI render.
#   - Assumes Docker Engine running inside WSL and WSL2 mirrored networking
#     (so --net=host reaches the robot on the Wi-Fi subnet).
#
# Robot IP resolution matches run_container.sh: positional arg > exported
# ROBOT_IP > docker/nav.env default > interactive prompt.
set -euo pipefail

IMAGE_NAME="steel-city-jazzy:latest"
CONTAINER_NAME="steel-city-dev"
DO_BUILD=0

usage() {
    cat <<'EOF'
Usage: ./docker/run_container_wsl.sh [--build] [ROBOT_IP]
  ROBOT_IP   TurtleBot4 RPi Wi-Fi IP (optional; defaults from docker/nav.env)
  --build    Rebuild the image before starting
EOF
}

validate_ipv4() {
    local ip="$1"
    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build) DO_BUILD=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *)
            if validate_ipv4 "$1"; then ROBOT_IP="$1"; shift
            else echo "Invalid ROBOT_IP: $1" >&2; usage; exit 1; fi ;;
    esac
done

# Fall back to the default ROBOT_IP in docker/nav.env when none was passed.
NAV_ENV="$(dirname "$0")/nav.env"
if [[ -z "${ROBOT_IP:-}" && -f "$NAV_ENV" ]]; then
    ENV_ROBOT_IP="$(sed -n 's/^ROBOT_IP=//p' "$NAV_ENV" | tail -n1)"
    if validate_ipv4 "$ENV_ROBOT_IP"; then
        ROBOT_IP="$ENV_ROBOT_IP"
        echo "Using ROBOT_IP=$ROBOT_IP from docker/nav.env"
    fi
fi

if [[ -z "${ROBOT_IP:-}" ]]; then
    while true; do
        read -r -p "Discovery Server IP (TurtleBot4 RPi Wi-Fi IP): " ROBOT_IP
        if validate_ipv4 "$ROBOT_IP"; then break; fi
        echo "Invalid IP address. Example: 192.168.8.111"
    done
fi

if [[ ! -e /mnt/wslg ]]; then
    echo "[WARN] /mnt/wslg not found — are you inside WSL? GUI apps may not render." >&2
fi

if [[ "$DO_BUILD" -eq 1 ]]; then
    docker build -t "$IMAGE_NAME" -f docker/Dockerfile .
fi

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Image $IMAGE_NAME not found. Re-run with --build." >&2
    exit 1
fi

CURRENT_DIR="$(pwd)"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run -it \
    --name="$CONTAINER_NAME" \
    --env="DISPLAY=${DISPLAY:-:0}" \
    --env="WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}" \
    --env="XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}" \
    --env="PULSE_SERVER=${PULSE_SERVER:-/mnt/wslg/PulseServer}" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="ROBOT_IP=${ROBOT_IP}" \
    --env="ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}" \
    --env="NVIDIA_DRIVER_CAPABILITIES=all" \
    --env="NVIDIA_VISIBLE_DEVICES=all" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="/mnt/wslg:/mnt/wslg:rw" \
    --volume="$CURRENT_DIR/docker/entrypoint.sh:/entrypoint.sh:ro" \
    --volume="$CURRENT_DIR:/root/docker-ws" \
    --net=host \
    --privileged \
    --gpus all \
    "$IMAGE_NAME"
