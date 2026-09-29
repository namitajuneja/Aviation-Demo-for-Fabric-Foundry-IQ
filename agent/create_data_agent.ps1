[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw "Use either -DryRun or -Apply, not both." }

$workspaceId = $env:FABRIC_WORKSPACE_ID
$agentName = if ($env:FABRIC_DATA_AGENT_NAME) { $env:FABRIC_DATA_AGENT_NAME } else { "Aviation Group Intelligence" }
$instructions = Join-Path $PSScriptRoot "instructions.md"
$examples = Join-Path $PSScriptRoot "few_shot_examples.json"
if (-not (Test-Path $instructions) -or -not (Test-Path $examples)) { throw "Agent configuration files are missing." }

Write-Host "Plan: create '$agentName' in workspace '$workspaceId', add semantic model/ontology, instructions, examples, test, then publish."
Write-Warning "Fabric's documented item CRUD support does not list Fabric data agent authoring."
Write-Warning "The supported tutorial uses the Fabric portal for create/configure/publish; it documents MCP only after publish."
Write-Host "No cloud request was sent. Follow .\agent\publish_to_teams.md."
if ($Apply) {
    Write-Warning "-Apply intentionally performs no mutation because no supported authoring endpoint is used."
}

