#!/bin/bash
# Install ROS 2 Jazzy + TurtleBot4 natively inside a WSL Ubuntu 24.04 (noble)
# distro — the Docker-free equivalent of docker/Dockerfile. Run as root:
#
#   wsl -d Ubuntu-24.04 -u root bash /mnt/c/.../scripts/native/install_jazzy.sh
#
# (RoboStack has no Jazzy, and the default WSL Ubuntu 26.04 is too new for the
#  Jazzy apt repo — hence a dedicated Ubuntu 24.04 distro.)
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== ROS 2 Jazzy apt repo (Ubuntu 24.04 / noble) ==="
apt-get update
apt-get install -y curl gnupg ca-certificates locales software-properties-common
locale-gen en_US.UTF-8
add-apt-repository -y universe
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu noble main" > /etc/apt/sources.list.d/ros2.list
apt-get update

echo "=== installing ros-jazzy-desktop + TurtleBot4 (large download) ==="
apt-get install -y \
  ros-jazzy-desktop \
  ros-jazzy-turtlebot4-desktop \
  ros-jazzy-turtlebot4-description \
  ros-jazzy-turtlebot4-msgs \
  ros-jazzy-turtlebot4-navigation \
  ros-jazzy-turtlebot4-node \
  ros-jazzy-cv-bridge \
  python3-colcon-common-extensions \
  python3-rosdep

rosdep init 2>/dev/null || true
rosdep update || true

echo "=== done: $(ls /opt/ros/jazzy/setup.bash && echo OK) ==="
echo "Next: build the workspace and use scripts/native/run_native.sh"
