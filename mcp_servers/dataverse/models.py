from typing import Any

from pydantic import BaseModel


class QueryResult(BaseModel):
    records: list[dict[str, Any]]
    total_count: int | None = None
    entity_set: str
    odata_context: str = ""


class CountResult(BaseModel):
    count: int
    entity_set: str


class CreateResult(BaseModel):
    record_id: str
    entity_set: str


class UpdateResult(BaseModel):
    record_id: str
    entity_set: str
    updated_columns: list[str]
    success: bool = True


class DeleteResult(BaseModel):
    record_id: str
    entity_set: str
    success: bool = True
