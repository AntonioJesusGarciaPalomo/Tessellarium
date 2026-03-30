"""
Tessellarium — Azure Foundry Agent Service Client

Wraps the azure-ai-projects SDK for the Responses API pattern.
Provides agent registration, conversation management, and tool connections.

If Foundry is not configured, the system falls back to direct Azure OpenAI calls.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency — the SDK is pre-release
_foundry_available = False
try:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    _foundry_available = True
except ImportError:
    pass


class FoundryClient:
    """
    Wraps azure-ai-projects SDK for the Responses API pattern.

    Usage:
        client = FoundryClient(endpoint, project_name)
        response = await client.run_agent(
            model="gpt-4o",
            system_prompt="You are...",
            user_message="Extract...",
            temperature=0.1,
        )
    """

    def __init__(
        self,
        endpoint: str,
        project_name: str,
        api_key: Optional[str] = None,
    ):
        if not _foundry_available:
            raise RuntimeError(
                "azure-ai-projects SDK not available. "
                "Install with: pip install azure-ai-projects>=2.0.0b4"
            )

        self._endpoint = endpoint
        self._project_name = project_name

        # Use API key or DefaultAzureCredential
        if api_key:
            from azure.core.credentials import AzureKeyCredential
            self._client = AIProjectClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(api_key),
            )
        else:
            self._client = AIProjectClient(
                endpoint=endpoint,
                credential=DefaultAzureCredential(),
            )

        self._openai_client = None

    def _get_openai_client(self):
        """Get the OpenAI client from the Foundry project (lazy init)."""
        if self._openai_client is None:
            self._openai_client = self._client.inference.get_chat_completions_client()
        return self._openai_client

    async def run_agent(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        Run an agent via the Foundry-managed OpenAI endpoint.

        Uses the Responses API pattern: the Foundry project provides
        an OpenAI-compatible client with automatic content safety,
        tracing, and token tracking.
        """
        client = self._get_openai_client()

        kwargs = dict(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format

        import asyncio
        response = await asyncio.to_thread(client.complete, **kwargs)
        return response.choices[0].message.content


class AgentBase:
    """
    Base class for all Tessellarium agents.

    Provides a unified interface that works in two modes:
    - Direct mode: uses openai SDK (local dev, no Foundry)
    - Foundry mode: uses azure-ai-projects SDK (production)

    Mode is selected based on whether a FoundryClient is provided.
    """

    def __init__(
        self,
        model: str,
        foundry_client: Optional[FoundryClient] = None,
        azure_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: str = "2025-12-01-preview",
    ):
        self.model = model
        self._foundry = foundry_client
        self._direct_client = None

        if not self._foundry:
            endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
            key = api_key or os.getenv("AZURE_OPENAI_API_KEY", "")
            if endpoint and key:
                from openai import AzureOpenAI
                self._direct_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=key,
                    api_version=api_version,
                )

    @property
    def is_foundry_mode(self) -> bool:
        return self._foundry is not None

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        Call the LLM using whichever mode is available.
        Returns the raw response text.
        """
        if self._foundry:
            return await self._foundry.run_agent(
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        elif self._direct_client:
            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format:
                kwargs["response_format"] = response_format

            response = self._direct_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        else:
            raise RuntimeError(
                "No LLM backend configured. Set AZURE_OPENAI_ENDPOINT "
                "and AZURE_OPENAI_API_KEY, or configure Foundry."
            )

    def _call_llm_sync(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        response_format: Optional[dict] = None,
    ) -> str:
        """Synchronous version for direct mode only (testing)."""
        if self._foundry:
            raise RuntimeError("Synchronous calls not supported in Foundry mode")

        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format

        response = self._direct_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content


# ─── Singleton factory ───────────────────────────────────────────────────────

_foundry_client: Optional[FoundryClient] = None


def get_foundry_client() -> Optional[FoundryClient]:
    """
    Get the shared FoundryClient singleton.
    Returns None if Foundry is not configured (falls back to direct mode).
    """
    global _foundry_client

    if _foundry_client is not None:
        return _foundry_client

    endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT", "")
    project = os.getenv("AZURE_FOUNDRY_PROJECT", "")

    if not endpoint or not project or not _foundry_available:
        return None

    try:
        _foundry_client = FoundryClient(
            endpoint=endpoint,
            project_name=project,
        )
        logger.info("Foundry client initialized: %s/%s", endpoint, project)
        return _foundry_client
    except Exception as e:
        logger.warning("Failed to initialize Foundry client: %s. Using direct mode.", e)
        return None
