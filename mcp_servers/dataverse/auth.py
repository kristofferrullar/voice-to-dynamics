"""MSAL client-credentials token acquisition for Dataverse Web API."""
from __future__ import annotations

import logging

import msal

from config.settings import get_settings

logger = logging.getLogger(__name__)

_DATAVERSE_SCOPE_SUFFIX = "/.default"


class DataverseAuth:
    """Acquires and caches OAuth2 tokens for the Dataverse Web API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._environment_url = settings.dataverse_environment_url.rstrip("/")
        self._scope = self._environment_url + _DATAVERSE_SCOPE_SUFFIX
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        )

    def get_token(self) -> str:
        """Return a valid bearer token, acquiring a new one if needed."""
        result = self._app.acquire_token_for_client(scopes=[self._scope])
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise RuntimeError(f"Failed to acquire Dataverse token: {error}")
        return result["access_token"]

    @property
    def environment_url(self) -> str:
        return self._environment_url
