# Snowflake source of truth

Run from PowerShell with SnowSQL after setting the `.env` values:

```powershell
snowsql -f .\snowflake\01_create_objects.sql
snowsql -D AVIATION_STAGE_URL=$env:SNOWFLAKE_STAGE_URL `
  -D AVIATION_STORAGE_INTEGRATION=$env:SNOWFLAKE_STORAGE_INTEGRATION `
  -f .\snowflake\02_load_data.sql
snowsql -f .\snowflake\03_mirroring_prereqs.sql
```

## Mirroring caveats to defend

- Fabric mirrors Snowflake **base tables**; views and dynamic tables are not mirrored.
- Every mirrored table must have Snowflake `CHANGE_TRACKING = TRUE`.
- “Zero ETL” removes pipeline copies and transformation jobs, but Snowflake compute is still consumed when Fabric reads the initial snapshot and change feed.
- Initial snapshot time and Snowflake/transfer cost scale with source-table size. Use the compact profile for this demo.
- Schema drift must be assessed before production changes. Additive columns should be validated in the mirror and semantic layer; destructive changes need coordinated deployment.
