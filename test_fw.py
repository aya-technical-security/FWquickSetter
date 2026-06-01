import subprocess, json

def decode_ps(b):
    for enc in ('utf-8', 'cp932', 'utf-8-sig'):
        try:
            return b.decode(enc)
        except:
            continue
    return b.decode('utf-8', errors='replace')

ps = '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-NetFirewallRule -Enabled True -Direction Inbound | Select-Object -First 2 DisplayName,Action | ConvertTo-Json -Compress'

r = subprocess.run(['powershell','-ExecutionPolicy','Bypass','-Command', ps], capture_output=True, timeout=60)
print('STDOUT:', repr(decode_ps(r.stdout)[:400]))
print('STDERR:', repr(decode_ps(r.stderr)[:200]))
print('CODE:', r.returncode)
