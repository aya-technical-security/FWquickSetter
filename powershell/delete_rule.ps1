param(
    [string]$RuleName
)
 
Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue |
Remove-NetFirewallRule
 
Write-Output "SUCCESS: Deleted rule $RuleName"