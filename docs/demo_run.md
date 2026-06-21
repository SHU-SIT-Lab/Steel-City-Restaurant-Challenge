# Competition Demo Run Guide

Use this guide on competition day. All PC-side commands run inside the **`steel-city-dev`** Docker container unless noted.

## Prerequisites

| Item | Location / value |
|------|------------------|
| Robot IP | `192.168.4.239` (SSH: `ubuntu@192.168.4.239`, password: `turtlebot4`) |
| Docker container | `steel-city-dev` via `./docker/run_container.sh 192.168.4.239` |
| Map | `maps/home.yaml` + `maps/home.pgm` (must match where waypoints were recorded) |
| Waypoints | `configs/waypoints.yaml` |
| OpenAI key | `export OPENAI_API_KEY=...` inside Docker |
| Firestore | `configs/security_key.json` must exist |

---

## Quick start (15 minutes)

### 1. Start Docker on your laptop

From the repo root on your **host** (not inside Docker):

```bash
cd /path/to/Steel-City-Restaurant-Challenge
./docker/run_container.sh 192.168.4.239
```

If you changed Docker dependencies, rebuild once:

```bash
./docker/run_container.sh 192.168.4.239 --build
```

### 2. Build the workspace (first time or after code changes)

Inside the container:

```bash
cd /root/docker-ws/turtlebot4_ws
colcon build --symlink-install
source install/setup.bash
```

Also add to every new terminal:

```bash
source /etc/turtlebot4/setup.bash
source /root/docker-ws/turtlebot4_ws/install/setup.bash
```

### 3. Fix map filenames and generate Nav2 params (if needed)

```bash
/root/docker-ws/scripts/nav/fix_map_names.sh
python3 /root/docker-ws/scripts/nav/apply_nav2_competition.py   # inside Docker, ROS sourced
python3 /root/docker-ws/scripts/nav/normalize_waypoints.py
```

**Map selection:** `MAP_FILE` in [`docker/nav.env`](../docker/nav.env) defaults to `maps/home.yaml` because current waypoints were recorded on that map. If the laser scan aligns with a different map in RViz, set `MAP_FILE` to that map and re-record waypoints.

```bash
export MAP_FILE=/root/docker-ws/maps/home.yaml   # or restaurant.yaml
```

### 4. Start robot bringup (on the TurtleBot4)

SSH to the robot:

```bash
ssh ubuntu@192.168.4.239
ros2 launch turtlebot4_bringup robot.launch.py
```

**Important:** Undock the robot — the OAK-D camera is disabled while docked.

Leave this running for the whole session.

### 5. Verify ROS connectivity (Docker)

```bash
ros2 topic list
```

You should see `/scan`, `/odom`, and `/oakd/...` topics. If the list is nearly empty, recreate Docker with the correct robot IP.

Print the startup checklist:

```bash
/root/docker-ws/docker/start_competition_stack.sh
```

---

## Navigation setup (required before any demo)

**Do NOT run SLAM on competition day.** Use the saved map with AMCL.

### Terminal A — Localization + RViz

```bash
source /etc/turtlebot4/setup.bash
source /root/docker-ws/turtlebot4_ws/install/setup.bash
/root/docker-ws/scripts/nav/launch_localization.sh
```

## Discovery server (Docker vs robot)

Navigation **must run in Docker**, not on the robot. On the robot, only run `robot.launch.py`.

Docker talks to the robot through the **FastDDS discovery server** on the RPi (`ROBOT_IP:11811`). Nav2 nodes must use a **CLIENT** profile (`ROS_SUPER_CLIENT=false`). The old setup used `ROS_SUPER_CLIENT=true` for everything, which breaks costmap publishing in Docker while the same stack works on the robot.

After pulling these fixes, **recreate the container** so FastDDS XML is generated for your robot IP:

```bash
./docker/run_container.sh 192.168.4.239
```

Then verify:

```bash
./scripts/trial/verify_docker_nav.sh
```

**Do not launch Nav2 twice** (common cause of no costmap / robot moves briefly then stops). If unsure, run:

```bash
/root/docker-ws/scripts/nav/stop_navigation_stack.sh
```

**Do not add an Image/camera display in RViz** — it often crashes Docker. Use the waypoint GUI or `view_camera.sh` instead (see below).

### Set initial pose in RViz

1. In RViz, click **2D Pose Estimate**
2. Click where the robot actually is on the map
3. Drag to set heading
4. Confirm the **laser scan** aligns with walls on the map

Repeat if the scan drifts or after moving the robot by hand.

### Terminal B — Nav2

Wait until `/amcl_pose` is publishing, then:

```bash
source /etc/turtlebot4/setup.bash
source /root/docker-ws/turtlebot4_ws/install/setup.bash
/root/docker-ws/scripts/nav/launch_nav2.sh
```

If costmaps do not appear within ~30 seconds (FastDDS + discovery server), retry activation:

```bash
/root/docker-ws/scripts/nav/activate_nav2.sh
```

If goals produce **no path**, run:

```bash
./scripts/trial/diagnose_nav2_goal.sh
```

Verify Nav2 is ready:

```bash
ros2 action list | grep navigate_to_pose
ros2 run tf2_ros tf2_echo map base_link
```

### Test RViz navigation goal

In RViz, use **Nav2 Goal** (click goal, drag heading). The robot should plan and move.

If goals fail:
- SLAM still running? Stop it and use localization instead
- Initial pose wrong? Re-estimate in RViz
- Nav2 not running? Launch `competition_nav2.launch.py`

