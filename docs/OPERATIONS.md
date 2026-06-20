# Operations runbook — running the robot from a Windows + WSL2 laptop

End-to-end guide to drive the TurtleBot4 from a Windows laptop (the "host") over
Wi-Fi. Start here. Component details are linked at the bottom.

## What runs where

| | Runs on | Provides |
| --- | --- | --- |
| **Robot** (TurtleBot4 RPi + Create 3) | the robot | sensors (`/scan`, `/oakd/*`), base, **FastDDS discovery server** on `:11811`, the competition bringup |
| **Host** (this laptop) | Windows → WSL2 → Docker (`steel-city-jazzy`) | Nav2, RViz, the waiter behaviors, the webapp |

The two talk over Wi-Fi via the **discovery server** (unicast — no multicast
needed). The host connects as a FastDDS *super client* pointed at the robot's IP.

---

## A. One-time host setup (do once per laptop)

Full commands: **[wsl_host_setup.md](wsl_host_setup.md)**. In short:

1. **Mirrored networking.** Copy `scripts/windows/wslconfig.example` to
   `C:\Users\<you>\.wslconfig`, then in PowerShell: `wsl --shutdown`.
2. **Docker + GPU in WSL** (Ubuntu, runs as root):
   ```bash
   apt-get update && apt-get install -y docker.io
   systemctl enable --now docker
   # NVIDIA Container Toolkit (see wsl_host_setup.md for the apt repo lines)
   ```
3. **Build the image** (from the repo root inside WSL, ~20-40 min once):
   ```bash
   docker build -t steel-city-jazzy:latest -f docker/Dockerfile .
   ```

Verify: `docker run --rm --gpus all ubuntu:24.04 nvidia-smi -L` lists the GPU.

---

## B. Each session (get the robot talking)

### 1. Join the robot's Wi-Fi
Connect the **laptop** to the same Wi-Fi as the robot. Confirm the laptop got an
address on the robot's subnet:
```bash
wsl hostname -I          # should include an address on the robot's subnet
```

### 2. Allow that subnet through the firewall (once per robot network)
In PowerShell, from the repo's `scripts/windows/`:
```powershell
powershell -ExecutionPolicy Bypass -File allow-robot-subnet.ps1 -Subnet 192.168.8.0/24
```
Use the robot's actual subnet (e.g. `10.253.0.0/16` on a different network).
Approve the UAC prompt. **Skip this and ROS will see nothing even though ping
works** — see Troubleshooting.

### 3. Set the robot IP
Edit `docker/nav.env` → `ROBOT_IP=<robot-ip>` (or pass it as an argument to the
run script). Confirm reachability:
```bash
wsl ping <robot-ip>      # should reply, low latency
```

### 4. Launch the container
```bash
./docker/run_container_wsl.sh        # uses ROBOT_IP from nav.env
```
The entrypoint writes the discovery-server config and **auto-pins FastDDS to the
laptop's interface on the robot subnet** (the interface whitelist), then starts.

### 5. Verify
Inside the container:
```bash
ros2 topic list                       # expect ~39 topics: /scan, /oakd/*, /battery_state ...
ros2 topic echo /battery_state --once # sanity check
```
If you see only `/parameter_events` and `/rosout`, go to Troubleshooting.

---

## C. Running navigation / the competition

1. Bring up localization + Nav2 against the saved map, set the initial pose in
   RViz, then launch the stack. Full steps: **[navigation.md](navigation.md)**.
2. Online furniture (tables/chairs) avoidance from the OAK-D depth camera:
   **[furniture_costmap.md](furniture_costmap.md)**.
3. How the robot decides what to do (the behavior system):
   **[task_manager.md](task_manager.md)**.

> **Map note:** autonomous nav needs `maps/restaurant.yaml`/`.pgm`. If `maps/`
> only has `README.md`, build the map with SLAM first or copy in the team map —
> reading sensors/battery does not need it.

---

## D. Troubleshooting — "ping works but ROS sees nothing"

This is the #1 issue and it has a known cause. The robot is up, the network is
fine, but **DDS (inbound UDP) is blocked or mis-routed**. In order:

1. **Firewall.** Did you run `allow-robot-subnet.ps1` for *this* network's
   subnet? Confirm inbound UDP actually arrives:
   ```bash
   # on the laptop (WSL), listen:
   python3 -c "import socket;s=socket.socket(2,2);s.bind(('0.0.0.0',9999));print(s.recvfrom(64))"
   # on the robot (ssh in), fire:
   echo -n hi > /dev/udp/<laptop-ip>/9999
   ```
   No packet received ⇒ firewall rule missing/wrong subnet.
2. **Interface whitelist.** The entrypoint auto-pins FastDDS to the laptop's
   robot-subnet IP. If the laptop has VPNs/extra adapters and discovery still
   fails, confirm `FASTRTPS_DEFAULT_PROFILES_FILE` is set in the container and
   points at a whitelist with the *current* IP.
3. **Mirrored networking.** `wsl hostname -I` must show the robot-subnet address,
   not just `172.x`. If not, `.wslconfig` mirrored mode isn't active — re-copy it
   and `wsl --shutdown`.
4. **Robot side.** `ssh` in and run `ros2 node list` — it should show ~24 nodes.
   If empty, the robot's bringup is down (restart `turtlebot4.service`).

Full diagnosis and the underlying root cause: **[troubleshooting_dds_wsl.md](troubleshooting_dds_wsl.md)**.

---

## Document index

| Topic | Doc |
| --- | --- |
| **This runbook** | OPERATIONS.md |
| Windows/WSL host setup | [wsl_host_setup.md](wsl_host_setup.md) |
| Windows helper scripts | [../scripts/windows/README.md](../scripts/windows/README.md) |
| DDS-over-WiFi troubleshooting | [troubleshooting_dds_wsl.md](troubleshooting_dds_wsl.md) |
| Navigation (map, Nav2, waypoints) | [navigation.md](navigation.md) |
| Online furniture costmap (OAK-D) | [furniture_costmap.md](furniture_costmap.md) |
| Behavior system (task manager) | [task_manager.md](task_manager.md) |
| Database / Speech / Vision / Interfaces | [database.md](database.md) · [speech.md](speech.md) · [vision.md](vision.md) · [interfaces.md](interfaces.md) |
| Active-inference reformulation (research/WIP) | [aif_design.md](aif_design.md) |
| ROS Jazzy migration log | [report.md](report.md) |
