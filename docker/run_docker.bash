xhost local:root

XAUTH=/tmp/.docker.xauth
CURRENT_DIR="$(pwd)"

docker run -it \
       --name=ros_container \
       --env="DISPLAY=$DISPLAY" \
       --env="QT_X11_NO_MITSHM=1" \
       --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
       --volume="$CURRENT_DIR:/root/docker-ws" \
       --env="XAUTHORITY=$XAUTH" \
       --env="NVIDIA_DRIVER_CAPABILITIES=all" \
       --env="NVIDIA_VISIBLE_DEVICES=all" \
       --volume="$XAUTH:$XAUTH" \
       --net=host \
       --privileged \
       --gpus all \
       aung9htet/ubuntu-22.04:jazzy
echo "Done"
