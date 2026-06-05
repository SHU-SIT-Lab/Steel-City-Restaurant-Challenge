# Steel-City-Restaurant-Challenge

## Repository structure

```
Steel-City-Restaurant-Challenge/
├── configs/
│   └── config.yaml
├── data/
│   └── dataplaceholder.py
├── docker/
│   ├── run_docker.bash
│   └── save_docker.bash
├── docs/
│   └── readme.md
├── turtlebot_ws/
│   └── src/
│       ├── database/
│       ├── interfaces/
│       ├── navigation/
│       ├── speech/
│       ├── task_manager/
│       └── vision/
├── tests/
│   └── __init__.py
├── environment.yaml
└── README.md
```

## Setup

```bash
git clone git@github.com:SHU-SIT-Lab/Steel-City-Restaurant-Challenge.git
cd Steel-City-Restaurant-Challenge
```

Start the Docker container from the repository root:

```bash
./docker/run_docker.bash
```

The repository is mounted inside the Docker container at `/root/docker-ws`.
Because the ROS workspace is built inside Docker, create and activate the conda
environment inside the Docker container:

```bash
cd /root/docker-ws
conda env create -f environment.yaml
conda activate steel-city-restaurant
```

## Build the ROS workspace

After activating the environment inside Docker, build the ROS workspace:

```bash
cd /root/docker-ws/turtlebot_ws
colcon build --symlink-install
source install/setup.bash
```
