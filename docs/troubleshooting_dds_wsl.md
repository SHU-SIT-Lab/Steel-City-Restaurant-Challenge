# Troubleshooting: robot invisible over Wi-Fi from a WSL2 Docker host

**Symptom.** `ping 192.168.8.111` works (low latency, 0% loss) and `ssh` into the
robot works, but from the laptop's Docker container `ros2 topic list` shows only
the 2 local topics (`/parameter_events`, `/rosout`) and `ros2 node list` is
empty — for **every** `ROS_DOMAIN_ID` and with **both** discovery server and
simple discovery. On the robot itself `ros2 node list` shows all ~24 nodes, so
the robot is fine.

**Root cause — two stacked problems.** ICMP (ping) and outbound TCP (SSH) work,
but **DDS discovery needs the robot to initiate UDP back to the laptop**, and
that was failing for two independent reasons:

1. **Windows Firewall dropped unsolicited inbound UDP.** The competition Wi-Fi
   (`EMSRC`) is classified as a **Public** network, whose default inbound action
   is Block. The robot's discovery replies never reached the laptop. (`firewall=false`
   in `.wslconfig` was *not* enough — the host Windows Defender Firewall drops the
   packet before it is mirrored into the WSL VM.)

2. **DDS locator pollution.** The laptop has several interfaces — Wi-Fi
   `192.168.8.x`, Docker `172.17.0.1`, Tailscale `100.81.x`, corporate `10.91.x`.
   FastDDS advertises **all** of them as locators, so the robot's discovery
   server tries to answer on interfaces it cannot route to.

## How it was diagnosed

- `ros2 node list` **on the robot** (via SSH) → 24 nodes ⇒ robot is publishing.
- `ss -ulpn | grep 11811` on the robot → `0.0.0.0:11811` ⇒ discovery server is
  reachable on all interfaces, not bound to localhost.
- **Inbound UDP probe:** listen on the laptop (`udp/9999`), have the robot send a
  datagram to it (`echo -n HELLO > /dev/udp/<laptop-ip>/9999`). Before the fix:
  timeout (blocked). After the firewall rule: received. This isolates the
  firewall problem from the ROS problem.

## The fix

### 1. Allow inbound from the robot subnet (Windows, admin, persistent)

```powershell
New-NetFirewallRule -DisplayName "ROS2 DDS robot subnet" -Direction Inbound `
    -Action Allow -RemoteAddress 192.168.8.0/24 -Profile Any -Enabled True
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

Scoped to the competition subnet only (not the internet). Persists across
reboots. Remove with `Remove-NetFirewallRule -DisplayName "ROS2 DDS robot subnet"`.

### 2. Pin FastDDS to the Wi-Fi interface (interface whitelist)

A FastDDS profile that whitelists only the laptop's `192.168.8.x` address (plus
`127.0.0.1`) stops the locator pollution. `docker/entrypoint.sh` now **generates
this automatically** at container start: it finds the laptop's IP on the robot's
subnet and writes `/etc/turtlebot4/fastdds_wifi.xml`, then exports
`FASTRTPS_DEFAULT_PROFILES_FILE`. No per-machine editing needed.

## Verify

```bash
./docker/run_container_wsl.sh        # entrypoint pins the interface + discovery server
# inside the container:
ros2 topic list                      # ~39 topics: /battery_state, /scan, /oakd/...
ros2 topic echo /battery_state --once
```

## Notes

- ICMP/TCP working while UDP fails is the signature: **DDS is UDP and needs
  inbound-initiated flows** — test inbound UDP directly, don't trust ping.
- The whitelist tracks whatever `192.168.8.x` address DHCP gives the laptop
  (auto-detected each start), so it survives lease changes.
- Requires WSL2 **mirrored networking** (`networkingMode=mirrored` in
  `.wslconfig`) so the laptop's `192.168.8.x` address is shared into WSL.
- See also [wsl_host_setup.md](wsl_host_setup.md).
