# Demo runbook (20–25 minutes)

## Preflight

- Fabric F2+ capacity, workspace Contributor, Snowflake account, Azure CLI, Power BI Desktop with developer/PBIP features enabled.
- Set the variables in `.env.example` in the current PowerShell process.
- Confirm mirroring is running and the Lakehouse is attached to both notebooks.

## Flow

1. **Source (3 min):** show the ten Snowflake base tables and `CHANGE_TRACKING = TRUE`. Explain that initial snapshot/change-feed reads still consume Snowflake/transfer resources.
2. **Zero-ETL mirror (3 min):** in Fabric, show mirrored table status. Run `01_validate_mirror.ipynb`; call out row counts, key checks, and max business dates.
3. **Gold (4 min):** run `02_build_gold.ipynb`. Show `gold_dim_*`, `gold_fact_flight`, `gold_fact_booking`, and `gold_fact_disruption`.
4. **Direct Lake (4 min):** open `.\powerbi\AviationDemo.pbip`, refresh model metadata, then show Executive Overview, Operations, Customer & Revenue, and Cargo & Maintenance.
5. **Ontology (4 min):** show Flight, Route, Aircraft, Customer, Booking, Disruption, and their relationships. Explain that `aviation.ttl` is a portable design artifact; import/bind is manual because no supported RDF-import endpoint was found.
6. **Agent (5 min):** ask the questions in `04_agent_questions.ipynb`, the Fabric portal, or the Foundry `aviation-group-intelligence` agent. Demonstrate evidence-first answers and one safe “not available” response.

## Demo questions

- Which routes had the worst average delay and how many passengers were affected?
- Compare revenue and load factor by operating company.
- Which aircraft have both high downtime and repeated disrupted flights?
- Which loyalty tiers lost the most revenue to cancellations?

## Recovery

- Notebook failure: verify the correct mirrored database/Lakehouse is attached and table names are visible.
- Empty report: update the Direct Lake connection in Power BI Desktop and refresh metadata.
- Agent unavailable: use portal screenshots/results only; don't substitute an undocumented API.
- Foundry calls `knowledge_base_retrieve`: the wrong/legacy knowledge-base agent is open. Use the Foundry prompt agent deployed by `.\foundry\deploy_agent.py`, which invokes the published Fabric data-agent tool.
- Foundry says workspace/artifact IDs are missing: recreate the connection with the hyphenated `workspace-id` and `artifact-id` keys by rerunning `.\foundry\deploy_agent.py --apply`.
- Maintenance graph aggregation fails: redeploy with `--maintenance-lakehouse-fallback`; this keeps maintenance on governed OneLake data and leaves other domains ontology-first.
- Cleanup: preview `.\scripts\teardown.ps1 -DryRun`, then run with `-Apply` only after confirming item IDs.
