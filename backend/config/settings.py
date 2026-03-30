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
    app_version: str = "0.2.0"
    debug: bool = False
    cors_origins: str = "*"

    # ─── Azure Foundry ───────────────────────────────────────────────────
    azure_foundry_endpoint: str = ""
    azure_foundry_project: str = ""

    # ─── Azure OpenAI (used via Foundry Agent Service) ───────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-12-01-preview"
    model_gpt4o: str = "gpt-4o"
    model_gpt4o_mini: str = "gpt-4o-mini"

    # ─── Azure Content Understanding ─────────────────────────────────────
    content_understanding_endpoint: str = ""
    content_understanding_api_version: str = "2025-11-01"

    # ─── Azure AI Search (used by Foundry IQ) ────────────────────────────
    search_endpoint: str = ""
    search_api_key: str = ""
    search_index_name: str = "tessellarium-protocols"

    # ─── Azure Content Safety ────────────────────────────────────────────
    content_safety_endpoint: str = ""
    content_safety_api_key: str = ""

    # ─── Azure Cosmos DB ─────────────────────────────────────────────────
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "tessellarium"
    cosmos_sessions_container: str = "sessions"
    cosmos_threads_container: str = "threads"

    # ─── Azure Blob Storage ──────────────────────────────────────────────
    storage_connection_string: str = ""
    storage_uploads_container: str = "uploads"
    storage_processed_container: str = "processed"
    storage_literature_container: str = "literature"

    # ─── Lean 4 Verification Service ─────────────────────────────────────
    lean_service_url: Optional[str] = None
    lean_mcp_token: str = ""
    lean_timeout_seconds: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
