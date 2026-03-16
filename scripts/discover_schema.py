#!/usr/bin/env python
"""Discover Dataverse entity schema from the live $metadata endpoint.

Generates a starter YAML schema file for a given entity.
Curate the output (add intent_triggers, display_name_sv, common_values,
query_templates) before using it with the agent.

Usage:
  python scripts/discover_schema.py --entity opportunity --output schema/opportunity.yaml
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import yaml

from mcp_servers.dataverse.auth import DataverseAuth


def discover(entity_logical_name: str) -> dict:
    auth = DataverseAuth()
    # Fetch entity metadata
    url = (
        f"{auth.environment_url}/api/data/v9.2/"
        f"EntityDefinitions(LogicalName='{entity_logical_name}')"
        f"/Attributes?$select=LogicalName,AttributeType,DisplayName,IsSortableEnabled,IsValidForRead"
    )
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }
    r = httpx.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    attributes = []
    for attr in data.get("value", []):
        logical_name = attr.get("LogicalName", "")
        attr_type = attr.get("AttributeType", "String").lower()
        attributes.append(
            {
                "logical_name": logical_name,
                "display_name_sv": attr.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label", logical_name),
                "type": attr_type,
                "filterable": attr_type not in ("memo", "image", "file"),
                "selectable": attr.get("IsValidForRead", True),
            }
        )

    entity_set = entity_logical_name + "s"  # rough default — verify against actual EntitySet name
    return {
        "entity": {
            "logical_name": entity_logical_name,
            "entity_set": entity_set,
            "display_name_sv": f"TODO: {entity_logical_name}",
        },
        "intent_triggers": [f"TODO: add Swedish phrases for {entity_logical_name}"],
        "attributes": attributes,
        "query_templates": {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Dataverse entity schema")
    parser.add_argument("--entity", required=True, help="Logical entity name (e.g. 'opportunity')")
    parser.add_argument("--output", required=True, help="Output YAML file path")
    args = parser.parse_args()

    print(f"Fetching schema for '{args.entity}'...")
    schema = discover(args.entity)
    output_path = Path(args.output)
    output_path.write_text(yaml.dump(schema, allow_unicode=True, sort_keys=False, default_flow_style=False))
    print(f"Written to {output_path}")
    print("Next steps:")
    print("  1. Edit display_name_sv and entity_set (verify the EntitySet name)")
    print("  2. Add Swedish intent_triggers")
    print("  3. Set common_values for optionset columns")
    print("  4. Add query_templates for frequent user queries")
    print(f"  5. Add entry to mcp_servers/dataverse/allowed_tables.yaml")


if __name__ == "__main__":
    main()
