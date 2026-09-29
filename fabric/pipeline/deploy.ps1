[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw "Use either -DryRun or -Apply, not both." }
$workspaceId = $env:FABRIC_WORKSPACE_ID
$displayName = if ($env:FABRIC_PIPELINE_NAME) { $env:FABRIC_PIPELINE_NAME } else { "Aviation Refresh" }
$definitionPath = Join-Path $PSScriptRoot "aviation_refresh.pipeline.json"
if (-not (Test-Path -LiteralPath $definitionPath)) { throw "Missing pipeline definition." }
$null = Get-Content -Raw -LiteralPath $definitionPath | ConvertFrom-Json

Write-Host "Plan: ensure DataPipeline '$displayName' exists in workspace '$workspaceId'."
Write-Host "Definition: $definitionPath"
if ($DryRun -or -not $Apply) {
    Write-Host "DRY RUN: validated JSON; no token requested and no cloud request sent."
    exit 0
}
if ([string]::IsNullOrWhiteSpace($workspaceId)) { throw "FABRIC_WORKSPACE_ID is required." }

$token = az account get-access-token --resource "https://api.fabric.microsoft.com" --query accessToken -o tsv
if ([string]::IsNullOrWhiteSpace($token)) { throw "Azure CLI did not return a Fabric token. Run az login." }
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId"
$items = Invoke-RestMethod -Method Get -Uri "$base/items?type=DataPipeline" -Headers $headers
$match = @($items.value) | Where-Object displayName -eq $displayName | Select-Object -First 1
if ($match) {
    Write-Host "Pipeline already exists: $($match.id). No update was attempted."
    Write-Host "Use the Fabric portal or the documented Update Item Definition API for intentional updates."
    exit 0
}

$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw $definitionPath)))
$platform = @{ metadata = @{ type = "DataPipeline"; displayName = $displayName } } | ConvertTo-Json -Depth 5 -Compress
$platformPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($platform))
$body = @{
    displayName = $displayName
    type = "DataPipeline"
    definition = @{ parts = @(
        @{ path = "pipeline-content.json"; payload = $payload; payloadType = "InlineBase64" },
        @{ path = ".platform"; payload = $platformPayload; payloadType = "InlineBase64" }
    )}
} | ConvertTo-Json -Depth 10
$created = Invoke-RestMethod -Method Post -Uri "$base/items" -Headers $headers -Body $body
Write-Host "Create request accepted. Item id: $($created.id)"

