# Steel-City-Restaurant-Challenge

Codebase for the [Steel City Restaurant Challenge](https://sitlabresearch.uk/research/robotics-challenge/) — a RoboCup-inspired service robotics competition at Sheffield Hallam University.

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
│   ├── database/
│   ├── interfaces/
│   ├── navigation/
│   ├── speech/
│   ├── task_manager/
│   └── vision/
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

Clone the repository:

```bash
git clone git@github.com:SHU-SIT-Lab/Steel-City-Restaurant-Challenge.git
cd Steel-City-Restaurant-Challenge
```

## Environment

Create and activate the conda environment from the repository root:

```bash
conda env create -f environment.yaml
conda activate steel-city-restaurant
```

Use this when working on Python components outside Docker. If you are using ROS, create and activate the environment inside the Docker container instead (see below).

## Working with ROS

ROS development runs inside Docker. From the repository root:

1. Start the container:
  ```bash
   ./docker/run_docker.bash
  ```
2. Go to the mounted repository:
  ```bash
   cd /root/docker-ws
  ```
3. Create and activate the conda environment:
  ```bash
   conda env create -f environment.yaml
   conda activate steel-city-restaurant
  ```
4. Build the ROS workspace (first time only):
  ```bash
   cd turtlebot_ws
   colcon build --symlink-install
   source install/setup.bash
  ```

## Documentation


| Module       | Docs                                                       |
| ------------ | ---------------------------------------------------------- |
| Database     | [docs/database/README.md](docs/database/README.md)         |
| Interfaces   | [docs/interfaces/README.md](docs/interfaces/README.md)     |
| Navigation   | [docs/navigation/README.md](docs/navigation/README.md)     |
| Speech       | [docs/speech/README.md](docs/speech/README.md)             |
| Task Manager | [docs/task_manager/README.md](docs/task_manager/README.md) |
| Vision       | [docs/vision/README.md](docs/vision/README.md)             |


