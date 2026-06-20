# DEPLOY — on-site checklist

One page for whoever's at the robot. Goal: bring the TurtleBot4 up on the chosen
brain (reactive / active-inference / AIF + law-as-code). Work top to bottom;
most steps are one-time and stay done.

Robot IP: **192.168.8.111** · its Wi-Fi subnet: **192.168.8.x** · host: this
Windows laptop + WSL2 (Ubuntu 24.04 distro with ROS 2 Jazzy).

> This assumes the deploy stack is merged to `main`. Until then the helpers are
> spread across branches: firewall/DDS helpers (`scripts/windows/`, the
> troubleshooting/OPERATIONS docs) on **PR #16**, the native runtime
> (`install_jazzy.sh`, `run_without_docker.md`) on **PR #21**, the AIF integration
> + `deploy.sh` on **PR #24**.

---

## 0. One-time setup (do once per laptop; skip if already done)

- [ ] **WSL mirrored networking** — `~/.wslconfig` has `networkingMode=mirrored`,
      then `wsl --shutdown` once. (`scripts/windows/wslconfig.example`.)
- [ ] **WSL PATH fix** — inside the distro, `/etc/wsl.conf` has
      `[interop]\nappendWindowsPath=false`, then `wsl --shutdown`. Without it ROS's
      `setup.bash` breaks (empty `AMENT_PREFIX_PATH`).
- [ ] **ROS 2 Jazzy installed** — `bash scripts/native/install_jazzy.sh`
      (~420 pkgs incl. turtlebot4). One-time, slow.
- [ ] **Firewall rule** — allow the robot subnet inbound (UAC-elevated PowerShell):
      `scripts/windows/allow-robot-subnet.ps1`. This is the usual cause of
      "ping works but ROS sees nothing".

---

## 1. Join the network

- [ ] Connect the laptop to the **robot's Wi-Fi** (192.168.8.x). Use **5 GHz** if
      offered — 2.4 GHz adds lag.
- [ ] Power on the robot; wait for its Create 3 / RPi to boot (~1–2 min).
- [ ] **Ping it:** `ping 192.168.8.111` → replies. If not, you're on the wrong
      Wi-Fi or the robot isn't up. Stop here until ping works.

---

## 2. Launch (one command)

From the repo root, **inside the Ubuntu 24.04 WSL distro**:

```bash
cd /mnt/c/Users/mahau/OneDrive/Desktop/projects/Steel-City-Restaurant-Challenge
scripts/native/deploy.sh aif-law      # AIF + law-as-code multi-customer ordering
#                        aif           # AIF, no law (FIFO)
#                        reactive      # the original reactive coordinator
```

`deploy.sh` installs deps (jax+pymdp), builds the workspace, configures the
discovery server + FastDDS Wi-Fi whitelist, sets the brain flags, runs a 5-second
robot-topic check, and launches.

> **First run is slow** (~several min): jax install + `colcon build` + JAX's first
> XLA compile at node start. **Subsequent runs:** `BUILD=0 DEPS=0 scripts/native/deploy.sh aif-law`
> is fast. To set up without launching (to inspect the env): `NO_LAUNCH=1 ... `.

---

## 3. Verify it's up

- [ ] The 5-second check prints **"robot topics visible — good."**
      (else see Gotchas.)
- [ ] The AIF node logs **`AIF coordinator ready (EFE selection; table choice: …)`**.
- [ ] In another WSL shell (after sourcing — easiest: `NO_LAUNCH=1 scripts/native/deploy.sh aif`):
      `ros2 topic list` shows `/scan`, `/oakd/*`, `/battery_state`;
      `ros2 topic echo /battery_state --once` shows a sane percentage.

---

## 4. Gotchas (first-run, most-likely first)

| Symptom | Fix |
| --- | --- |
| **Ping works, ROS sees nothing** | (1) Windows **firewall** — run `scripts/windows/allow-robot-subnet.ps1` (elevated). (2) Wrong interface — `deploy.sh` pins FastDDS to the 192.168.8.x NIC; if it warned "no interface on 192.168.8.x", you're not on the robot's Wi-Fi. See `docs/troubleshooting_dds_wsl.md`. |
| **`AMENT_PREFIX_PATH` empty / packages not found** | `/etc/wsl.conf` `appendWindowsPath=false` not applied → `wsl --shutdown`, reopen. (deploy.sh's eval-sourcing usually dodges this.) |
| **`colcon build` fails on a missing dep** | `cd turtlebot4_ws && rosdep install --from-paths src --ignore-src -y`, then re-run. |
| **`pip install` jax fails (externally-managed env)** | deploy.sh already uses `--break-system-packages`; if it still fails, check internet on the robot Wi-Fi (may be captive/offline — pre-install jax before going on-site). |
| **Node start hangs for a minute** | Normal — JAX's first XLA compile. It proceeds after. |
| **Robot drives but mis-detects furniture** | separate concern — see `docs/furniture_costmap.md` (online OAK-D costmap). |
| **Want to fall back fast** | `Ctrl-C`, then `scripts/native/deploy.sh reactive BUILD=0 DEPS=0` — the proven baseline. |

---

## 5. Quick reference

```bash
# full first run, AIF + law
scripts/native/deploy.sh aif-law
# fast re-launch (already built)
BUILD=0 DEPS=0 scripts/native/deploy.sh aif-law
# baseline reactive
BUILD=0 DEPS=0 scripts/native/deploy.sh reactive
```

The brain flags (what deploy.sh sets): `AIF_COORDINATOR=1` → active inference;
`AIF_LAW=1` → law-as-code ordering. Both unset → reactive. Details:
`docs/aif_ros_integration.md`. Architecture: `docs/aif_architecture.md`.
Operator background: `docs/OPERATIONS.md`.
