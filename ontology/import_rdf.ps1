[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($DryRun -and $Apply) { throw "Use either -DryRun or -Apply, not both." }
$rdf = Join-Path $PSScriptRoot "aviation.ttl"
if (-not (Test-Path -LiteralPath $rdf)) { throw "Missing $rdf" }
$bytes = (Get-Item -LiteralPath $rdf).Length
Write-Host "Validated local Turtle artifact: $rdf ($bytes bytes)."
Write-Warning "No supported Fabric RDF-import REST endpoint is documented as of 2026-09-28."
Write-Host "No cloud request was sent. Follow .\ontology\MANUAL_STEPS.md."
if ($Apply) { Write-Warning "-Apply intentionally performs no import; portal-only steps remain required." }
