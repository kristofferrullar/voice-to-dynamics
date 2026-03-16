# Schema Guide

Entity schemas are YAML files in the `schema/` directory. They define what Dataverse entities the agent knows about, what columns it can use, and pre-built OData query templates for common intents.

## Generating a Starter Schema

```bash
python scripts/discover_schema.py --entity opportunity --output schema/opportunity.yaml
```

This introspects the live Dataverse `$metadata` endpoint and writes a starter file. You must then curate it manually.

## Required Curation Steps

### 1. Verify `entity_set`
The discovery script guesses the EntitySet name by appending `s`. Verify against the actual Dataverse metadata. For example: `opportunity` → `opportunities`, but `lead` → `leads`, `activity` → `activities`.

### 2. Add `display_name_sv`
The Swedish name used in logs and the agent system prompt.

### 3. Add `intent_triggers`
Swedish phrases a user might say to refer to this entity. The more specific and varied, the better:

```yaml
intent_triggers:
  - affärsmöjlighet
  - affärsmöjligheter
  - möjlighet
  - deal
```

### 4. Set `filterable` carefully
Only mark columns as `filterable: true` if Dataverse supports `$filter` on them. Option sets, strings, dates, lookups, and numbers are generally filterable. Memo (multi-line text) and image columns are not.

### 5. Add `common_values` for option sets
Option set columns store integers. Map friendly names to integers so the agent knows what values to use:

```yaml
- logical_name: statecode
  type: optionset
  common_values:
    open: 0
    won: 1
    lost: 2
```

### 6. Add `query_templates`
Pre-built OData patterns for the most frequent queries. The agent strongly prefers templates over constructing custom queries. Available template variables: `{current_user_id}`, `{today}`, `{month_start}`, `{month_end}`.

```yaml
query_templates:
  count_open_owned_by_me:
    description: "How many open opportunities do I have?"
    odata: "$filter=statecode eq 0 and _ownerid_value eq {current_user_id}&$count=true&$top=1&$select=opportunityid"
    select: "opportunityid"
```

### 7. Register in `allowed_tables.yaml`
Add the entity to `mcp_servers/dataverse/allowed_tables.yaml` with the permissions it needs:

```yaml
opportunity:
  entity_set: opportunities
  display_name: Affärsmöjlighet
  permissions: [query, count, update]
```

## Tips

- Keep the schema file focused — only include columns the agent actually needs.
- More attributes = larger system prompt = higher token cost per request. Trim aggressively.
- Test by running a text-only agent session: `python -c "import asyncio; from src.agent.agent import ...; asyncio.run(...)"` before connecting speech.
