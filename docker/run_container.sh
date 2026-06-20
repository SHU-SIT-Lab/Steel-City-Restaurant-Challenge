#!/bin/bash
set -euo pipefail

IMAGE_NAME="steel-city-jazzy:latest"
CONTAINER_NAME="steel-city-dev"
DO_BUILD=0

usage() {
    cat <<'EOF'
Usage: ./docker/run_container.sh [--build] [ROBOT_IP]

Arguments:
  ROBOT_IP     TurtleBot4 RPi Wi-Fi IP (optional; prompts if omitted)

Environment:
  ROBOT_IP     Same as the positional argument (positional takes precedence)

Options:
  --build      Rebuild the Docker image before starting the container
EOF
}

validate_ipv4() {
    local ip="$1"
    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            DO_BUILD=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if validate_ipv4 "$1"; then
                ROBOT_IP="$1"
                shift
            else
                echo "Invalid ROBOT_IP: $1" >&2
                usage
                exit 1
            fi
            ;;
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
        if validate_ipv4 "$ROBOT_IP"; then
            export ROBOT_IP
            break
        fi
        echo "Invalid IP address. Example: 192.168.1.150"
    done
fi

if [[ "$DO_BUILD" -eq 1 ]]; then
    docker build -t "$IMAGE_NAME" -f docker/Dockerfile .
fi

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Image $IMAGE_NAME not found. Re-run with --build." >&2
    exit 1
fi

if command -v xhost >/dev/null 2>&1; then
    xhost local:root >/dev/null 2>&1 || true
fi

XAUTH=/tmp/.docker.xauth
CURRENT_DIR="$(pwd)"

sudo touch "$XAUTH"
xauth nlist "$DISPLAY" 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f "$XAUTH" nmerge - 2>/dev/null || true

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run -it \
    --name="$CONTAINER_NAME" \
    --env="DISPLAY=${DISPLAY:-:0}" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="ROBOT_IP=${ROBOT_IP}" \
    --env="ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}" \
    --env="XAUTHORITY=$XAUTH" \
    --env="NVIDIA_DRIVER_CAPABILITIES=all" \
    --env="NVIDIA_VISIBLE_DEVICES=all" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$CURRENT_DIR:/root/docker-ws" \
    --volume="$XAUTH:$XAUTH" \
    --net=host \
    --privileged \
    --gpus all \
    "$IMAGE_NAME"
