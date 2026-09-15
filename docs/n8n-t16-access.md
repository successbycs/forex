# Accessing n8n from the T16

n8n deliberately listens only on the T480's loopback interface.  Do not make
it LAN- or internet-accessible.  The approved browser path is a temporary SSH
local forward from the T16.

In **T16 Windows PowerShell**, set the pre-existing verified SSH target if it
is not already available in that session, then run the Forex-owned launcher:

```powershell
$env:T480_SSH_TARGET = 'your-existing-t480-ssh-target'
& "$HOME\projects\forex\t16\open-n8n-tunnel.ps1"
```

Leave that PowerShell window open and browse to
[http://127.0.0.1:15678](http://127.0.0.1:15678). Sign in with the normal n8n
browser account. No API key or infrastructure `.env` file belongs on the T16
command line or in the browser URL.

The launcher uses strict host-key checking and binds only
`127.0.0.1:15678` on T16. It forwards solely to `127.0.0.1:5678` on T480. Press
`Ctrl+C` in the launcher window to remove the tunnel. If it exits immediately,
the error is a concrete SSH, local-port, or T480 n8n availability problem;
do not solve it by widening an n8n listener or adding a firewall rule.

For a one-off command without the launcher, the correct PowerShell syntax is:

```powershell
ssh.exe -N -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -L "127.0.0.1:15678:127.0.0.1:5678" $env:T480_SSH_TARGET
```
