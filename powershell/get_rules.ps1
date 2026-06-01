Get-NetFirewallRule |
Where-Object {$_.Enabled -eq "True"} |
Select-Object DisplayName, Direction, Action |
ConvertTo-Json -Depth 3