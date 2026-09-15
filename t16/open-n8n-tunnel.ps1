<#
.SYNOPSIS
Opens the fixed, loopback-only T16 browser tunnel to T480 n8n.

.DESCRIPTION
The n8n service remains private on T480.  This script binds only
127.0.0.1:15678 on the T16 and forwards it over the existing, verified
Windows OpenSSH route to T480's loopback-only 127.0.0.1:5678 listener.
It deliberately provides no remote shell, dynamic forward, or LAN listener.

Keep this PowerShell window open while using n8n, then press Ctrl+C to close
the tunnel.  No API token is needed for browser sign-in.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$target = [Environment]::GetEnvironmentVariable('T480_SSH_TARGET')
if ([string]::IsNullOrWhiteSpace($target)) {
    throw 'T480_SSH_TARGET is not set. Set it in this T16 PowerShell session to the existing verified T480 SSH target, then run this script again.'
}

$ssh = Get-Command ssh.exe -ErrorAction Stop
$arguments = @(
    '-N', '-T',
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ConnectTimeout=10',
    '-L', '127.0.0.1:15678:127.0.0.1:5678',
    $target
)

Write-Host 'Opening private T16 -> T480 n8n tunnel at http://127.0.0.1:15678'
Write-Host 'Keep this window open. Press Ctrl+C when finished.'
& $ssh.Source @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "The n8n SSH tunnel exited with code $exitCode. Check T480_SSH_TARGET, the verified host key, and whether T480 n8n is running."
}
