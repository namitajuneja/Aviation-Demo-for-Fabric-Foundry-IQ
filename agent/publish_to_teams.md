# Configure, publish, and share the data agent

These are portal steps. `create_data_agent.ps1` intentionally doesn't invent a management endpoint.

1. In the target Fabric workspace select **New item > Fabric data agent** and name it **Aviation Group Intelligence**.
2. Add no more than the supported five sources. For this demo add the **AviationGold** semantic model and **AviationOntology**.
3. Select the gold model tables/measures needed by the demo. Paste `.\agent\instructions.md` into **Data agent instructions**.
4. Add the question/query guidance from `.\agent\few_shot_examples.json` as examples where the source type supports examples.
5. Test the four questions and one out-of-scope question. Confirm permissions are enforced and no unsupported claim is made.
6. Select **Publish**. In agent settings copy the published URL and record only the data-agent ID in `FABRIC_DATA_AGENT_ID`.
7. Validate with `.\agent\test_agent.ipynb` or `.\fabric\notebooks\04_agent_questions.ipynb`.
8. Share the Fabric item with the intended Entra group. In Microsoft 365 Copilot/Teams, add the published Fabric data agent using the tenant-supported agent sharing flow. Exact Teams catalog/promote controls vary by tenant policy and are not automated here.

Prerequisites include Fabric capacity, agent tenant settings, cross-geo AI settings where required, and user Read permission on the semantic model/ontology. Never broaden workspace permissions merely to make the demo work.

The documented MCP URL is:

```text
https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspaceId}/dataagents/{dataAgentId}/agent
```

