#xhost local:root
#
#XAUTH=/tmp/.docker.xauth
#CURRENT_DIR="$(pwd)"
#
#docker run -it \
#    --name ros_container \
#    --net=host \
#    --ipc=host \
#    --privileged \
#    --gpus all \
#    -e DISPLAY=$DISPLAY \
#    -e QT_X11_NO_MITSHM=1 \
#    -e NVIDIA_VISIBLE_DEVICES=all \
#    -e NVIDIA_DRIVER_CAPABILITIES=all \
#    -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
#    -e ROS_DOMAIN_ID=0 \
#    -e ROS_LOCALHOST_ONLY=0 \
#    -e FASTRTPS_DEFAULT_PROFILES_FILE=/root/docker-ws/configs/fastdds_host.xml \
#    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
#    -v $CURRENT_DIR:/root/docker-ws \
#    aung9htet/ubuntu-22.04:jammy

# Allow local container connections to the host's X server
xhost local:root

CURRENT_DIR="$(pwd)"

docker run -it \
    --name ros_container \
    --net=host \
    --ipc=host \
    --privileged \
    --gpus all \
    -e DISPLAY=$DISPLAY \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v $CURRENT_DIR:/root/turtlebot-ws \
    ros:jazzy-ros-base
