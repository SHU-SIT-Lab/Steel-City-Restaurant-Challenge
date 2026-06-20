# Running the robot without Docker (native ROS 2 Jazzy in WSL)

A Docker-free way to run the TurtleBot4 stack. Because the robot is **ROS 2
Jazzy**, this uses a native **Ubuntu 24.04** WSL distro with the Jazzy apt
packages — RoboStack has no Jazzy, and the default WSL Ubuntu 26.04 is too new
for the Jazzy apt repo.

It reuses all the networking work from the Docker path (mirrored WSL networking,
the firewall rule, the discovery server, the FastDDS interface whitelist), so the
only thing that changes is *container → native distro*.

> Trade-off: this is a comparable-size install to the Docker image (a GB-ish apt
> download). It's not *less* work than Docker — it's *Docker-free*. Docker itself
> works today with the entrypoint LF fix (PR #16) if you prefer it.

## One-time setup

1. **Install the Noble distro** (PowerShell):
   ```powershell
   wsl --install -d Ubuntu-24.04 --no-launch
   ```

2. **Install ROS 2 Jazzy + TurtleBot4** (mirrors `docker/Dockerfile`):
   ```powershell
   wsl -d Ubuntu-24.04 -u root bash /mnt/c/<path-to-repo>/scripts/native/install_jazzy.sh
   ```

3. **Mirrored networking** — already global to WSL2 via `~/.wslconfig`
   (`networkingMode=mirrored`). See [wsl_host_setup.md](wsl_host_setup.md).

4. **Firewall rule** for the robot's subnet (once per network):
   `scripts/windows/allow-robot-subnet.ps1 -Subnet 192.168.8.0/24`.

5. **Build the competition workspace** (inside the distro, from the repo root):
   ```bash
   wsl -d Ubuntu-24.04 -u root
   cd /mnt/c/<path-to-repo>/turtlebot4_ws
   source /opt/ros/jazzy/setup.bash
   colcon build --symlink-install && source install/setup.bash
   ```

## Each session

Join the robot's Wi-Fi, then from the repo root inside the distro:
```bash
ROBOT_IP=192.168.8.111 bash scripts/native/run_native.sh
# inside the configured shell:
ros2 topic list                       # expect /scan, /oakd/*, /battery_state
ros2 topic echo /battery_state --once
```
`run_native.sh` sources Jazzy + the workspace, sets the discovery server, and
auto-generates the FastDDS interface whitelist for your current `192.168.8.x` IP
— the same fix the Docker entrypoint applies.

## Troubleshooting
Identical to the Docker path — "ping works but ROS sees nothing" is the firewall
+ DDS locator issue. See **[troubleshooting_dds_wsl.md](troubleshooting_dds_wsl.md)**.

## Files
| Path | Role |
| --- | --- |
| `scripts/native/install_jazzy.sh` | Install ROS 2 Jazzy + TurtleBot4 in the distro |
| `scripts/native/run_native.sh` | Source + configure discovery/whitelist + run |
| `docker/nav.env` | `ROBOT_IP` (shared with the Docker path) |
