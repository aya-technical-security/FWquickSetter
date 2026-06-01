param(
    [string]$Port,
    [string]$Protocol
)

$RuleName = "FWQ_$Port`_$Protocol"

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Protocol $Protocol `
    -LocalPort $Port `
    -Action Allow

Write-Output "SUCCESS: Opened $Protocol/$Port"