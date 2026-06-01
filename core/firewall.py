import subprocess
import json


def get_enabled_firewall_rules():
    ps_script = """
$ErrorActionPreference = 'SilentlyContinue'
$portMap = @{}
Get-NetFirewallPortFilter | ForEach-Object { $portMap[$_.InstanceID] = $_ }
$appMap = @{}
Get-NetFirewallApplicationFilter | ForEach-Object { $appMap[$_.InstanceID] = $_ }
$results = Get-NetFirewallRule -Enabled True -Direction Inbound | ForEach-Object {
    $id = $_.InstanceID
    $port = $portMap[$id]
    $app = $appMap[$id]
    $prog = if ($app) { ([string]$app.Program) -replace '\\\\', '/' } else { '' }
    [PSCustomObject]@{
        Enabled = [string]$_.Enabled
        DisplayName = [string]$_.DisplayName
        LocalPort = if ($port) { [string]$port.LocalPort } else { '' }
        Protocol = if ($port) { [string]$port.Protocol } else { '' }
        Direction = [string]$_.Direction
        Profile = [string]$_.Profile
        Action = [string]$_.Action
        Program = $prog
    }
}
if ($results) { $results | ConvertTo-Json -Compress -Depth 2 } else { Write-Output '[]' }
"""

    def decode_ps(b):
        for enc in ('utf-8', 'cp932', 'utf-8-sig'):
            try:
                return b.decode(enc)
            except Exception:
                continue
        return b.decode('utf-8', errors='replace')

    try:
        cmd = '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; ' + ps_script
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', cmd],
            capture_output=True,
            timeout=120,
        )

        stdout = decode_ps(result.stdout).strip()
        stderr = decode_ps(result.stderr).strip()

        if not stdout:
            return [], f"ERROR (PS): {stderr[:500]}" if stderr else "ERROR: no output"

        idx = -1
        for ch in ('[', '{'):
            i = stdout.find(ch)
            if i != -1 and (idx == -1 or i < idx):
                idx = i
        if idx == -1:
            return [], f"ERROR: no JSON: {stdout[:300]}"

        data = json.loads(stdout[idx:])
        if isinstance(data, dict):
            data = [data]
        return data, None

    except subprocess.TimeoutExpired:
        return [], "ERROR: timeout (120s)"
    except json.JSONDecodeError as e:
        return [], f"ERROR: JSON parse failed ({e})"
    except Exception as e:
        return [], f"ERROR: {type(e).__name__}: {e}"
