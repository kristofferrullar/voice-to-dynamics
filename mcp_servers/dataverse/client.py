"""Async HTTP client for the Dataverse Web API (OData v4).

A single `httpx.AsyncClient` is kept alive for the lifetime of the
`DataverseClient` instance so every API call reuses the same TCP/TLS
connection instead of opening and tearing down a new one each time.

The module-level `get_client()` function returns a lazily-created singleton
that is shared across all tool calls within a single MCP server subprocess.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from mcp_servers.dataverse.auth import DataverseAuth

logger = logging.getLogger(__name__)

_API_VERSION = "v9.2"

# Lazily initialised singleton — only created when the first tool is called,
# so the MCP server subprocess can import this module even before credentials
# are validated (MSAL raises at construction if the tenant ID is empty).
_shared_client: "DataverseClient | None" = None


def get_client() -> "DataverseClient":
    """Return the shared DataverseClient, creating it on first call."""
    global _shared_client
    if _shared_client is None:
        _shared_client = DataverseClient()
    return _shared_client


class DataverseClient:
    """Thin async wrapper over the Dataverse Web API."""

    def __init__(self) -> None:
        self._auth = DataverseAuth()
        base = f"{self._auth.environment_url}/api/data/{_API_VERSION}"
        self._http = httpx.AsyncClient(base_url=base, timeout=30.0)

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
        url = f"/{entity_set}"
        if query:
            url = f"{url}?{query}"
        r = await self._http.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json()

    async def post(self, entity_set: str, data: dict[str, Any]) -> str:
        """Create a record. Returns the new record id."""
        r = await self._http.post(f"/{entity_set}", headers=self._headers(), json=data)
        r.raise_for_status()
        # Dataverse returns the entity URL in OData-EntityId header
        entity_id_header = r.headers.get("OData-EntityId", "")
        if "(" in entity_id_header:
            return entity_id_header.split("(")[-1].rstrip(")")
        return ""

    async def patch(self, entity_set: str, record_id: str, data: dict[str, Any]) -> None:
        headers = {**self._headers(), "If-Match": "*"}
        r = await self._http.patch(
            f"/{entity_set}({record_id})", headers=headers, json=data
        )
        r.raise_for_status()

    async def delete(self, entity_set: str, record_id: str) -> None:
        r = await self._http.delete(
            f"/{entity_set}({record_id})", headers=self._headers()
        )
        r.raise_for_status()

    async def get_current_user(self) -> dict[str, Any]:
        """Return the systemuser record for the authenticated service principal."""
        r = await self._http.get("/WhoAmI", headers=self._headers())
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self._http.aclose()
