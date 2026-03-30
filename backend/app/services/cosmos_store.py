"""Tessellarium — Azure Cosmos DB storage adapter for experiment data."""

import asyncio
from typing import Optional
from datetime import datetime

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.models.problem_space import ProblemSpace


class CosmosStore:
    """
    Persists ProblemSpace sessions to Azure Cosmos DB for NoSQL.
    Each session is a single JSON document keyed by ProblemSpace.id.

    The azure-cosmos SDK is synchronous; all calls are wrapped in
    asyncio.to_thread() to avoid blocking the event loop.
    """

    def __init__(
        self,
        endpoint: str,
        key: str,
        database_name: str,
        container_name: str,
    ):
        self._client = CosmosClient(endpoint, credential=key)
        self._database = self._client.create_database_if_not_exists(database_name)
        self._container = self._database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/id"),
        )

    async def save_session(self, problem_space: ProblemSpace) -> None:
        """Upsert a ProblemSpace as a JSON document."""
        doc = problem_space.model_dump(mode="json")
        doc["id"] = problem_space.id
        await asyncio.to_thread(self._container.upsert_item, doc)

    async def get_session(self, session_id: str) -> Optional[ProblemSpace]:
        """Read a session by id. Returns None if not found."""
        try:
            doc = await asyncio.to_thread(
                self._container.read_item,
                item=session_id,
                partition_key=session_id,
            )
            return ProblemSpace.model_validate(doc)
        except CosmosResourceNotFoundError:
            return None

    async def delete_session(self, session_id: str) -> None:
        """Delete a session by id. No-op if not found."""
        try:
            await asyncio.to_thread(
                self._container.delete_item,
                item=session_id,
                partition_key=session_id,
            )
        except CosmosResourceNotFoundError:
            pass

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        """Return lightweight summaries of recent sessions."""
        query = (
            "SELECT TOP @limit c.id, c.objective, c.created_at, c.updated_at "
            "FROM c ORDER BY c.updated_at DESC"
        )
        items = await asyncio.to_thread(
            lambda: list(
                self._container.query_items(
                    query=query,
                    parameters=[{"name": "@limit", "value": limit}],
                    enable_cross_partition_query=True,
                )
            )
        )
        return items
