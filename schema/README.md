# Entity Schema Files

Each `.yaml` file in this directory describes a Dataverse entity that the agent is allowed to interact with.

## Structure

```yaml
entity:
  logical_name:    # Dataverse logical entity name
  entity_set:      # OData EntitySet name (used in API URLs)
  display_name_sv: # Swedish display name for logging / UX

intent_triggers:   # Swedish phrases that indicate the user is talking about this entity

attributes:        # Columns the agent may reference
  - logical_name:     # OData column name
    display_name_sv:  # What the user might say in Swedish
    type:             # string | int | money | date | optionset | guid | lookup | bool
    filterable:       # Whether $filter on this column is safe
    selectable:       # Whether $select may include this column
    common_values:    # (optionset only) friendly name → integer map

query_templates:   # Pre-built OData patterns for common intents
  <key>:
    description:   # When to use this template
    odata:         # OData query string (supports {current_user_id}, {month_start}, {month_end})
    select:        # Comma-separated columns to $select
```

## Adding a New Entity

1. Run the schema discovery script to generate a starter file:
   ```
   python scripts/discover_schema.py --entity <logical_name> --output schema/<logical_name>.yaml
   ```
2. Edit the generated file:
   - Add Swedish `intent_triggers`
   - Set `filterable: true/false` for each attribute
   - Add `common_values` for option-set columns
   - Write `query_templates` for frequent user queries
3. Add the entity to `mcp_servers/dataverse/allowed_tables.yaml` with appropriate permissions.

See `docs/schema_guide.md` for detailed guidance.
