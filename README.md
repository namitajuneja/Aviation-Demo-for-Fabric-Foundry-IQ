# Fabric aviation intelligence demo

A runnable, synthetic airline-group demonstration of:

**Snowflake system of record → zero-ETL mirroring into OneLake → Fabric IQ ontology → Fabric and Foundry agents answering natural-language questions.**

The operating companies are MAINLINE, REGIONAL, CARGO, and LOYALTY. The data is synthetic and reproducible; no script reads secrets from files. Set deployment values as environment variables using `.env.example` as a checklist.

## Architecture

```text
Snowflake AVIATION_DEMO.OPS
          |
          | Fabric mirroring (change tracking)
          v
OneLake mirrored database --> AviationGold Lakehouse --> Direct Lake semantic model
                                      |
                                      v
                              Fabric IQ ontology
                                      |
                           Fabric data agent (published)
                                      |
                                      v
                         Microsoft Foundry prompt agent
```

## What is automated

1. Generate synthetic data with `python .\scripts\generate_data.py`.
2. Prepare/load Snowflake by following `.\snowflake\README.md`.
3. Mirror the ten `AVIATION_DEMO.OPS` base tables in the Fabric portal.
4. Import and run `.\fabric\notebooks\01_validate_mirror.ipynb` and `02_build_gold.ipynb`.
5. Open `.\powerbi\AviationDemo.pbip` in Power BI Desktop and bind the Direct Lake model to the target Lakehouse.
6. Create the Fabric pipeline with `.\fabric\pipeline\deploy.ps1 -Apply`.
7. Connect a published Fabric data agent to Microsoft Foundry with `python .\foundry\deploy_agent.py --apply --smoke-test`.

Ontology and data-agent steps are split deliberately. The current Fabric REST API supports ontology item creation/definitions, but RDF import isn't a documented REST operation. Data-agent authoring/publishing remains a portal workflow; only a published agent's MCP query endpoint is documented. See `.\ontology\MANUAL_STEPS.md` and `.\agent\publish_to_teams.md`.

Every cloud PowerShell script defaults to dry-run. `-DryRun` is accepted explicitly; `-Apply` is required to make supported changes.

## Environment

```powershell
# Use .\.env.example as a variable checklist; scripts do not read an .env file.
$env:FABRIC_WORKSPACE_ID = "<uuid>"
$env:FABRIC_LAKEHOUSE_ID = "<uuid>"
$env:FABRIC_ONTOLOGY_NAME = "AviationOntology"
$env:FABRIC_DATA_AGENT_ID = "<published-agent-uuid>"
```

Authentication uses `az account get-access-token`; sign in with `az login` before an apply operation. No script persists a token.

## Included sample data

`data\` contains a compact seeded dataset for immediate inspection and smoke testing. Regenerate it with:

```powershell
python .\scripts\generate_data.py --seed 42
```

The generator supports the full demo volumes described in the source and writes Parquet plus capped CSV previews.

## Foundry integration

The Foundry project, Fabric data agent, and its underlying Fabric capacity must be in the same tenant and region. Publish the Fabric data agent before deploying the Foundry agent.

```powershell
python .\foundry\deploy_agent.py --dry-run
python .\foundry\deploy_agent.py --apply --smoke-test
```

The deployment uses a project-scoped `CustomKeys` connection. Current Foundry preview runtimes expect the credential names `workspace-id` and `artifact-id` even though some documentation examples use underscores. The script uses the runtime-compatible hyphenated names.

Some preview tenants reject aggregation over the ontology's `MaintenanceEvent` graph node even when its binding is healthy. Add `--maintenance-lakehouse-fallback` to route only maintenance/AOG questions through the governed `AviationGold.maintenance_event` table while all other questions continue to prefer the ontology. This limitation and workaround are explicit rather than hidden.

## Official API position (checked 2026-09-28)

- [Ontology create REST API](https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/create-ontology) documents `POST .../workspaces/{workspaceId}/ontologies`.
- [Ontology item definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/ontology-definition) documents JSON/TMDL definition parts, not RDF/Turtle import.
- [Fabric item API support](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/item-management-overview) lists Ontology and Data Pipeline, but doesn't list Fabric data agent as a CRUD item type.
- [Data agent tutorial](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-end-to-end-tutorial) documents portal authoring/publishing and the published MCP endpoint.
- [Foundry Fabric tool](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/fabric) documents identity passthrough, same-region requirements, and the `MicrosoftFabricPreviewTool`.