---

## Waypoint GUI (camera + teleop + Go)

**Camera:** Do not enable camera in RViz. Use one of these instead:

```bash
cd /root/docker-ws
python3 scripts/nav/record_waypoints.py
# or
./scripts/nav/view_camera.sh
```

Full GUI with teleop and navigation:

```bash
source /etc/turtlebot4/setup.bash
source /root/docker-ws/turtlebot4_ws/install/setup.bash
cd /root/docker-ws
python3 scripts/nav/record_waypoints.py
```

| Panel | What to check |
|-------|---------------|
| Camera | Enable checkbox on; status should show `live (/oakd/...)` |
| Pose | Should show AMCL source after localization |
| Navigate | Pick waypoint, press **Go** (requires nav server in step below) |
| Teleop | Arrow keys to fine-tune poses; click focus banner if keys stop |

### Record missing waypoints

Run `python3 scripts/nav/normalize_waypoints.py` if keys look wrong (`table1` vs `table_1`).

Placeholder `table_4` and `table_5` may need recording on-site:

- Drive the robot there with teleop → select POI → **Save current pose**

Verify `table_1` and `table_2` are distinct if they are different physical tables.

---

## Full competition demo stack

### Terminal C — Behaviors + LLM + audio

```bash
source /etc/turtlebot4/setup.bash
source /root/docker-ws/turtlebot4_ws/install/setup.bash
export OPENAI_API_KEY="your-key-here"
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py enable_laptop_audio:=true
```

This starts:
- Navigation server (`/navigation/navigate_to_waypoint`)
- Behavior coordinator (vision, STT, TTS, Firestore, LLM order-taking)
- Laptop mic publisher (`/audio`) and speaker subscriber (`/audio_output`)

If laptop audio fails, list devices inside Docker:

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
export SPEAKER_DEVICE_ID=0   # pick your output device index
export MIC_DEVICE_INDEX=1    # pick your mic index
```

---

## Preflight checks

```bash
cd /root/docker-ws
python3 scripts/trial/run_unit_tests.py          # no robot required
./scripts/trial/preflight_verify.sh              # includes unit tests + DB
./scripts/trial/diagnose_nav2_goal.sh
./scripts/trial/verify_navigation.sh
python3 scripts/trial/validate_waypoints.py
```

---

## Demo flow (autonomous)

Reset database state before a demo run:

```bash
python3 scripts/trial/behavior_triggers.py reset
```

Expected flow:

1. Robot checks entrance for customers (vision)
2. Asks party size (speech)
3. Seats customers at an empty table
4. Takes order via LLM at the table
5. Marks order ready (auto or manual kitchen script)
6. Collects order at barista, delivers to table

Manual kitchen override:

```bash
python3 scripts/trial/kitchen_mark_ready.py 0
```

Manual behavior triggers (fallback):

```bash
python3 scripts/trial/behavior_triggers.py --help
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| RViz goals — no path | Same map as waypoints (`MAP_FILE=home.yaml`); 2D Pose Estimate; goal in free cell; run `diagnose_nav2_goal.sh` |
| No costmap / heatmap in RViz | Launch localization first; run `stop_navigation_stack.sh` if Nav2 was started twice; then `activate_nav2.sh` |
| RViz crashes when camera enabled | **Do not use Image in RViz**; use `record_waypoints.py` or `view_camera.sh` |
| RViz goals do nothing (path shows, no move) | Check `/cmd_vel` types; undock robot; ensure Nav2 launched only once; read Nav2 terminal |
| Nav2 on robot + Docker both running | Stop robot-side nav; use Docker only (`launch_localization.sh` + `launch_nav2.sh`) |
| Camera topic exists but GUI blank | Undock robot; QoS is now fixed — restart GUI |
| `ros2 topic hz /oakd/...` — not published yet | **Robot docked** or OAK-D driver stopped — run `./scripts/nav/undock_robot.sh` then `./scripts/nav/diagnose_camera.sh` |
| No `/oakd/*` in `ros2 topic list` | Undock robot; if still missing on robot SSH, `sudo turtlebot4-service-restart` (Jazzy power_save bug) |
| No ROS topics in Docker | Recreate container: `./docker/run_container.sh 192.168.4.239` |
| Nav service waiting in GUI | Launch `steel_city.launch.py` |
| **Go** sends robot to wrong place | Re-record waypoint; confirm localization not SLAM |
| No speech / LLM errors | Set `OPENAI_API_KEY`; check mic with `ros2 topic hz /audio` |
| Map won't load | Run `scripts/nav/fix_map_names.sh` |

---

## Terminal layout (recommended)

| Terminal | Where | Command |
|----------|-------|---------|
| 1 | Robot SSH | `robot.launch.py` |
| 2 | Docker | `competition_localization.launch.py` |
| 3 | Docker | `competition_nav2.launch.py` |
| 4 | Docker | `steel_city.launch.py enable_laptop_audio:=true` |
| 5 | Docker | `record_waypoints.py` (when tuning) |

---

## Mapping (pre-competition only — not on demo day)

If you need to rebuild the map before the event:

```bash
# Docker
ros2 launch turtlebot4_navigation slam.launch.py params:=/root/docker-ws/configs/slam.yaml

# After driving the robot around:
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "name: {data: '/root/docker-ws/maps/restaurant'}"
```

Then run `fix_map_names.sh`, switch to localization mode, and re-record all waypoints.
