<#
.SYNOPSIS
    Allow inbound traffic from the robot's Wi-Fi subnet so ROS 2 / DDS discovery
    works from this Windows + WSL2 Docker host. Self-elevates (UAC).

.DESCRIPTION
    DDS discovery needs the robot to initiate UDP back to the laptop. On a
    "Public" Wi-Fi (e.g. a competition network) Windows blocks that by default,
    so the robot is pingable but invisible to ROS. This adds a scoped inbound
    allow rule for the robot subnet (not the whole internet) and marks the Wi-Fi
    Private. Re-run with a different -Subnet whenever the robot network changes.

.PARAMETER Subnet
    The robot's subnet in CIDR, e.g. 192.168.8.0/24 or 10.253.0.0/16.

.PARAMETER InterfaceAlias
    The Wi-Fi adapter alias (default "Wi-Fi"). Find yours with Get-NetAdapter.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File allow-robot-subnet.ps1 -Subnet 192.168.8.0/24

.NOTES
    Remove later with:  Remove-NetFirewallRule -DisplayName "ROS2 DDS <subnet>"
    See docs/troubleshooting_dds_wsl.md for the full diagnosis.
#>
param(
    [Parameter(Mandatory = $true)][string]$Subnet,
    [string]$InterfaceAlias = "Wi-Fi"
)

# --- self-elevate if not running as Administrator ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$id).IsInRole(
    [Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Requesting administrator rights (approve the UAC prompt)..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"",
        '-Subnet', $Subnet, '-InterfaceAlias', $InterfaceAlias
    )
    exit
}

$name = "ROS2 DDS $Subnet"
Remove-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow `
    -RemoteAddress $Subnet -Profile Any -Enabled True | Out-Null
try {
    Set-NetConnectionProfile -InterfaceAlias $InterfaceAlias -NetworkCategory Private -ErrorAction Stop
} catch {
    Write-Warning "Could not set $InterfaceAlias to Private (not connected?). Rule still added."
}
Write-Host "OK: inbound allowed from $Subnet (rule '$name')."
Write-Host "Verify after the robot joins:  wsl ping <robot-ip>  then  ros2 topic list"
