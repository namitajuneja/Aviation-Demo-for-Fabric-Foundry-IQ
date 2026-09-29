#!/usr/bin/env python3
"""Deploy a Foundry prompt agent backed by a published Fabric data agent."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Config:
    subscription_id: str
    resource_group: str
    account_name: str
    project_name: str
    project_endpoint: str
    model: str
    agent_name: str
    connection_name: str
    workspace_id: str
    artifact_id: str

    @property
    def connection_id(self) -> str:
        return (
            f"/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{self.account_name}"
            f"/projects/{self.project_name}/connections/{self.connection_name}"
        )


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def load_config() -> Config:
    config = Config(
        subscription_id=required_env("AZURE_SUBSCRIPTION_ID"),
        resource_group=required_env("FOUNDRY_RESOURCE_GROUP"),
        account_name=required_env("FOUNDRY_ACCOUNT_NAME"),
        project_name=required_env("FOUNDRY_PROJECT_NAME"),
        project_endpoint=required_env("FOUNDRY_PROJECT_ENDPOINT").rstrip("/"),
        model=os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1").strip(),
        agent_name=os.environ.get(
            "FOUNDRY_AGENT_NAME", "aviation-group-intelligence"
        ).strip(),
        connection_name=os.environ.get(
            "FOUNDRY_FABRIC_CONNECTION_NAME", "fabric-dataagent-hyphen-v1"
        ).strip(),
        workspace_id=required_env("FABRIC_WORKSPACE_ID"),
        artifact_id=required_env("FABRIC_DATA_AGENT_ID"),
    )
    UUID(config.subscription_id)
    UUID(config.workspace_id)
    UUID(config.artifact_id)
    return config


def create_connection(config: Config) -> None:
    payload = {
        "properties": {
            "category": "CustomKeys",
            "authType": "CustomKeys",
            "target": "-",
            "group": "AzureAI",
            "isSharedToAll": False,
            "credentials": {
                "keys": {
                    "workspace-id": config.workspace_id,
                    "artifact-id": config.artifact_id,
                }
            },
            "metadata": {"type": "fabric_dataagent_preview"},
        }
    }
    url = (
        f"https://management.azure.com{config.connection_id}"
        "?api-version=2025-04-01-preview"
    )
    subprocess.run(
        [
            "az",
            "rest",
            "--method",
            "put",
            "--url",
            url,
            "--headers",
            "Content-Type=application/json",
            "--body",
            json.dumps(payload),
            "--output",
            "none",
        ],
        check=True,
    )


def instructions(use_maintenance_fallback: bool) -> str:
    text = (
        "Use the Microsoft Fabric data-agent tool for every aviation question. "
        "Ground answers in the published Fabric IQ aviation ontology and OneLake. "
        "Never invent figures. Give the result first with its time window and units, "
        "then briefly explain the business driver."
    )
    if use_maintenance_fallback:
        text += (
            " For maintenance, AOG, downtime, cost, aircraft-tail, ATA, or part-number "
            "questions, ask the Fabric tool to use the AviationGold lakehouse table "
            "maintenance_event rather than the ontology. For all other domains prefer "
            "AviationGroupOntology."
        )
    return text


def deploy_agent(
    config: Config, use_maintenance_fallback: bool, smoke_test: bool
) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        FabricDataAgentToolParameters,
        MicrosoftFabricPreviewTool,
        PromptAgentDefinition,
        ToolProjectConnection,
    )
    from azure.identity import AzureCliCredential

    project = AIProjectClient(
        endpoint=config.project_endpoint,
        credential=AzureCliCredential(),
        allow_preview=True,
    )
    tool = MicrosoftFabricPreviewTool(
        fabric_dataagent_preview=FabricDataAgentToolParameters(
            project_connections=[
                ToolProjectConnection(project_connection_id=config.connection_id)
            ]
        )
    )
    version = project.agents.create_version(
        agent_name=config.agent_name,
        definition=PromptAgentDefinition(
            model=config.model,
            instructions=instructions(use_maintenance_fallback),
            tools=[tool],
            tool_choice="required",
            temperature=0.1,
        ),
        description="Aviation intelligence grounded in a published Fabric data agent.",
    )
    print(f"Created {version.id} ({version.status}).")

    if smoke_test:
        client = project.get_openai_client(agent_name=config.agent_name)
        response = client.with_options(timeout=600).responses.create(
            tool_choice="required",
            input=(
                "Which cargo lanes are under-yielding over the latest eight weeks "
                "compared with the preceding eight weeks?"
            ),
        )
        if response.status != "completed" or not response.output_text.strip():
            raise RuntimeError(f"Smoke test failed with status {response.status}.")
        print(response.output_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--maintenance-lakehouse-fallback", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config()
    except (ValueError, KeyError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"Project endpoint: {config.project_endpoint}")
    print(f"Agent: {config.agent_name}")
    print(f"Connection: {config.connection_id}")
    print(f"Fabric workspace: {config.workspace_id}")
    print(f"Published Fabric data agent: {config.artifact_id}")
    if not args.apply:
        print("DRY RUN: no cloud request sent. Re-run with --apply.")
        return 0

    try:
        create_connection(config)
        deploy_agent(
            config,
            args.maintenance_lakehouse_fallback,
            args.smoke_test,
        )
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
