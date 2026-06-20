# Steel-City-Restaurant-Challenge

Codebase for the [Steel City Restaurant Challenge](https://sitlabresearch.uk/research/robotics-challenge/) — a RoboCup-inspired service robotics competition at Sheffield Hallam University.

## Repository structure

Python modules live under `scripts/`. Each subdirectory maps to a competition component and has its own documentation in `docs/`. Robot control runs through the ROS 2 workspace in `turtlebot4_ws/`.

```
Steel-City-Restaurant-Challenge/
├── configs/
│   ├── config.yaml
│   ├── waypoints.yaml
│   └── turtlebot_setup.bash.template
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── run_container.sh
├── docs/
│   └── report.md          # migration / change log
├── scripts/
├── turtlebot4_ws/
│   └── src/
│       └── turtlebot4_steel_city_competition/
├── environment.yaml
└── README.md
```

## Requirements

- **Ubuntu 24.04** host for Docker (recommended)
- **ROS 2 Jazzy** + **TurtleBot4** with Create 3 firmware `I.*.`* (FastDDS)
- TurtleBot4 RPi configured as a Discovery Server (`turtlebot4-setup`, port 11811)

See [TurtleBot4 Jazzy setup](https://turtlebot.github.io/turtlebot4-user-manual/setup/basic.html).

## Setup

Clone the repository:

```bash
git clone git@github.com:SHU-SIT-Lab/Steel-City-Restaurant-Challenge.git
cd Steel-City-Restaurant-Challenge
```

## Environment (non-ROS scripts)

For laptop development of `scripts/` components outside Docker:

```bash
conda env create -f environment.yaml
conda activate steel-city-restaurant
```

## OpenAI API key

LLM and speech features require an OpenAI API key. Set it before launching competition nodes or running `scripts/speech/`:

```bash
export OPENAI_API_KEY="your-key-here"
```

Inside Docker, export it in the same shell before running nodes, or add the line above to your host shell before starting the container so you can paste it once inside:

```bash
export OPENAI_API_KEY="your-key-here"
./docker/run_container.sh 192.168.1.150
```

Do not commit API keys to the repository.

## Working with ROS (Docker)

### Build the image

From the repository root:

```bash
docker build -t steel-city-jazzy:latest -f docker/Dockerfile .
```

The image installs:

- `ros-jazzy-turtlebot4-desktop`
- `ros-jazzy-turtlebot4-description`
- `ros-jazzy-turtlebot4-msgs`
- `ros-jazzy-turtlebot4-navigation`
- `ros-jazzy-turtlebot4-node`

### Run the container

Pass the TurtleBot4 RPi Wi-Fi IP as an argument:

```bash
./docker/run_container.sh 192.168.1.150
```

Build and run in one step:

```bash
./docker/run_container.sh --build 192.168.1.150
```

If you omit the IP, the script prompts for it interactively:

```bash
./docker/run_container.sh
```

On startup the container:

1. Writes `/etc/turtlebot4/setup.bash` for discovery-server connectivity
2. Sources ROS Jazzy from `/root/.bashrc`
3. Prints a confirmation of both configurations and the installed TurtleBot4 packages

### Save the container

After installing extra tools or packages inside a running container, save the modified state back to an image:

```bash
docker commit steel-city-dev steel-city-jazzy:latest
```

**Note:** `docker commit` saves `/etc/turtlebot4/setup.bash` with the current discovery-server IP. After committing, always recreate the container with `./docker/run_container.sh <robot-ip>` (do not rely on `docker start` alone) so the entrypoint regenerates `setup.bash` for the correct robot address.

Or save under a new tag:

```bash
docker commit steel-city-dev steel-city-jazzy:my-save
```

Rebuild from the Dockerfile when you change repository Docker files rather than relying on a saved container.

### Working with ROS (Docker)

See **[docs/navigation.md](docs/navigation.md)** for the full navigation guide: competition map usage, localization, waypoints, and the waypoint GUI helper.

Quick start:

```bash
./docker/run_container.sh 192.168.4.239
cd turtlebot4_ws && colcon build --symlink-install && source install/setup.bash
```

Then follow the competition workflow in the navigation guide.


## Documentation


| Module       | Docs                                         |
| ------------ | -------------------------------------------- |
| Database     | [docs/database.md](docs/database.md)         |
| Interfaces   | [docs/interfaces.md](docs/interfaces.md)     |
| Navigation   | [docs/navigation.md](docs/navigation.md)     |
| Speech       | [docs/speech.md](docs/speech.md)             |
| Task Manager | [docs/task_manager.md](docs/task_manager.md) |
| Vision       | [docs/vision.md](docs/vision.md)             |
| Migration    | [docs/report.md](docs/report.md)             |


