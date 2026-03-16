import pytest

from src.agent.schema_loader import load_all


def test_loads_all_schemas():
    schemas = load_all()
    assert len(schemas) > 0


def test_opportunity_schema_present():
    schemas = load_all()
    assert "opportunity" in schemas


def test_opportunity_has_intent_triggers():
    schemas = load_all()
    opp = schemas["opportunity"]
    assert len(opp.intent_triggers) > 0
    assert any("affär" in t for t in opp.intent_triggers)


def test_opportunity_has_filterable_columns():
    schemas = load_all()
    opp = schemas["opportunity"]
    filterable = [a for a in opp.attributes if a.filterable]
    assert len(filterable) > 0


def test_opportunity_statecode_has_common_values():
    schemas = load_all()
    opp = schemas["opportunity"]
    statecode = next(a for a in opp.attributes if a.logical_name == "statecode")
    assert statecode.common_values is not None
    assert statecode.common_values.get("open") == 0


def test_opportunity_has_query_templates():
    schemas = load_all()
    opp = schemas["opportunity"]
    assert "count_open_owned_by_me" in opp.query_templates


def test_all_schemas_valid():
    schemas = load_all()
    for name, schema in schemas.items():
        assert schema.logical_name == name
        assert schema.entity_set
        assert schema.display_name_sv
