[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw "Use either -DryRun or -Apply, not both." }
$workspaceId = $env:FABRIC_WORKSPACE_ID
$ids = @($env:FABRIC_DEMO_ITEM_IDS -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })

Write-Host "Teardown is allow-list only. Workspace: '$workspaceId'."
if ($ids.Count -eq 0) {
    Write-Host "No IDs supplied. Set FABRIC_DEMO_ITEM_IDS to comma-separated item UUIDs."
    exit 0
}
Write-Host "Items selected: $($ids -join ', ')"
if ($DryRun -or -not $Apply) {
    Write-Host "DRY RUN: no token requested and no cloud request sent."
    exit 0
}
if ([string]::IsNullOrWhiteSpace($workspaceId)) { throw "FABRIC_WORKSPACE_ID is required." }
foreach ($id in $ids) {
    if ($id -notmatch "^[0-9a-fA-F-]{36}$") { throw "Invalid item UUID: $id" }
}

$token = az account get-access-token --resource "https://api.fabric.microsoft.com" --query accessToken -o tsv
if ([string]::IsNullOrWhiteSpace($token)) { throw "Azure CLI did not return a Fabric token." }
$headers = @{ Authorization = "Bearer $token" }
foreach ($id in $ids) {
    $uri = "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/items/$id"
    Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
    Write-Host "Deleted item $id"
}
Write-Warning "Snowflake objects, capacity, workspace, and source data were intentionally not deleted."
