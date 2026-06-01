param(
    [string]$Port,
    [string]$Protocol
)

$RuleName = "FWQ_$Port`_$Protocol"

Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue |
Remove-NetFirewallRule

Write-Output "SUCCESS: Closed $Protocol/$Port"