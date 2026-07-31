from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./voice_agent.db"
    public_base_url: str = "http://localhost:8000"
    twilio_auth_token: str = ""
    twilio_validate_signatures: bool = True
    business_name: str = "Northstar Home Services"
    business_timezone: str = "Asia/Kolkata"
    calendar_provider: str = "memory"
    hubspot_private_app_token: str = ""
    escalation_phone_number: str = ""
    openrouter_api_key: str = ""
    openrouter_primary_model: str = "openai/gpt-oss-120b"
    openrouter_fallback_models: str = "~openai/gpt-latest,~anthropic/claude-sonnet-latest"


    @property
    def openrouter_models(self) -> list[str]:
        return [model.strip() for model in self.openrouter_fallback_models.split(",") if model.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
