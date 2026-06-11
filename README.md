# Steel-City-Restaurant-Challenge

Codebase for the [Steel City Restaurant Challenge](https://sitlabresearch.uk/research/robotics-challenge/) — a RoboCup-inspired service robotics competition at Sheffield Hallam University.

## Repository structure

Python modules live under `scripts/`. Each subdirectory maps to a competition component and has its own documentation in `docs/`. Robot control runs through the ROS 2 workspace in `turtlebot_ws/`.

```
Steel-City-Restaurant-Challenge/
├── configs/
│   └── config.yaml
├── data/
│   └── dataplaceholder.py
├── docker/
│   ├── run_docker.bash
│   └── save_docker.bash
├── docs/              # documentation for individual modules
├── scripts/
│   ├── __init__.py
│   ├── database/
│   ├── interfaces/
│   ├── navigation/
│   ├── speech/
│   ├── task_manager/
│   └── vision/
├── tests/
│   └── __init__.py
├── turtlebot_ws/
│   └── src/
├── environment.yaml
├── LICENSE
└── README.md
```

## Setup

Clone the repository:

```bash
git clone git@github.com:SHU-SIT-Lab/Steel-City-Restaurant-Challenge.git
cd Steel-City-Restaurant-Challenge
```

If you are working with ROS, skip to [Working with ROS](#working-with-ros).

## Environment

Create and activate the conda environment from the repository root:

```bash
conda env create -f environment.yaml
conda activate steel-city-restaurant
```

Use this when working on Python components outside Docker.

To update `environment.yaml` after installing new packages:

```bash
conda env export --from-history --no-builds > environment.yaml
```

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


| Module       | Docs                                           |
| ------------ | ---------------------------------------------- |
| Database     | [docs/database.md](docs/database.md)           |
| Interfaces   | [docs/interfaces.md](docs/interfaces.md)       |
| Navigation   | [docs/navigation.md](docs/navigation.md)       |
| Speech       | [docs/speech.md](docs/speech.md)               |
| Task Manager | [docs/task_manager.md](docs/task_manager.md)   |
| Vision       | [docs/vision.md](docs/vision.md)               |


