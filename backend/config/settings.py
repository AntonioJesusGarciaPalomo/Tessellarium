"""
Tessellarium — Configuration

All Azure service endpoints and keys loaded from environment.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Configuration loaded from .env file or environment variables.
    """

    # ─── App ─────────────────────────────────────────────────────────────
    app_name: str = "Tessellarium"
    app_version: str = "0.1.0"
    debug: bool = False

    # ─── Azure Foundry ───────────────────────────────────────────────────
    azure_foundry_endpoint: str = ""
    azure_foundry_project: str = ""

    # ─── Azure OpenAI (for direct calls: vision, etc.) ───────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-12-01-preview"
    model_gpt4o: str = "gpt-4o"
    model_gpt4o_mini: str = "gpt-4o-mini"

    # ─── Azure Content Understanding ─────────────────────────────────────
    content_understanding_endpoint: str = ""
    content_understanding_api_version: str = "2025-11-01"

    # ─── Azure AI Search ─────────────────────────────────────────────────
    search_endpoint: str = ""
    search_api_key: str = ""
    search_index_name: str = "tesselarium-protocols"

    # ─── Azure Content Safety ────────────────────────────────────────────
    content_safety_endpoint: str = ""
    content_safety_api_key: str = ""

    # ─── Azure Cosmos DB ─────────────────────────────────────────────────
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "tesselarium"
    cosmos_container: str = "sessions"

    # ─── Lean 4 Verification Service (optional) ─────────────────────────
    lean_service_url: Optional[str] = None
    lean_timeout_seconds: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
