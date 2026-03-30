"""
Tessellarium — Main API

The central orchestrator. Receives files, coordinates Azure services,
runs the DOE Planner, and returns results.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import json

from config.settings import settings
from app.models.problem_space import (
    ProblemSpace, CompileRequest, CompileResponse,
    UploadResponse, SafetyVerdict, Constraint,
)
from app.doe_planner.planner import DOEPlanner
from app.safety.governor import SafetyGovernor
from app.agents.parser_agent import ParserAgent
from app.agents.critic_agent import CriticAgent
from app.services.cosmos_store import CosmosStore
from app.services.content_safety_service import ContentSafetyService
from app.services.content_understanding import (
    ContentUnderstandingService, extract_text_from_pdf,
)
from app.services.search_service import SearchService

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unbiased experimental mosaics, by design.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session store — Cosmos DB when configured, in-memory fallback for local dev
_cosmos_store: Optional[CosmosStore] = None
_memory_sessions: dict[str, ProblemSpace] = {}


def _get_store() -> Optional[CosmosStore]:
    global _cosmos_store
    if _cosmos_store is None and settings.cosmos_endpoint and settings.cosmos_key:
        _cosmos_store = CosmosStore(
            endpoint=settings.cosmos_endpoint,
            key=settings.cosmos_key,
            database_name=settings.cosmos_database,
            container_name=settings.cosmos_sessions_container,
        )
    return _cosmos_store


async def _save_session(ps: ProblemSpace) -> None:
    store = _get_store()
    if store:
        await store.save_session(ps)
    else:
        _memory_sessions[ps.id] = ps


async def _load_session(session_id: str) -> Optional[ProblemSpace]:
    store = _get_store()
    if store:
        return await store.get_session(session_id)
    return _memory_sessions.get(session_id)


# Content Safety service — initialized if endpoint is configured
_content_safety: Optional[ContentSafetyService] = None


def _get_content_safety() -> Optional[ContentSafetyService]:
    global _content_safety
    if _content_safety is None and settings.content_safety_endpoint and settings.content_safety_api_key:
        _content_safety = ContentSafetyService(
            endpoint=settings.content_safety_endpoint,
            api_key=settings.content_safety_api_key,
        )
    return _content_safety


# Content Understanding service — initialized if endpoint is configured
_content_understanding: Optional[ContentUnderstandingService] = None


def _get_content_understanding() -> Optional[ContentUnderstandingService]:
    global _content_understanding
    if _content_understanding is None and settings.content_understanding_endpoint:
        _content_understanding = ContentUnderstandingService(
            endpoint=settings.content_understanding_endpoint,
        )
    return _content_understanding


# Search service — Semantic Citation Layer
_search_service: Optional[SearchService] = None


def _get_search() -> Optional[SearchService]:
    global _search_service
    if _search_service is None and settings.search_endpoint and settings.search_api_key:
        _search_service = SearchService(
            endpoint=settings.search_endpoint,
            api_key=settings.search_api_key,
            index_name=settings.search_index_name,
            embedding_endpoint=settings.azure_openai_endpoint or None,
            embedding_key=settings.azure_openai_api_key or None,
        )
    return _search_service


# ─── Health Check ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


# ─── Upload & Parse ──────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(
    protocol: Optional[UploadFile] = File(None),
    csv_file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    max_runs_budget: Optional[int] = Form(None),
):
    """
    Phase 1-2: Ingest files → extract structure → build ProblemSpace.

    1. Content Understanding extracts structured text from the PDF
    2. CSV content is read as text (Code Interpreter TODO)
    3. Parser Agent structures everything into a ProblemSpace
    """
    session_id = str(uuid.uuid4())

    protocol_text = None
    csv_text = None

    # Phase 1a: Extract text from protocol PDF
    if protocol:
        pdf_bytes = await protocol.read()

        # Try Content Understanding first
        cu_service = _get_content_understanding()
        if cu_service:
            protocol_text = await cu_service.analyze_protocol(
                pdf_bytes, protocol.filename or "protocol.pdf",
            )

        # Fallback to local PDF extraction
        if protocol_text is None and pdf_bytes:
            protocol_text = await extract_text_from_pdf(pdf_bytes)

    # Phase 1b: Read CSV as text (Code Interpreter analysis TODO)
    if csv_file:
        csv_bytes = await csv_file.read()
        csv_text = csv_bytes.decode("utf-8", errors="replace")

    # TODO: Phase 1c - Call GPT-4o vision for image interpretation

    # Phase 2: Parser Agent structures inputs into ProblemSpace
    if protocol_text or csv_text:
        try:
            parser = ParserAgent()
            ps = await parser.parse(
                protocol_text=protocol_text,
                csv_analysis=csv_text,
                max_runs_budget=max_runs_budget,
            )
            ps.id = session_id
            ps.protocol_filename = protocol.filename if protocol else None
            ps.csv_filename = csv_file.filename if csv_file else None
            ps.image_filename = image.filename if image else None
        except Exception as e:
            # If Parser Agent fails, create empty ProblemSpace
            ps = ProblemSpace(
                id=session_id,
                max_runs_budget=max_runs_budget,
                protocol_filename=protocol.filename if protocol else None,
                csv_filename=csv_file.filename if csv_file else None,
                image_filename=image.filename if image else None,
            )
    else:
        # No files to parse — create empty ProblemSpace
        ps = ProblemSpace(
            id=session_id,
            max_runs_budget=max_runs_budget,
            protocol_filename=protocol.filename if protocol else None,
            csv_filename=csv_file.filename if csv_file else None,
            image_filename=image.filename if image else None,
        )

    await _save_session(ps)

    return UploadResponse(session_id=session_id, problem_space=ps)


class ParseRequest(BaseModel):
    """Request to parse raw text inputs via the Parser Agent."""
    protocol_text: Optional[str] = None
    csv_analysis: Optional[str] = None
    image_observations: Optional[str] = None
    user_context: Optional[str] = None
    max_runs_budget: Optional[int] = None


@app.post("/api/parse", response_model=UploadResponse)
async def parse_inputs(request: ParseRequest):
    """
    Phase 1-2 via text: Parse raw text inputs through the Parser Agent.
    Uses GPT-4o to structure unstructured text into a ProblemSpace.
    Then stores it in a session ready for compilation.
    """
    session_id = str(uuid.uuid4())

    try:
        parser = ParserAgent()
        ps = await parser.parse(
            protocol_text=request.protocol_text,
            csv_analysis=request.csv_analysis,
            image_observations=request.image_observations,
            user_context=request.user_context,
            max_runs_budget=request.max_runs_budget,
        )
        ps.id = session_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parser Agent failed: {str(e)}")

    await _save_session(ps)
    return UploadResponse(session_id=session_id, problem_space=ps)


@app.post("/api/problem-space/{session_id}")
async def set_problem_space(session_id: str, problem_space: ProblemSpace):
    """
    Directly set a ProblemSpace (for testing and for the Parser Agent output).
    """
    problem_space.id = session_id
    await _save_session(problem_space)
    return {"status": "ok", "session_id": session_id}


# ─── Compile ─────────────────────────────────────────────────────────────────

@app.post("/api/compile", response_model=CompileResponse)
async def compile_experiment(request: CompileRequest):
    """
    Phase 3-5: Safety gate → DOE compilation → explanation.

    This is the HEART of Tessellarium:
    1. Safety Governor checks and constrains
    2. DOE Planner compiles 3 candidates (deterministic)
    3. Critic Agent reviews (LLM - TODO)
    4. Explainer Agent generates decision cards (LLM - TODO)
    """
    ps = await _load_session(request.session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")

    # Apply any new constraints
    for constraint in request.new_constraints:
        ps.constraints.append(constraint)

    # Update budget if provided
    if request.updated_budget is not None:
        ps.max_runs_budget = request.updated_budget

    # Phase 3: Safety Gate
    governor = SafetyGovernor(ps, content_safety_service=_get_content_safety())
    verdict = await governor.evaluate_async()

    if verdict == SafetyVerdict.BLOCK:
        # Return evidence summary only
        return CompileResponse(
            session_id=request.session_id,
            problem_space=ps,
            candidates=[],
            safety_verdict=verdict,
            safety_notes=ps.safety_notes,
        )

    # Phase 4: DOE Compilation (deterministic — the heart)
    planner = DOEPlanner(ps)
    candidates = planner.compile()

    # Phase 4b: Critic Agent reviews each candidate
    critic = CriticAgent()
    for candidate in candidates:
        try:
            await critic.critique(ps, candidate)
        except Exception:
            # Offline fallback if Azure OpenAI is unavailable
            critic.critique_offline(ps, candidate)

    # TODO: Phase 5 - Explainer Agent generates decision cards

    # Index into Semantic Citation Layer
    search_svc = _get_search()
    if search_svc:
        await search_svc.index_problem_space(ps)
        for candidate in candidates:
            await search_svc.index_compilation(ps, candidate)

    await _save_session(ps)

    return CompileResponse(
        session_id=request.session_id,
        problem_space=ps,
        candidates=candidates,
        safety_verdict=verdict,
        safety_notes=ps.safety_notes,
    )


# ─── Add Constraint (recalculate) ────────────────────────────────────────────

@app.post("/api/constrain/{session_id}")
async def add_constraint(session_id: str, constraint: Constraint):
    """
    Add a constraint and recalculate.
    This is the "lot C is exhausted" moment in the demo.
    Returns the new plan + what discrimination was lost.
    """
    ps = await _load_session(session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark level as unavailable if specified
    if constraint.excluded_factor_id and constraint.excluded_level_id:
        factor = ps.get_factor_by_id(constraint.excluded_factor_id)
        if factor:
            for level in factor.levels:
                if level.id == constraint.excluded_level_id:
                    level.available = False

    ps.constraints.append(constraint)

    # Recompile
    governor = SafetyGovernor(ps, content_safety_service=_get_content_safety())
    verdict = await governor.evaluate_async()

    if verdict != SafetyVerdict.BLOCK:
        planner = DOEPlanner(ps)
        candidates = planner.compile()
    else:
        candidates = []

    await _save_session(ps)

    return CompileResponse(
        session_id=session_id,
        problem_space=ps,
        candidates=candidates,
        safety_verdict=verdict,
        safety_notes=ps.safety_notes,
    )


# ─── Get Coverage Map ───────────────────────────────────────────────────────

@app.get("/api/coverage/{session_id}")
async def get_coverage(session_id: str):
    """Return the coverage map for visualization."""
    ps = await _load_session(session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "total_combinations": ps.total_combinations,
        "tested_combinations": ps.tested_combinations,
        "coverage_map": [cell.model_dump() for cell in ps.coverage_map],
        "untested_discriminative": len(ps.get_discriminative_untested()),
    }


# ─── Get Session ─────────────────────────────────────────────────────────────

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get the full ProblemSpace for a session."""
    ps = await _load_session(session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")
    return ps.model_dump()


# ─── List Sessions ───────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions(limit: int = 50):
    """List recent session summaries."""
    store = _get_store()
    if store:
        return await store.list_sessions(limit=limit)
    # In-memory fallback
    return [
        {
            "id": ps.id,
            "objective": ps.objective,
            "created_at": ps.created_at.isoformat(),
            "updated_at": ps.updated_at.isoformat(),
        }
        for ps in list(_memory_sessions.values())[:limit]
    ]


# ─── Search ─────────────────────────────────────────────────────────────────

@app.get("/api/search")
async def search_citations(
    q: str,
    source_type: Optional[str] = None,
    session_id: Optional[str] = None,
    top: int = 5,
):
    """Search the Semantic Citation Layer for grounding evidence."""
    search_svc = _get_search()
    if not search_svc:
        raise HTTPException(
            status_code=503,
            detail="Search service not configured",
        )

    filters = {}
    if source_type:
        filters["source_type"] = source_type
    if session_id:
        filters["session_id"] = session_id

    results = await search_svc.search(query=q, filters=filters, top=top)
    return {"query": q, "results": results, "count": len(results)}


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
