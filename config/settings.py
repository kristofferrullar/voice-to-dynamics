from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Azure Speech ────────────────────────────────────────────────────────────
    azure_speech_key: str = ""
    azure_speech_region: str = "swedencentral"

    # ── Azure OpenAI Real-time ──────────────────────────────────────────────────
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_realtime_deployment: str = "gpt-4o-realtime-preview"

    # ── Anthropic ───────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── GitHub ──────────────────────────────────────────────────────────────────
    github_personal_access_token: str = ""

    # ── Dataverse / Entra ID ────────────────────────────────────────────────────
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    dataverse_environment_url: str = ""

    # ── Microsoft Teams (Azure Bot Service) ─────────────────────────────────────
    teams_app_id: str = ""
    teams_app_password: str = ""

    # ── Twilio (WhatsApp) ────────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""  # e.g. whatsapp:+14155238886

    # ── Azure Communication Services (voice calls) ───────────────────────────────
    acs_connection_string: str = ""
    acs_phone_number: str = ""        # the ACS-acquired phone number
    acs_callback_url: str = ""        # public HTTPS URL for ACS event callbacks


@lru_cache
def get_settings() -> Settings:
    return Settings()
