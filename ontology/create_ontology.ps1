[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw "Use either -DryRun or -Apply, not both." }

$workspaceId = $env:FABRIC_WORKSPACE_ID
$name = if ($env:FABRIC_ONTOLOGY_NAME) { $env:FABRIC_ONTOLOGY_NAME } else { "AviationOntology" }
$baseUri = "https://api.fabric.microsoft.com/v1"
$planOnly = $DryRun -or -not $Apply

Write-Host "Plan: ensure ontology '$name' exists in workspace '$workspaceId'."
Write-Host "Endpoint: GET/POST $baseUri/workspaces/{workspaceId}/ontologies"
if ($planOnly) {
    Write-Host "DRY RUN: no token requested and no cloud request sent. Re-run with -Apply."
    exit 0
}
if ([string]::IsNullOrWhiteSpace($workspaceId)) { throw "FABRIC_WORKSPACE_ID is required." }

$token = az account get-access-token --resource "https://api.fabric.microsoft.com" --query accessToken -o tsv
if ([string]::IsNullOrWhiteSpace($token)) { throw "Azure CLI did not return a Fabric token. Run az login." }
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$uri = "$baseUri/workspaces/$workspaceId/ontologies"
$existing = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
$match = @($existing.value) | Where-Object displayName -eq $name | Select-Object -First 1
if ($match) {
    Write-Host "Ontology already exists: $($match.id)"
    exit 0
}
$body = @{ displayName = $name; description = "Compact aviation operations ontology." } | ConvertTo-Json
$created = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
Write-Host "Create request accepted. Item id: $($created.id)"

