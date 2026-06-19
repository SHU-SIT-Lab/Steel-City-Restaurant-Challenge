# ROS Jazzy Migration Report

Change log for the Humble → Jazzy migration. Every repo change during this
workstream is recorded here.

---

## 2026-06-19 — Migration start: Docker, workspace slim-down, package fixes

### Added

- `docs/report.md` — this migration journal
- `docker/Dockerfile` — Ubuntu 24.04 + ROS 2 Jazzy + TurtleBot4 desktop/navigation + competition deps
- `docker/entrypoint.sh` — robot IP prompt, writes `/etc/turtlebot4/setup.bash`, restarts ros2 daemon
- `docker/run_container.sh` — host wrapper with X11/GPU, robot IP prompt, optional `--build`
- `docker/.dockerignore` — excludes build artifacts and `.git`
- `configs/turtlebot_setup.bash.template` — discovery-server env template with `__ROBOT_IP__` placeholder
- `configs/waypoints.yaml` — named poses for restaurant navigation
- `turtlebot4_ws/README.md` — workspace build/run instructions
- `turtlebot4_ws/src/turtlebot4_steel_city_competition/src/navigation/restaurant_navigator.py` — Nav2 wrapper
- `turtlebot4_ws/src/turtlebot4_steel_city_competition/launch/restaurant_bringup.launch.py` — competition launch

### Changed

- `configs/turtlebot_setup.bash` — documented example; template is source of truth
- `turtlebot4_ws/.../launch/steel_city.launch.py` — fixed executable `turtlebot4_run.py`
- `turtlebot4_ws/.../package.xml` — added missing ROS deps
- `turtlebot4_ws/.../CMakeLists.txt` — install navigation module
- `turtlebot4_ws/.../src/turtlebot4_run.py` — wire navigation into coordinator ctx
- `turtlebot4_ws/.../src/helpers/config.py` — removed hardcoded OpenAI API key
- `scripts/speech/config.py` — removed hardcoded OpenAI API key
- `environment.yaml` — Python 3.12 conda env for scripts/ (ROS-free)
- `README.md` — Jazzy Docker workflow, corrected paths
- `docs/navigation.md` — navigation setup and usage
- `.gitignore` — explicit `turtlebot4_ws/{build,install,log}/`

### Removed

- `docker/run_docker.bash` — replaced by `docker/run_container.sh`
- `docker/save_docker.bash` — save workflow documented in README (`docker commit`)
- `turtlebot4_ws/src/turtlebot4/` — vendored Humble upstream (replaced by apt)
- `turtlebot4_ws/src/turtlebot4_robot/` — vendored Humble upstream
- `turtlebot4_ws/src/turtlebot4_simulator/` — vendored Humble upstream

### Notes

- `ros-jazzy-audio-common-msgs` is not available as a Debian package on Noble; competition code falls back to `std_msgs/UInt8MultiArray` when `audio_common_msgs` is missing.
- Build tools use Ubuntu packages `python3-colcon-common-extensions` and `python3-rosdep` rather than `ros-jazzy-ros-dev-tools`.
- `docker/entrypoint.sh` uses `set -eo pipefail` (not `-u`) so `/opt/ros/jazzy/setup.bash` can source cleanly.
- Dockerfile installs TurtleBot4 packages in two apt steps: desktop metapackage, then description/msgs/navigation/node explicitly.
- Container startup prints confirmation of `/etc/turtlebot4/setup.bash`, `/root/.bashrc`, and installed TurtleBot4 packages.

### Verify

```bash
docker build -t steel-city-jazzy:latest -f docker/Dockerfile .
./docker/run_container.sh --build 192.168.1.150
# Startup banner confirms setup.bash, .bashrc, and package list
cd turtlebot4_ws && colcon build --symlink-install && source install/setup.bash
ros2 topic list
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

Verified locally: Docker image builds; `colcon build` succeeds with one package.

## 2026-06-19 — Final polish: Docker docs and startup confirmation

### Changed

- `docker/Dockerfile` — explicit two-step apt install for all TurtleBot4 packages
- `docker/entrypoint.sh` — startup banner confirming setup.bash, bashrc, and package install
- `docker/run_container.sh` — accept `ROBOT_IP` as positional argument
- `README.md` — run/save Docker instructions, OPENAI_API_KEY section, Create 3 discovery web UI steps

### Removed

- `docker/run_docker.bash`
- `docker/save_docker.bash`
