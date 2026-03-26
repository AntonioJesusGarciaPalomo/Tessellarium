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

# In-memory session store (Cosmos DB in production)
sessions: dict[str, ProblemSpace] = {}


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

    In the full implementation, this calls:
    - Content Understanding for the PDF
    - Code Interpreter for the CSV
    - GPT-4o vision for the image
    - Parser Agent to unify into ProblemSpace

    For now, accepts a pre-structured JSON or processes files.
    """
    session_id = str(uuid.uuid4())

    # Create initial ProblemSpace
    ps = ProblemSpace(
        id=session_id,
        max_runs_budget=max_runs_budget,
        protocol_filename=protocol.filename if protocol else None,
        csv_filename=csv_file.filename if csv_file else None,
        image_filename=image.filename if image else None,
    )

    # TODO: Phase 1 - Call Content Understanding for PDF extraction
    # TODO: Phase 1 - Call Code Interpreter for CSV analysis
    # TODO: Phase 1 - Call GPT-4o vision for image interpretation
    # TODO: Phase 2 - Call Parser Agent to structure ProblemSpace

    # For now, store the empty ProblemSpace
    sessions[session_id] = ps

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

    sessions[session_id] = ps
    return UploadResponse(session_id=session_id, problem_space=ps)


@app.post("/api/problem-space/{session_id}")
async def set_problem_space(session_id: str, problem_space: ProblemSpace):
    """
    Directly set a ProblemSpace (for testing and for the Parser Agent output).
    """
    problem_space.id = session_id
    sessions[session_id] = problem_space
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
    ps = sessions.get(request.session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")

    # Apply any new constraints
    for constraint in request.new_constraints:
        ps.constraints.append(constraint)

    # Update budget if provided
    if request.updated_budget is not None:
        ps.max_runs_budget = request.updated_budget

    # Phase 3: Safety Gate
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

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

    # TODO: Phase 4b - Critic Agent reviews each candidate
    # TODO: Phase 5 - Explainer Agent generates decision cards
    # TODO: Phase 5 - AI Search for grounding citations

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
    ps = sessions.get(session_id)
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
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    if verdict != SafetyVerdict.BLOCK:
        planner = DOEPlanner(ps)
        candidates = planner.compile()
    else:
        candidates = []

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
    ps = sessions.get(session_id)
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
    ps = sessions.get(session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Session not found")
    return ps.model_dump()


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
