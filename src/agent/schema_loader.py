"""Schema loader — reads and validates all entity YAML files from the schema/ directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class AttributeSchema(BaseModel):
    logical_name: str
    display_name_sv: str
    type: str
    filterable: bool = False
    selectable: bool = True
    common_values: dict[str, int] | None = None
    note: str | None = None


class QueryTemplate(BaseModel):
    description: str
    odata: str
    select: str


class EntitySchema(BaseModel):
    logical_name: str
    entity_set: str
    display_name_sv: str
    intent_triggers: list[str]
    attributes: list[AttributeSchema]
    query_templates: dict[str, QueryTemplate] = {}

    @field_validator("intent_triggers")
    @classmethod
    def triggers_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("intent_triggers must not be empty")
        return [t.lower() for t in v]


_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"


def load_all() -> dict[str, EntitySchema]:
    """Load and validate all .yaml files in the schema/ directory.

    Returns a dict keyed by entity logical_name.
    """
    schemas: dict[str, EntitySchema] = {}
    for path in sorted(_SCHEMA_DIR.glob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(path.read_text())
        entity_raw = raw.get("entity", {})
        schema = EntitySchema(
            logical_name=entity_raw["logical_name"],
            entity_set=entity_raw["entity_set"],
            display_name_sv=entity_raw["display_name_sv"],
            intent_triggers=raw.get("intent_triggers", []),
            attributes=[AttributeSchema(**a) for a in raw.get("attributes", [])],
            query_templates={
                k: QueryTemplate(**v) for k, v in raw.get("query_templates", {}).items()
            },
        )
        schemas[schema.logical_name] = schema
    return schemas
