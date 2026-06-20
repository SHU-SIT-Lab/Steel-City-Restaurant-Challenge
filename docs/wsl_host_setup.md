# Running the stack from Windows + WSL2

How to use a Windows laptop (via WSL2) as the Docker host that drives the
TurtleBot4, instead of a dedicated Linux PC. Verified on Windows 11 (build
26200) + WSL2 Ubuntu 26.04, NVIDIA RTX GPU, WSLg.

## Why WSL2 works here

- The stack runs in an `ubuntu:24.04` Docker image, so the WSL host distro
  version does not matter for ROS Jazzy.
- The robot uses a **Discovery Server** (unicast to `ROBOT_IP:11811`), which
  tolerates WSL2 networking far better than multicast discovery.
- **Mirrored networking** (below) gives the WSL VM the Windows IP, so the robot
  can route ROS traffic back to this node — the missing piece in default NAT.
- **WSLg** provides X11/Wayland, so RViz and the waypoint GUI render with no
  X-server install.

## One-time setup

1. **Mirrored networking** — create `C:\Users\<you>\.wslconfig`:

   ```ini
   [wsl2]
   networkingMode=mirrored
   dnsTunneling=true
   firewall=true
   autoProxy=true

   [experimental]
   hostAddressLoopback=true
   ```

   Apply: `wsl --shutdown` (PowerShell), then reopen WSL. Verify with
   `hostname -I` — it should list the Windows interfaces, not just a `172.x` IP.

2. **Docker Engine** (inside WSL, runs as root):

   ```bash
   apt-get update && apt-get install -y docker.io
   systemctl enable --now docker
   docker run --rm hello-world
   ```

3. **NVIDIA Container Toolkit** (for `--gpus all`; the repo is codename-agnostic
   so it installs on Ubuntu 26.04):

   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
     | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
     | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
     > /etc/apt/sources.list.d/nvidia-container-toolkit.list
   apt-get update && apt-get install -y nvidia-container-toolkit
   nvidia-ctk runtime configure --runtime=docker
   systemctl restart docker
   docker run --rm --gpus all ubuntu:24.04 nvidia-smi -L   # should list the GPU
   ```

## Build + run

```bash
# from the repo root inside WSL (the repo lives on /mnt/c/...):
docker build -t steel-city-jazzy:latest -f docker/Dockerfile .   # ~20-40 min first time
./docker/run_container_wsl.sh                                    # WSLg GUI + GPU + nav.env IP
```

Use `run_container_wsl.sh` (not `run_container.sh`) on WSL — it drops the
`xhost`/`xauth` X11 dance and mounts `/mnt/wslg` for WSLg instead.

## Competition day

1. Connect the **laptop's Wi-Fi to the robot's network** (the `192.168.8.x`
   AP). Confirm: `ping 192.168.8.111` from WSL succeeds.
2. `./docker/run_container_wsl.sh` (picks up `ROBOT_IP` from `docker/nav.env`).
3. Inside the container, build the workspace and bring up the stack per
   `docs/navigation.md`.

## Gotchas

- If `ping` to the robot fails after joining its Wi-Fi, re-check mirrored mode
  is active (`hostname -I` shows the `192.168.8.x` address) and that Windows
  Firewall is not blocking — `firewall=true` in `.wslconfig` lets WSL share the
  Windows firewall rules.
- Mirrored mode applies only after `wsl --shutdown`. A reboot also works.
- The OAK-D point cloud for online furniture detection is a separate concern —
  see [furniture_costmap.md](furniture_costmap.md).
