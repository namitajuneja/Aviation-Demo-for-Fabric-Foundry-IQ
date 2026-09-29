# Ontology manual steps

## Why manual work remains

As of 2026-09-28, Microsoft documents ontology CRUD and JSON/TMDL item definitions. The documented definition format doesn't describe RDF/Turtle import. Therefore `import_rdf.ps1` validates and previews only; it does not call an invented endpoint.

## Portal procedure

1. Run `.\ontology\create_ontology.ps1 -DryRun`, review the plan, then use `-Apply` to create an empty generation-2 ontology if needed.
2. In the Fabric workspace, open **AviationOntology**.
3. Use `aviation_ontology.yaml` and `aviation.ttl` as the reviewed design sources. Create the eight entity types and seven relationships.
4. Bind entities to the mirrored/Lakehouse tables using the keys in the YAML.
5. Map relationship endpoints with both `flight_no` and `date` where specified.
6. Refresh the graph model manually and inspect sample instances. Upstream updates aren't visible until ontology refresh.
7. Add the ontology as one of the Fabric data agent sources.

Do not paste credentials or tenant identifiers into YAML/TTL. Record workspace/item IDs only in environment variables.

