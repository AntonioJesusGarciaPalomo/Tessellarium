"""
Tessellarium — Azure AI Search client for hybrid semantic/vector search.

The Semantic Citation Layer: a unified search index storing chunks from
protocols, compilations, decision cards, literature claims, and evidence.
The Explainer Agent queries this to ground decision cards with citations.
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SearchFieldDataType as DT,
)
from azure.search.documents.models import VectorizedQuery

from app.models.problem_space import (
    ProblemSpace, ExperimentCandidate, DecisionCard,
)

logger = logging.getLogger(__name__)

# Default embedding dimensions (ada-002 = 1536, text-embedding-3-large = 3072)
DEFAULT_VECTOR_DIMENSIONS = 1536


class SearchService:
    """
    Azure AI Search client for the Semantic Citation Layer.
    Supports hybrid search (text + vector) with text-only fallback.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str = "tessellarium-protocols",
        embedding_endpoint: Optional[str] = None,
        embedding_key: Optional[str] = None,
        embedding_model: str = "text-embedding-ada-002",
        vector_dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
    ):
        self._endpoint = endpoint
        self._credential = AzureKeyCredential(api_key)
        self._index_name = index_name
        self._embedding_endpoint = embedding_endpoint
        self._embedding_key = embedding_key
        self._embedding_model = embedding_model
        self._vector_dimensions = vector_dimensions
        self._vectors_enabled = embedding_endpoint is not None

        self._index_client = SearchIndexClient(
            endpoint=endpoint, credential=self._credential,
        )
        self._search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=self._credential,
        )

    async def create_or_update_index(self) -> None:
        """Create or update the search index with the Semantic Citation Layer schema."""
        fields = [
            SimpleField(name="id", type=DT.String, key=True),
            SimpleField(name="session_id", type=DT.String, filterable=True),
            SimpleField(
                name="source_type", type=DT.String, filterable=True,
            ),
            SimpleField(
                name="artifact_type", type=DT.String, filterable=True,
            ),
            SearchableField(name="title", type=DT.String),
            SearchableField(name="content", type=DT.String),
            SimpleField(
                name="factor_ids",
                type=SearchFieldDataType.Collection(DT.String),
                filterable=True,
            ),
            SimpleField(
                name="hypothesis_ids",
                type=SearchFieldDataType.Collection(DT.String),
                filterable=True,
            ),
            SimpleField(
                name="constraint_ids",
                type=SearchFieldDataType.Collection(DT.String),
                filterable=True,
            ),
            SimpleField(name="citation_text", type=DT.String),
            SimpleField(name="source_url", type=DT.String),
            SimpleField(
                name="confidence", type=DT.Double, sortable=True,
            ),
            SimpleField(
                name="created_at", type=DT.DateTimeOffset, sortable=True,
            ),
        ]

        vector_search = None
        if self._vectors_enabled:
            fields.append(
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(DT.Single),
                    searchable=True,
                    vector_search_dimensions=self._vector_dimensions,
                    vector_search_profile_name="default-vector-profile",
                ),
            )
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(name="default-hnsw"),
                ],
                profiles=[
                    VectorSearchProfile(
                        name="default-vector-profile",
                        algorithm_configuration_name="default-hnsw",
                    ),
                ],
            )

        index = SearchIndex(
            name=self._index_name,
            fields=fields,
            vector_search=vector_search,
        )

        try:
            await asyncio.to_thread(self._index_client.create_or_update_index, index)
            logger.info("Search index '%s' created/updated.", self._index_name)
        except Exception as e:
            logger.warning("Failed to create/update index: %s", e)

    async def index_problem_space(self, ps: ProblemSpace) -> None:
        """Extract indexable chunks from a ProblemSpace and upload them."""
        docs = self._extract_problem_space_chunks(ps)
        if docs:
            await self._upload_documents(docs)

    async def index_compilation(
        self, ps: ProblemSpace, candidate: ExperimentCandidate,
    ) -> None:
        """Index a compilation result (design matrix + justification)."""
        docs = self._extract_compilation_chunks(ps, candidate)
        if docs:
            await self._upload_documents(docs)

    async def index_decision_card(
        self, session_id: str, card: DecisionCard,
    ) -> None:
        """Index a decision card for citation retrieval."""
        docs = self._extract_decision_card_chunks(session_id, card)
        if docs:
            await self._upload_documents(docs)

    async def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        top: int = 5,
    ) -> list[dict]:
        """
        Hybrid search: text + vector (if embeddings available).
        Falls back to text-only search if vectors are not configured.
        """
        try:
            filter_expr = self._build_filter(filters) if filters else None

            vector_queries = None
            if self._vectors_enabled:
                embedding = await self.generate_embedding(query)
                if embedding:
                    vector_queries = [
                        VectorizedQuery(
                            vector=embedding,
                            k_nearest_neighbors=top,
                            fields="content_vector",
                        ),
                    ]

            results = await asyncio.to_thread(
                lambda: list(self._search_client.search(
                    search_text=query,
                    filter=filter_expr,
                    top=top,
                    vector_queries=vector_queries,
                    select=[
                        "id", "content", "citation_text", "source_type",
                        "confidence", "title", "session_id",
                    ],
                ))
            )

            hits = []
            for result in results:
                hits.append({
                    "id": result["id"],
                    "content": result.get("content", ""),
                    "citation_text": result.get("citation_text", ""),
                    "source_type": result.get("source_type", ""),
                    "confidence": result.get("confidence"),
                    "score": result.get("@search.score", 0),
                    "title": result.get("title", ""),
                })
            return hits

        except Exception as e:
            logger.warning("Search failed: %s", e)
            return []

    async def generate_embedding(self, text: str) -> Optional[list[float]]:
        """Call Azure OpenAI embeddings endpoint. Returns None if not configured."""
        if not self._embedding_endpoint or not self._embedding_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._embedding_endpoint}/openai/deployments/"
                    f"{self._embedding_model}/embeddings"
                    f"?api-version=2024-02-01",
                    headers={"api-key": self._embedding_key},
                    json={"input": text[:8000]},
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception as e:
            logger.warning("Embedding generation failed: %s", e)
            return None

    # ─── Chunk Extraction ────────────────────────────────────────────

    def _extract_problem_space_chunks(
        self, ps: ProblemSpace,
    ) -> list[dict]:
        """Extract indexable chunks from a ProblemSpace."""
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        protocol_ref = ps.protocol_filename or f"Session {ps.id[:8]}"

        # Objective chunk
        if ps.objective:
            docs.append({
                "id": f"{ps.id}-objective",
                "session_id": ps.id,
                "source_type": "protocol",
                "artifact_type": "objective",
                "title": "Experimental Objective",
                "content": ps.objective,
                "factor_ids": [f.id for f in ps.factors],
                "hypothesis_ids": [h.id for h in ps.hypotheses],
                "constraint_ids": [],
                "citation_text": f"Objective: {ps.objective} — {protocol_ref}",
                "source_url": "",
                "confidence": 1.0,
                "created_at": now,
            })

        # Factor chunks
        for factor in ps.factors:
            level_names = ", ".join(lvl.name for lvl in factor.levels)
            content = (
                f"Factor: {factor.name}. "
                f"Levels: {level_names}. "
                f"Blocking: {factor.is_blocking_factor}. "
                f"Safety-sensitive: {factor.is_safety_sensitive}."
            )
            docs.append({
                "id": f"{ps.id}-factor-{factor.id}",
                "session_id": ps.id,
                "source_type": "protocol",
                "artifact_type": "factor",
                "title": f"Factor: {factor.name}",
                "content": content,
                "factor_ids": [factor.id],
                "hypothesis_ids": [],
                "constraint_ids": [],
                "citation_text": (
                    f"Factor: {factor.name} ({level_names}) — {protocol_ref}"
                ),
                "source_url": "",
                "confidence": 1.0,
                "created_at": now,
            })

        # Hypothesis chunks
        for hyp in ps.hypotheses:
            dist_names = []
            for fid in hyp.distinguishing_factors:
                f = ps.get_factor_by_id(fid)
                dist_names.append(f.name if f else fid)
            content = (
                f"Hypothesis {hyp.id}: {hyp.statement}. "
                f"State: {hyp.epistemic_state.value}/{hyp.operative_state.value}. "
                f"Distinguishing factors: {', '.join(dist_names) or 'none'}."
            )
            docs.append({
                "id": f"{ps.id}-hypothesis-{hyp.id}",
                "session_id": ps.id,
                "source_type": "protocol",
                "artifact_type": "hypothesis",
                "title": f"Hypothesis: {hyp.statement[:80]}",
                "content": content,
                "factor_ids": list(hyp.distinguishing_factors),
                "hypothesis_ids": [hyp.id],
                "constraint_ids": [],
                "citation_text": (
                    f"{hyp.id}: {hyp.statement} "
                    f"[{hyp.epistemic_state.value}] — {protocol_ref}"
                ),
                "source_url": "",
                "confidence": 0.8,
                "created_at": now,
            })

        # Evidence chunks
        for ev in ps.evidence:
            docs.append({
                "id": f"{ps.id}-evidence-{ev.id}",
                "session_id": ps.id,
                "source_type": "evidence",
                "artifact_type": ev.source_type,
                "title": f"Evidence: {ev.content[:80]}",
                "content": ev.content,
                "factor_ids": [],
                "hypothesis_ids": ev.supports_hypotheses + ev.challenges_hypotheses,
                "constraint_ids": [],
                "citation_text": (
                    f"{ev.id} [{ev.source_type}]: {ev.content} "
                    f"(confidence: {ev.confidence:.1f}) — {protocol_ref}"
                ),
                "source_url": ev.source_reference or "",
                "confidence": ev.confidence,
                "created_at": now,
            })

        # Constraint chunks
        for con in ps.constraints:
            docs.append({
                "id": f"{ps.id}-constraint-{con.id}",
                "session_id": ps.id,
                "source_type": "protocol",
                "artifact_type": "constraint",
                "title": f"Constraint: {con.description[:80]}",
                "content": (
                    f"{con.description}. "
                    f"Type: {con.constraint_type}. "
                    f"Safety: {con.is_safety_constraint}."
                ),
                "factor_ids": [con.excluded_factor_id] if con.excluded_factor_id else [],
                "hypothesis_ids": [],
                "constraint_ids": [con.id],
                "citation_text": (
                    f"Constraint {con.id}: {con.description} — {protocol_ref}"
                ),
                "source_url": "",
                "confidence": 1.0,
                "created_at": now,
            })

        return docs

    def _extract_compilation_chunks(
        self, ps: ProblemSpace, candidate: ExperimentCandidate,
    ) -> list[dict]:
        """Extract indexable chunks from a compilation candidate."""
        now = datetime.now(timezone.utc).isoformat()
        dm = candidate.design_matrix

        content = (
            f"Compilation candidate: {candidate.strategy.value}. "
            f"Design family: {dm.design_family.value}. "
            f"Runs: {dm.num_runs}. "
            f"Discrimination score: {candidate.total_discrimination_score:.3f}. "
            f"Justification: {candidate.justification}"
        )

        cost_text = ""
        if candidate.constraint_costs:
            cost_parts = []
            for cost in candidate.constraint_costs:
                cost_parts.append(cost.constraint_description)
            cost_text = " Constraint costs: " + "; ".join(cost_parts)

        return [{
            "id": f"{ps.id}-compilation-{candidate.id}",
            "session_id": ps.id,
            "source_type": "compilation",
            "artifact_type": candidate.strategy.value,
            "title": f"Candidate: {candidate.strategy.value} ({dm.num_runs} runs)",
            "content": content + cost_text,
            "factor_ids": [f.id for f in ps.factors],
            "hypothesis_ids": [h.id for h in ps.hypotheses],
            "constraint_ids": [c.id for c in ps.constraints],
            "citation_text": (
                f"DOE compilation ({candidate.strategy.value}): "
                f"{dm.design_family.value}, {dm.num_runs} runs, "
                f"discrimination={candidate.total_discrimination_score:.3f} — "
                f"Session {ps.id[:8]}"
            ),
            "source_url": "",
            "confidence": candidate.total_discrimination_score,
            "created_at": now,
        }]

    def _extract_decision_card_chunks(
        self, session_id: str, card: DecisionCard,
    ) -> list[dict]:
        """Extract indexable chunks from a decision card."""
        now = datetime.now(timezone.utc).isoformat()

        content = (
            f"Recommendation: {card.recommendation}. "
            f"Rationale: {card.why}. "
            f"Evidence used: {', '.join(card.evidence_used)}. "
            f"Assumptions: {', '.join(card.assumptions)}. "
            f"Limits: {', '.join(card.counterevidence_or_limits)}. "
            f"Would change mind: {card.what_would_change_mind}"
        )

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]

        return [{
            "id": f"{session_id}-decision-{content_hash}",
            "session_id": session_id,
            "source_type": "decision_card",
            "artifact_type": "decision_card",
            "title": f"Decision: {card.recommendation[:80]}",
            "content": content,
            "factor_ids": [],
            "hypothesis_ids": [],
            "constraint_ids": [],
            "citation_text": (
                f"Decision card: {card.recommendation} — Session {session_id[:8]}"
            ),
            "source_url": "",
            "confidence": 0.9,
            "created_at": now,
        }]

    # ─── Helpers ─────────────────────────────────────────────────────

    async def _upload_documents(self, docs: list[dict]) -> None:
        """Upload documents to the search index."""
        if self._vectors_enabled:
            for doc in docs:
                content = doc.get("content", "")
                if content:
                    embedding = await self.generate_embedding(content)
                    if embedding:
                        doc["content_vector"] = embedding

        try:
            await asyncio.to_thread(self._search_client.upload_documents, docs)
            logger.info("Indexed %d documents.", len(docs))
        except Exception as e:
            logger.warning("Failed to index documents: %s", e)

    @staticmethod
    def _build_filter(filters: dict) -> str:
        """Build an OData filter expression from a dict."""
        parts = []
        for key, value in filters.items():
            if isinstance(value, str):
                parts.append(f"{key} eq '{value}'")
            elif isinstance(value, list):
                # Collection filter: any value in the collection matches
                or_parts = [f"{key}/any(x: x eq '{v}')" for v in value]
                parts.append(f"({' or '.join(or_parts)})")
            else:
                parts.append(f"{key} eq {value}")
        return " and ".join(parts)
