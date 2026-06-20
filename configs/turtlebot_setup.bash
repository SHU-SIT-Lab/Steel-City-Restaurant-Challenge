# Example discovery-server setup for bare-metal Ubuntu 24.04 hosts.
# Inside Docker, /etc/turtlebot4/setup.bash is generated automatically from
# configs/turtlebot_setup.bash.template at container start.
#
# Replace ROBOT_IP with your TurtleBot4 RPi Wi-Fi address.
source /opt/ros/jazzy/setup.bash

export ROS_DOMAIN_ID=0
export ROS_LOCAL_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

export ROS_SUPER_CLIENT=True
export ROS_DISCOVERY_SERVER="ROBOT_IP:11811;"
