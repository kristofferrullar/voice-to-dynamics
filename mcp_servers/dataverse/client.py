"""Async HTTP client for the Dataverse Web API (OData v4)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from mcp_servers.dataverse.auth import DataverseAuth

logger = logging.getLogger(__name__)

_API_VERSION = "v9.2"
_MAX_RETRIES = 3


class DataverseClient:
    """Thin async wrapper over the Dataverse Web API."""

    def __init__(self) -> None:
        self._auth = DataverseAuth()
        self._base_url = f"{self._auth.environment_url}/api/data/{_API_VERSION}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth.get_token()}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Prefer": "odata.include-annotations=*",
        }

    async def get(self, entity_set: str, query: str = "") -> dict[str, Any]:
        url = f"{self._base_url}/{entity_set}"
        if query:
            url = f"{url}?{query}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def post(self, entity_set: str, data: dict[str, Any]) -> str:
        """Create a record. Returns the new record id."""
        url = f"{self._base_url}/{entity_set}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=self._headers(), json=data)
            r.raise_for_status()
            # Dataverse returns the entity URL in OData-EntityId header
            entity_id_header = r.headers.get("OData-EntityId", "")
            if "(" in entity_id_header:
                return entity_id_header.split("(")[-1].rstrip(")")
            return ""

    async def patch(self, entity_set: str, record_id: str, data: dict[str, Any]) -> None:
        url = f"{self._base_url}/{entity_set}({record_id})"
        headers = {**self._headers(), "If-Match": "*"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.patch(url, headers=headers, json=data)
            r.raise_for_status()

    async def delete(self, entity_set: str, record_id: str) -> None:
        url = f"{self._base_url}/{entity_set}({record_id})"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.delete(url, headers=self._headers())
            r.raise_for_status()

    async def get_current_user(self) -> dict[str, Any]:
        """Return the systemuser record for the authenticated service principal."""
        url = f"{self._base_url}/WhoAmI"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()
