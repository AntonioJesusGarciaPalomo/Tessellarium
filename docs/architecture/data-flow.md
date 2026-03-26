# Tessellarium — Architecture and Data Flow

## Design principle

The architecture enforces a strict separation: **the LLM interprets and explains, deterministic code computes and optimizes, and the researcher directs and decides**. No component crosses its boundary. The LLM never generates the experimental plan. The planner never interprets natural language. The safety governor never suggests — it constrains.

---

## Components

### Frontend — React SPA on Azure Static Web Apps

Responsibility: the researcher's interface. File upload, hypothesis tree visualization, coverage map, design matrices, decision cards, constraint management. No business logic. It renders what the backend returns.

### Backend API — Python FastAPI on Azure Container Apps

Responsibility: central orchestrator. Receives files from the frontend, coordinates all Azure service calls, executes the DOE Planner (deterministic Python), persists state in Cosmos DB, and returns results. This is the brain of the system.

Container Apps was chosen over Functions because the compilation pipeline requires in-memory state during a session and benefits from a persistent server with automatic scaling and private networking.

### Azure Content Understanding (GA)

Responsibility: protocol PDF ingestion. Receives the researcher's PDF and returns structured output: markdown with layout, described figures, and fields extracted according to a custom analyzer schema (objective, factors, levels, controls, constraints, materials, acceptance criteria).

Flow: Frontend → Backend → Content Understanding API → structured JSON → Backend.

### Azure OpenAI — GPT-4o and GPT-4o-mini

Three agents with strictly bounded roles, orchestrated via Azure Foundry Agent Service:

**Parser Agent** (GPT-4o): receives Content Understanding output + CSV analysis + image observations and produces the **Problem Space JSON** — the unified structured representation of the experimental space. This agent interprets and structures. It does not recommend.

**Critic Agent** (GPT-4o-mini): receives the DOE Planner's proposal and searches for weaknesses. Missing controls? Confounding between factors? Insufficient sample size? A constraint that invalidates the proposal? This agent refutes. It does not propose.

**Explainer Agent** (GPT-4o-mini): receives the validated proposal and generates the six-field decision card in natural language: recommendation, rationale, evidence used, assumptions, limits, and what would change the recommendation. This agent translates. It does not decide.

### Code Interpreter (GA, within Foundry Agent Service)

Responsibility: CSV analysis. The researcher uploads a CSV with experimental results. Code Interpreter executes Python in a sandbox to compute descriptive statistics, detect trends, identify anomalies, and generate plots. Returns a structured JSON of observations + plot files.

Flow: Backend → Foundry Agent (with Code Interpreter tool) → Python analysis → observation JSON + plots → Backend.

### GPT-4o Vision (via Azure OpenAI)

Responsibility: interpret experimental images. Receives the assay image (plate photo, electrophoresis gel, instrument readout) and returns structured observations: what it sees, anomalies detected, conditions suggested.

Flow: Backend → Azure OpenAI API (GPT-4o, message with image) → observation JSON → Backend.

### DOE Planner — Deterministic Python in the Backend

**This is the heart of Tessellarium and the decision that differentiates the system.**

The experiment compiler is pure Python code executing deterministic combinatorial logic. It receives the Problem Space JSON (factors, levels, hypotheses, constraints, tested combinations, budget) and computes:

- Which combinations remain untested
- Which of those discriminate between specific hypothesis pairs
- The appropriate design family (Latin square, BIBD, fractional factorial, orthogonal array, covering array)
- The optimal design matrix under constraints
- The cost of each constraint in terms of lost discrimination

Uses PyDOE2 for matrix generation, itertools for combination enumeration, scipy for optimization, and custom logic for family selection and discrimination calculation.

Produces three candidates per compilation (discrimination, robustness, coverage) with their matrices and discrimination metrics.

### Safety Governor — Deterministic Python in the Backend

Responsibility: four-layer safety and integration of safety as a compilation constraint.

Layer 1 — Azure AI Content Safety: general moderation (hate, sexual, violence, self-harm) with configured thresholds.

Layer 2 — Prompt Shields: detection of direct attacks (jailbreak) and indirect attacks (hidden instructions in uploaded documents).

Layer 3 — Custom domain categories: clinical_advice, patient_specific_treatment, disallowed_bio_procedure, unsafe_reagent_use.

Layer 4 — Safety Governor (deterministic rules): takes Content Safety signals and applies domain logic to decide: **allow** (compile normally), **degrade** (exclude sensitive region, recompile, show cost), or **block** (evidence summary only + mandatory human review).

