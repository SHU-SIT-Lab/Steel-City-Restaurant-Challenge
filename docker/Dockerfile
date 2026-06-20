FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
    > /etc/apt/sources.list.d/ros2.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-desktop \
    ros-jazzy-turtlebot4-desktop \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-turtlebot4-description \
    ros-jazzy-turtlebot4-msgs \
    ros-jazzy-turtlebot4-navigation \
    ros-jazzy-turtlebot4-node \
    ros-jazzy-cv-bridge \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    python3-pip \
    build-essential \
    git \
    espeak \
    portaudio19-dev \
    libasound2-dev \
    python3-tk \
    python3-pil \
    && rm -rf /var/lib/apt/lists/*

RUN rosdep init 2>/dev/null || true && rosdep update

RUN pip3 install --break-system-packages --no-cache-dir \
    openai-whisper \
    openai \
    firebase-admin \
    pyyaml \
    pyttsx3 \
    scipy \
    pyaudio \
    numpy \
    opencv-python-headless \
    ultralytics \
    speechbrain \
    sounddevice \
    torch

RUN mkdir -p /etc/turtlebot4

COPY configs/turtlebot_setup.bash.template /etc/turtlebot4/setup.bash.template
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN printf '%s\n' \
    'source /etc/turtlebot4/setup.bash' \
    'source /root/docker-ws/turtlebot4_ws/install/setup.bash 2>/dev/null || true' \
    >> /root/.bashrc

WORKDIR /root/docker-ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
