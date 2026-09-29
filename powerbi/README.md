# AviationDemo PBIP

Open `.\powerbi\AviationDemo.pbip` with a current Power BI Desktop. Before refresh, replace the server/database placeholders in `.\powerbi\AviationDemo.SemanticModel\definition\expressions.tmdl` through **Transform data > Data source settings**, then bind to the Fabric Lakehouse SQL endpoint. Keep storage mode Direct Lake.

The checked-in model includes eight tables, composite `flight_key` relationships, and governed measures. Four report page definitions establish the demo narrative; add/change visuals in Desktop and commit the resulting PBIR files.