Safety constraints become DOE Planner inputs before compilation, not output filters.

### Azure AI Search (GA, classic hybrid)

Responsibility: grounding and citations. Protocols, notes, and results are indexed with chunking, vectorization, and hybrid search (BM25 + vector + semantic ranking). When the Explainer Agent generates decision cards, claims are anchored to specific source fragments with traceable citations.

### Cosmos DB for NoSQL (GA)

Responsibility: session persistence. Each researcher's session is a JSON document containing the complete Problem Space: hypotheses with epistemic and operative states, evidence, protocols, constraints, compilation history, previous design results. The researcher returns tomorrow and the experimental space is where they left it.

### Lean 4 Verification Service (optional) — Container on Azure Container Apps

Responsibility: formal verification of design matrix properties. Receives a JSON matrix + the property to verify (Latin square bijectivity, covering array t-way coverage, BIBD incidence balance). Generates a .lean file, invokes Lean with native_decide for decidable properties over finite structures, and returns verified/failed/timeout.

Deployed as a separate container with elan + Lean 4 preinstalled. Exposes a REST endpoint that the backend calls optionally after the DOE Planner produces a matrix.

---

## Data flow — end to end

```
Phase 1 — Ingestion
┌──────────┐   ┌──────────┐   ┌──────────┐
│Protocol  │   │Results   │   │Experiment│
│PDF       │   │CSV       │   │Image     │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │
     ▼              ▼              ▼
  Content       Code           GPT-4o
  Understanding Interpreter    Vision
     │              │              │
     └──────────────┼──────────────┘
                    ▼
Phase 2 — Interpretation
          ┌─────────────────┐
          │  Parser Agent   │
          │  (GPT-4o)       │
          └────────┬────────┘
                   ▼
          ┌─────────────────┐
          │ Problem Space   │──────▶ Cosmos DB
          │ JSON            │
          └────────┬────────┘
                   ▼
Phase 3 — Safety Gate
          ┌─────────────────────────┐
          │ Safety Governor         │
          │ + Content Safety API    │──────▶ Block / Degrade
          └────────┬────────────────┘
                   ▼
Phase 4 — Compilation (deterministic)
          ┌─────────────────────────┐
          │ DOE Planner             │
          │ (Python, NOT LLM)       │──────▶ Lean 4 (optional)
          │ → 3 candidates          │
          └────────┬────────────────┘
                   ▼
          ┌─────────────────┐
          │  Critic Agent   │
          │  (GPT-4o-mini)  │
          └────────┬────────┘
                   ▼
Phase 5 — Explanation
          ┌─────────────────┐
          │ Explainer Agent │
          │ (GPT-4o-mini)   │──────▶ AI Search (grounding)
          └────────┬────────┘
                   ▼
Phase 6 — Output
  ┌───────────────────────────────────────┐
  │ 3 candidates + matrices               │
  │ + decision cards + coverage map        │
  │ + discrimination metrics               │
  │ + constraint costs                     │
  └───────────────────┬───────────────────┘
                      ▼
              React Frontend
```

---

## Key architectural decisions

**Decision 1: The DOE Planner is Python code, not LLM.** The experiment compiler uses PyDOE2, itertools, and custom combinatorial logic. The LLM never touches design matrix generation. This is what separates Tessellarium from every other scientific assistant.

**Decision 2: Safety is an input to the compiler, not a filter on the output.** The Safety Governor analyzes the Problem Space before the DOE Planner runs. If it detects a sensitive zone, it converts it into an exclusion constraint that the compiler respects. The result is a plan that never proposes anything dangerous because the dangerous region never entered the search space.

**Decision 3: Three types of components, three levels of determinism.** Azure services (Content Understanding, Code Interpreter, Content Safety, AI Search, Cosmos DB) are infrastructure. LLM agents (Parser, Critic, Explainer) interpret and explain. The DOE Planner and Safety Governor are deterministic code. Responsibilities never cross.

**Decision 4: Classic hybrid RAG, not agentic retrieval.** AI Search with hybrid search (BM25 + vector + semantic ranking) is GA, stable, and provides grounding with citations without depending on preview features.

**Decision 5: Lean 4 is optional and asynchronous.** The main flow works without Lean. If Lean is available and verification completes in time, the badge is added. If not, the system continues. The demo never blocks on a formal verification that takes too long.
