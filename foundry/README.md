# Microsoft Foundry deployment

This folder connects the published Fabric data agent to a Foundry prompt agent. It does not connect Foundry directly to Azure AI Search or to an ontology knowledge-base source.

## Prerequisites

- Fabric data agent published and queryable.
- Foundry project and Fabric capacity in the same tenant and region.
- Signed-in user has Foundry User access plus read access to the Fabric agent, ontology, and underlying data.
- Azure CLI authenticated with `az login`.
- Environment variables from `..\.env.example`.

## Deploy

```powershell
python .\foundry\deploy_agent.py --dry-run
python .\foundry\deploy_agent.py --apply --smoke-test
```

If the Fabric preview runtime rejects maintenance graph aggregations:

```powershell
python .\foundry\deploy_agent.py --apply --smoke-test --maintenance-lakehouse-fallback
```

The script is idempotent at the connection level and creates a new immutable agent version when applied. No credentials or access tokens are written to disk.

## Important preview behavior

The project connection uses `CustomKeys` with `workspace-id` and `artifact-id`. Those hyphenated names are required by the current Foundry Fabric-tool runtime. Using `workspace_id` and `artifact_id` can create a connection that looks valid in management APIs but fails during execution.
