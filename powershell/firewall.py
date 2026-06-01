import subprocess
import json


def get_enabled_firewall_rules():
    """
    有効な受信ファイアウォールルールを取得して list[dict] で返す。
    戻り値: (rules, error)
      - 成功時: (list[dict], None)
      - 失敗時: ([], error_message)
    """

    # PowerShell側でバックスラッシュを / に変換して ConvertTo-Json の
    # 不正エスケープバグを回避。ポート/アプリフィルタはハッシュ結合で高速化。
    ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'

$portMap = @{}
Get-NetFirewallPortFilter | ForEach-Object {
    $portMap[$_.InstanceID] = $_
}

$appMap = @{}
Get-NetFirewallApplicationFilter | ForEach-Object {
    $appMap[$_.InstanceID] = $_
}

$results = Get-NetFirewallRule -Enabled True -Direction Inbound |
    ForEach-Object {
        $id   = $_.InstanceID
        $port = $portMap[$id]
        $app  = $appMap[$id]

        $progRaw = if ($app) { [string]$app.Program } else { '' }
        $prog = $progRaw -replace '\\', '/'

        [PSCustomObject]@{
            Enabled     = [string]$_.Enabled
            DisplayName = [string]$_.DisplayName
            LocalPort   = if ($port) { [string]$port.LocalPort } else { '' }
            Protocol    = if ($port) { [string]$port.Protocol  } else { '' }
            Direction   = [string]$_.Direction
            Profile     = [string]$_.Profile
            Action      = [string]$_.Action
            Program     = $prog
        }
    }

if ($results) {
    $results | ConvertTo-Json -Compress -Depth 2
} else {
    Write-Output '[]'
}
"""

    try:
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                # UTF-8 で出力するよう PowerShell 側に明示指示
                "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + ps_script,
            ],
            capture_output=True,
            timeout=120,
            # bytes で受け取って自前でデコード（エンコード自動判定の失敗を防ぐ）
        )

        # PowerShell の出力エンコードを UTF-8 に強制しているが
        # 環境によっては CP932 になることがあるためフォールバックつきでデコード
        stdout_bytes = result.stdout
        stderr_bytes = result.stderr

        def decode_ps(b: bytes) -> str:
            for enc in ("utf-8", "cp932", "utf-8-sig"):
                try:
                    return b.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return b.decode("utf-8", errors="replace")

        stdout = decode_ps(stdout_bytes).strip()
        stderr = decode_ps(stderr_bytes).strip()

        if not stdout:
            if stderr:
                return [], f"ERROR (PS): {stderr[:500]}"
            return [], "ERROR: PowerShell returned no output"

        # JSON 開始位置を探す（警告メッセージが前に混入する場合がある）
        json_start = -1
        for ch in ('[', '{'):
            idx = stdout.find(ch)
            if idx != -1 and (json_start == -1 or idx < json_start):
                json_start = idx

        if json_start == -1:
            return [], f"ERROR: No JSON found:\n{stdout[:300]}"

        json_str = stdout[json_start:]

        data = json.loads(json_str)

        if isinstance(data, dict):
            data = [data]

        return data, None

    except subprocess.TimeoutExpired:
        return [], "ERROR: PowerShell timeout (120s)"
    except json.JSONDecodeError as e:
        return [], f"ERROR: JSON parse failed ({e})"
    except Exception as e:
        return [], f"ERROR: {type(e).__name__}: {e}"
