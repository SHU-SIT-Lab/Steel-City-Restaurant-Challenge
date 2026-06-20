# Windows host helpers

For running the stack from a Windows laptop via WSL2 (see
[../../docs/wsl_host_setup.md](../../docs/wsl_host_setup.md) and
[../../docs/OPERATIONS.md](../../docs/OPERATIONS.md)).

| File | Use |
| --- | --- |
| `wslconfig.example` | Copy to `C:\Users\<you>\.wslconfig`, then `wsl --shutdown`. Enables mirrored networking so WSL shares the laptop's Wi-Fi IP. |
| `allow-robot-subnet.ps1` | Add a scoped Windows Firewall inbound rule for the robot's subnet so DDS discovery works. Self-elevates. |

## Typical use

```powershell
# once per robot network (run from this folder):
powershell -ExecutionPolicy Bypass -File allow-robot-subnet.ps1 -Subnet 192.168.8.0/24
```

`-Subnet` is the robot's network in CIDR — change it when the robot is on a
different Wi-Fi (e.g. `10.253.0.0/16`). The rule is scoped to that subnet only,
not the internet, and persists across reboots.

**Why this is needed:** ping/SSH to the robot can work while ROS sees nothing,
because DDS is inbound UDP that a Public-network firewall drops. Full diagnosis:
[../../docs/troubleshooting_dds_wsl.md](../../docs/troubleshooting_dds_wsl.md).
