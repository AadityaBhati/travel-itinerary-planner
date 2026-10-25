from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    demo_mode: bool = False
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment_name: str = ""
    unsplash_access_key: str | None = None
    frontend_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
