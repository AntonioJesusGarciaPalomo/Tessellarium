![Tessellarium Banner](docs/images/brand/tessellarium-banner.png)

<!-- Badges -->
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![PyDOE2](https://img.shields.io/badge/PyDOE2-1.3%2B-orange.svg)](https://pypi.org/project/pyDOE2/)
[![OAPackage](https://img.shields.io/badge/OAPackage-2.7%2B-purple.svg)](https://oapackage.readthedocs.io/)
[![Lean 4](https://img.shields.io/badge/Lean_4-Formal_Verification-dc322f.svg)](https://leanprover.github.io/)

[![Infrastructure as Code](https://img.shields.io/badge/IaC-Bicep-f5a623.svg?logo=azuredevops&logoColor=white)](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
[![Built on Azure](https://img.shields.io/badge/Built_on-Microsoft_Azure-0078d4.svg?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/)
[![Microsoft Innovation Challenge](https://img.shields.io/badge/Microsoft-Innovation_Challenge_2026-5e5e5e.svg?logo=microsoft&logoColor=white)](#acknowledgments)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

### Decisive Experiment Compiler

> *Unbiased experimental mosaics, by design.*

---

## The problem

A researcher has competing hypotheses, partial data — protocols in PDF, results in CSV, images from assays — real-world constraints such as limited budgets, depleted materials, and safety-sensitive domains, and one urgent question: **what experiment should I run next?**

Today, the answer comes from intuition, conversations with colleagues, or a language model that generates plausible text without formal guarantees. None of these sources compute which experiment is optimal, what combinatorial coverage it achieves, which hypotheses it can and cannot discriminate, or what the researcher loses if a constraint prevents it from being executed.

Existing scientific assistants — Google AI co-scientist, Microsoft Discovery, Sapio ELaiN, Labguru — interpret protocols, summarize literature, and suggest next steps as free text. None of them formulates the next experiment as an optimization problem with verifiable properties.

This affects experimental scientists and research leaders across chemistry, pharmaceuticals, agronomy, and materials science — anyone who faces critical decisions about what to test next with limited resources, competing explanations, and, increasingly, regulatory scrutiny demanding auditable justification for experimental choices.

---

## The goal

Tessellarium treats the design of the next experiment as a **constrained combinatorial optimization problem**.

Given competing hypotheses, partial evidence, material and safety constraints, and a fixed run budget, it computes the minimal experimental matrix that maximizes hypothesis discrimination using established combinatorial design families: orthogonal arrays, covering arrays, Latin squares, BIBDs, and fractional factorials.

Its output is not a conversational recommendation but a **concrete experimental artifact**: the design matrix, the combinatorial family selected with its justification, the verifiable statistical properties of the design (D-efficiency, GWLP, pairwise coverage), and the explicit cost of each constraint in terms of lost discrimination capability.

---

## Theoretical foundation

The system is grounded in Fisher's theory of experimental design, where experiments are not improvised but constructed with formal mathematical structure.

The core engine follows a five-stage pipeline — **Generate → Filter → Score → Repair → Assess** — that separates mathematical design construction from hypothesis-specific optimization:

```mermaid
flowchart LR
    G["<b>① Generate</b><br/>Classical designs from<br/>known families"]
    F["<b>② Filter</b><br/>Remove rows violating<br/>constraints"]
    S["<b>③ Score</b><br/>Discrimination power<br/>against hypothesis pairs"]
    R["<b>④ Repair</b><br/>Greedy fill to restore<br/>coverage if damaged"]
    A["<b>⑤ Assess</b><br/>D-efficiency, GWLP,<br/>rank on all candidates"]

    G --> F --> S --> R --> A

    style G fill:#1a73e8,stroke:#1557b0,color:#ffffff
    style F fill:#e37400,stroke:#b45d00,color:#ffffff
    style S fill:#1e8e3e,stroke:#137333,color:#ffffff
    style R fill:#d93025,stroke:#b3261e,color:#ffffff
    style A fill:#7b1fa2,stroke:#6a1b9a,color:#ffffff

    linkStyle default stroke:#555,stroke-width:2px
```

Design generation uses two specialized libraries — **OAPackage** for orthogonal array enumeration, D-optimal design synthesis, and statistical quality assessment; and **PyDOE2** for generalized subset designs and fractional factorials — with greedy set cover as the universal fallback. Discrimination scoring against hypothesis pairs is Tessellarium's unique contribution: no classical DOE library optimizes for this.

---

## How it works

```mermaid
flowchart TB
    subgraph Phase1["<b>Phase 1 — Multimodal Ingestion</b>"]
        PDF["📄 Protocol PDF"]
        CSV["📊 Results CSV"]
        IMG["🖼️ Assay Image"]
        CU["Azure Content<br/>Understanding"]
        PDF --> CU
    end

    subgraph Phase2["<b>Phase 2 — Problem Space Construction</b>"]
        PA["<b>Parser Agent</b><br/>GPT-4o"]
        PS[("<b>Problem Space</b><br/>Factors · Hypotheses<br/>Evidence · Constraints<br/>Completed runs")]
        CU --> PA
        CSV --> PA
        IMG -.->|"planned"| PA
        PA --> PS
    end

    subgraph Phase3["<b>Phase 3 — Safety Gate</b>"]
        SG["<b>Safety Governor</b><br/>Deterministic rules<br/>+ Content Safety API"]
        PS --> SG
        SG -->|"ALLOW ✓"| DOE
        SG -->|"DEGRADE ⚠️"| DOE
        SG -->|"BLOCK 🛑"| Block["Evidence summary<br/>+ mandatory human review"]
    end

    subgraph Phase4["<b>Phase 4 — Deterministic Compilation</b>"]
        DOE["<b>DOE Planner</b><br/>Pure Python · Zero LLM"]
        OA["OAPackage"]
        PD["PyDOE2"]
        GR["Greedy"]
        DOE --> OA & PD & GR
        OA & PD & GR --> C1["<b>Candidate 1</b><br/>Max Discrimination"]
        OA & PD & GR --> C2["<b>Candidate 2</b><br/>Max Robustness"]
        OA & PD & GR --> C3["<b>Candidate 3</b><br/>Max Coverage"]
    end

    subgraph Phase5["<b>Phase 5 — Critique & Explanation</b>"]
        CR["<b>Critic Agent</b><br/>GPT-4o-mini"]
        EX["<b>Explainer Agent</b><br/>GPT-4o"]
        DC["<b>Decision Cards</b><br/>6-field structured<br/>explanation per candidate"]
        C1 & C2 & C3 --> CR --> EX --> DC
        EX -.-> SR["AI Search<br/>Grounding citations"]
    end

    subgraph Phase6["<b>Phase 6 — Optional Verification</b>"]
        LN["<b>Lean 4</b><br/>Formal proof of<br/>design properties"]
        C1 & C2 & C3 -.-> LN
    end

    DC --> OUT["<b>Output:</b> 3 candidates + design matrices + decision cards<br/>+ coverage map + discrimination metrics + constraint costs"]

    style Phase1 fill:#263238,stroke:#546e7a,color:#eceff1
    style Phase2 fill:#1a237e,stroke:#3949ab,color:#e8eaf6
    style Phase3 fill:#e65100,stroke:#f57c00,color:#fff3e0
    style Phase4 fill:#1b5e20,stroke:#388e3c,color:#e8f5e9
    style Phase5 fill:#283593,stroke:#3f51b5,color:#e8eaf6
    style Phase6 fill:#4a148c,stroke:#7b1fa2,color:#f3e5f5

    style PDF fill:#37474f,stroke:#78909c,color:#eceff1
    style CSV fill:#37474f,stroke:#78909c,color:#eceff1
    style IMG fill:#37474f,stroke:#78909c,color:#eceff1
    style CU fill:#0d47a1,stroke:#1565c0,color:#ffffff

    style PA fill:#1a237e,stroke:#3949ab,color:#ffffff
    style PS fill:#0d47a1,stroke:#1976d2,color:#ffffff

    style SG fill:#bf360c,stroke:#e64a19,color:#ffffff
    style Block fill:#b71c1c,stroke:#c62828,color:#ffffff

    style DOE fill:#1b5e20,stroke:#2e7d32,color:#ffffff
    style OA fill:#2e7d32,stroke:#43a047,color:#ffffff
    style PD fill:#2e7d32,stroke:#43a047,color:#ffffff
    style GR fill:#2e7d32,stroke:#43a047,color:#ffffff
    style C1 fill:#004d40,stroke:#00796b,color:#ffffff
    style C2 fill:#004d40,stroke:#00796b,color:#ffffff
    style C3 fill:#004d40,stroke:#00796b,color:#ffffff

    style CR fill:#283593,stroke:#3f51b5,color:#ffffff
    style EX fill:#283593,stroke:#3f51b5,color:#ffffff
    style DC fill:#1a237e,stroke:#3949ab,color:#ffffff
    style SR fill:#4a148c,stroke:#7b1fa2,color:#ffffff

    style LN fill:#4a148c,stroke:#7b1fa2,color:#ffffff

    style OUT fill:#263238,stroke:#78909c,color:#ffffff

    linkStyle default stroke:#90a4ae,stroke-width:1.5px
```

**1. Multimodal ingestion.**
The researcher uploads a protocol (PDF), experimental results (CSV), and optionally an assay image. Azure Content Understanding extracts document structure. Code Interpreter for CSV analysis and GPT-4o vision for image interpretation are planned for a future release.

**2. Problem space construction.**
A Parser Agent (GPT-4o) structures all extracted information into a unified representation: factors and their levels, competing hypotheses with epistemic and operative states, existing evidence, constraints, and already-tested combinations.

**3. Safety gate.**
A deterministic Safety Governor analyzes the problem space for clinically or biologically sensitive domains. Sensitive regions are excluded from the factor space *before* compilation — safety is a constraint on the input, not a filter on the output. The system reports what discrimination is lost by each exclusion.

**4. Deterministic compilation.**
The DOE Planner — pure Python, zero LLM — generates designs from known combinatorial families using OAPackage and PyDOE2, filters them against constraints, scores them by hypothesis discrimination, repairs coverage gaps, and assesses statistical quality. It produces three complementary candidates: one optimized for maximum discrimination, one for robustness and replication, and one for combinatorial coverage.

**5. Critique and explanation.**
A Critic Agent identifies weaknesses (confounding, coverage gaps, redundancy). An Explainer Agent generates a six-field decision card for each candidate: recommendation, rationale, evidence used, assumptions, limits, and what observation would change the recommendation — all grounded with citations from the Semantic Citation Layer.

**6. Optional verification.**
Design properties (pairwise coverage, Latin square bijectivity, BIBD balance) can be formally verified in Lean 4 via a dedicated verification service.

---

## Key differentiators

**Compiler, not assistant.** The experiment design engine is deterministic code that generates designs from known combinatorial families, scores them by discrimination power, and computes quality metrics (D-efficiency, GWLP). The LLM interprets inputs and explains outputs but never produces the experimental plan.

**Mathematically grounded designs.** Candidates are generated from OAPackage (orthogonal arrays with proven strength-2 coverage, D-optimal designs via coordinate exchange) and PyDOE2 (fractional factorials, generalized subset designs), not from greedy heuristics alone. Every design carries its D-efficiency and generalized word-length pattern.

**Safety as a compilation constraint.** Sensitive domains are excluded from the search space before the planner runs, not filtered after. The system shows what discrimination is lost per exclusion.

**Three candidates per compilation.** Each cycle produces designs optimized for discrimination, robustness, and coverage, giving the researcher an informed choice aligned with their current priority.

**Transparent constraint costs.** Every restriction is quantified: the researcher sees exactly what hypothesis pairs become indistinguishable and why.

---

## Combinatorial design families

Tessellarium selects from established design families based on the problem structure. Each family has different strengths. The intuition behind the most important ones:

### Orthogonal arrays

**The idea:** every pair of factors is tested in every combination of their levels, even though you don't test all possible runs.

**Analogy:** Imagine you're testing 4 pizza recipes varying crust (thin/thick), sauce (red/white), and cheese (mozzarella/cheddar). A full test is 2×2×2 = 8 pizzas. An orthogonal array of 4 runs lets you taste just 4 pizzas, yet for *every pair* of factors, you've tried all four combinations. You can cleanly separate "is it the crust or the sauce?" — the effects are not confounded.

```
Run  Crust  Sauce  Cheese
 1   Thin   Red    Mozzarella
 2   Thin   White  Cheddar
 3   Thick  Red    Cheddar
 4   Thick  White  Mozzarella
```

Check: Crust × Sauce? Thin-Red ✓, Thin-White ✓, Thick-Red ✓, Thick-White ✓. All four pairs appear. Same for every other pair of columns. That's strength-2 orthogonality — the defining property. Tessellarium uses **OAPackage** to enumerate these arrays and select the one with the best D-efficiency.

### Covering arrays

**The idea:** guarantee that every t-way combination of factor levels appears *at least once*, even under constraints.

**Analogy:** You're testing a web form with 5 fields, each with 3 options. A full test is 3⁵ = 243 configurations. A strength-2 covering array might need only 15 — every pair of fields still sees all 9 combinations. If a bug requires two specific settings to trigger, you'll find it.

Unlike orthogonal arrays, covering arrays allow *imbalanced* replication — some combinations may appear more than once. This flexibility is what makes them work when constraints exclude certain combinations. Tessellarium uses covering arrays as the default when constraints invalidate pure orthogonal designs.

### Fractional factorials

**The idea:** run a mathematically chosen *fraction* of the full factorial, trading higher-order interactions you don't care about for fewer runs.

**Analogy:** You have 6 binary factors (on/off each). Full factorial: 2⁶ = 64 runs. A 2⁶⁻² fractional factorial: 16 runs. You can estimate all 6 main effects and many 2-factor interactions, but some 2-factor interactions are "aliased" with each other — you can't tell them apart. The aliasing structure is known in advance, so the researcher chooses the resolution that matches their priorities.

```
Resolution III:  Main effects estimable, but aliased with 2-factor interactions.
Resolution IV:   Main effects clean; 2-factor interactions aliased with each other.
Resolution V:    Main effects and 2-factor interactions all estimable.
```

Tessellarium uses **PyDOE2** for these when all factors have the same number of levels.

### Latin squares

**The idea:** arrange treatments in a grid where each treatment appears exactly once per row and once per column, blocking two sources of nuisance variation simultaneously.

**Analogy:** A hospital tests 4 drugs across 4 wards (rows) and 4 time periods (columns). Each drug appears in every ward and every period exactly once. Ward-to-ward variation and period-to-period variation are both blocked — the drug effect is estimated cleanly.

```
          Period 1  Period 2  Period 3  Period 4
Ward A       D₁        D₂        D₃        D₄
Ward B       D₂        D₃        D₄        D₁
Ward C       D₃        D₄        D₁        D₂
Ward D       D₄        D₁        D₂        D₃
```

### BIBDs (Balanced Incomplete Block Designs)

**The idea:** when blocks are too small to hold all treatments, arrange them so every pair of treatments appears together in the same number of blocks.

**Analogy:** A wine tasting with 7 wines, but each taster can only try 3 per session. A BIBD arranges the sessions so every pair of wines is compared by the same number of tasters — no pair has an unfair advantage.

```
Session 1: Wine A, Wine B, Wine D
Session 2: Wine B, Wine C, Wine E
Session 3: Wine C, Wine D, Wine F
Session 4: Wine D, Wine E, Wine G
Session 5: Wine E, Wine F, Wine A
Session 6: Wine F, Wine G, Wine B
Session 7: Wine G, Wine A, Wine C
```

Every pair of wines appears together in exactly 1 session. That's the *balance* property — λ = 1.

### D-optimal designs

**The idea:** when no standard family fits (non-standard run sizes, irregular constraints), use numerical optimization to find the design that maximizes the determinant of the information matrix — the design that gives the smallest confidence regions for the estimated effects.

Tessellarium uses **OAPackage's coordinate-exchange algorithm** (`Doptimize`) to generate these. The optimization function is configurable: α=[1,2,0] prioritizes main-effect robustness (for MAX_ROBUSTNESS candidates); α=[1,0,0] targets pure D-efficiency (for MAX_COVERAGE candidates).

---

## Applied examples

### Pharmaceutical process optimization

In pharmaceutical development, Design of Experiments (DoE) is a standard methodology for reaction optimization under Quality by Design (QbD) frameworks. A typical esterification process with six factors (temperature, acid equivalents, reaction time, solvent, catalyst loading, water content) requires a sequential workflow — scoping, screening, RSM optimization, robustness — consuming 30–40 experiments across weeks.

Tessellarium compresses this workflow: given competing hypotheses about the root cause of yield drops ("insufficient acid" vs "time too short" vs "acid×time interaction"), it compiles a single covering array of 12 runs that discriminates between all three hypotheses while respecting material and regulatory constraints (e.g., ICH solvent restrictions). When a reagent becomes unavailable mid-study, the system recalculates and quantifies the discrimination lost.

```mermaid
sequenceDiagram
    participant R as Researcher
    participant T as Tessellarium
    participant DOE as DOE Planner

    R->>T: Upload protocol PDF + results CSV
    T->>T: Parse → 6 factors, 3 hypotheses, 10 completed runs
    T->>DOE: Compile (budget = 12 runs)
    DOE->>DOE: Generate OA(12, 6, mixed) via OAPackage
    DOE->>DOE: Score by discrimination: H1 vs H2 vs H3
    DOE-->>T: 3 candidates + D-efficiency + GWLP
    T-->>R: Decision cards with trade-offs

    R->>T: "Lot C is exhausted"
    T->>DOE: Re-compile with constraint
    DOE->>DOE: Filter → 2 rows removed → Repair coverage
    DOE-->>T: New plan + "H1 vs H3 discrimination drops 14%"
    T-->>R: Updated candidates + constraint cost
```

### Agronomic field trials

A 7×7 field trial with two blocking factors (soil moisture gradient, sun exposure gradient), two treatment factors (7 fertilizer formulations, 7 irrigation levels), and spatial constraints (equipment failure in column 4, safety exclusion of fertilizer G near a watercourse) requires a pair of Mutually Orthogonal Latin Squares (MOLS) that respect all exclusions.

Tessellarium constructs the design, applies constraint exclusions, and reports: "Without irrigation levels R5–R7 in column 4, the interaction fertilizer×irrigation in the central zone cannot be fully characterized. Discrimination between H2 (irrigation insufficient) and H3 (interaction effect) drops 14%."

---

## Architecture
 
The system separates three types of reasoning following the same neurosymbolic principle recently validated for mathematical discovery in combinatorial design theory *(Xia et al., 2026)*:
 
> The LLM interprets and explains.
> Deterministic code computes and optimizes.
> The researcher directs and decides.
 
![Tessellarium Architecture](docs/images/architecture/tessellarium-architecture.png)

### Azure services

| Service | Role |
|---|---|
| **Foundry Agent Service** | Agent orchestration (Parser, Critic, Explainer) — optional, falls back to direct Azure OpenAI |
| **Azure OpenAI** (GPT-4o, GPT-4o-mini) | Interpretation, explanation, vision |
| **Azure Content Understanding** | PDF protocol ingestion |
| **Azure AI Content Safety** | Prompt Shields, domain-specific categories |
| **Azure AI Search** | Hybrid search for grounded citations |
| **Cosmos DB** | Session persistence |
| **Container Apps** | Backend hosting (API + worker + Lean verifier) |
| **Static Web Apps** | Frontend hosting |
| **Front Door Premium + WAF** | CDN, TLS termination, bot protection |
| **Lean 4** *(optional)* | Formal verification of design properties |

### DOE computation libraries

| Library | Role |
|---|---|
| **OAPackage** | Orthogonal array enumeration, D-optimal design synthesis, quality metrics (D-efficiency, GWLP, rank) |
| **PyDOE2** | Generalized subset designs (mixed-level fractional factorials), 2-level fractional factorials, full factorials |
| **Greedy set cover** | Hypothesis-discrimination-optimized selection — Tessellarium's unique contribution |

The result is an auditable experimental artifact with traceable justification at every step, from ingestion to compilation to verification.

---

## Quick start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Azure CLI (`az`) and Azure Developer CLI (`azd`)
- An Azure subscription with Azure OpenAI access

### Local development

```bash
# Clone the repository
git clone https://github.com/Tessellarium/tessellarium.git
cd tessellarium

# Backend
cd backend
cp .env.template .env          # Edit with your Azure credentials (optional for tests)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

### Run the integration test (no Azure credentials needed)

```bash
cd backend
python tests/test_doe_planner.py
```

This test simulates the full pipeline: a reagent stability assay with 3 factors, 3 hypotheses, 4 completed runs, a budget of 4 more runs, constraint addition ("Lot C exhausted"), recalculation with discrimination cost, and a clinical safety block. All components are deterministic — no API calls required.

### Run the full test suite

```bash
cd backend
python -m pytest tests/ -v

# Or run individual test files:
python tests/test_doe_planner.py          # Core DOE compilation + constraints
python tests/test_design_generators.py    # Classical design generation (OAPackage + PyDOE2)
python tests/test_safety_governor.py      # Safety checks (ALLOW / DEGRADE / BLOCK)
python tests/test_critic_agent.py         # Offline critique logic
python tests/test_explainer_agent.py      # Decision card generation
python tests/test_search_service.py       # Semantic Citation Layer chunk extraction
python tests/test_content_understanding.py # PDF parsing
python tests/test_cosmos_store.py         # Serialization roundtrip
python tests/test_api_integration.py      # FastAPI endpoint tests
```

### Deploy to Azure

```bash
azd auth login
azd init
azd up
```

This provisions all Azure resources via Bicep (OpenAI, Content Safety, AI Search, Cosmos DB, Container Apps, Static Web Apps, Front Door + WAF) and deploys the backend and frontend.

---

## Project structure

```
tessellarium/
│
├── .gitignore
├── azure.yaml                          # azd manifest
├── LICENSE                             # MIT
├── README.md
│
├── .devcontainer/
│   └── devcontainer.json               # Dev container (Python 3.12, Node 20, az/azd CLI)
│
├── .vscode/
│   ├── settings.json                   # Workspace settings
│   └── launch.json                     # Debug configurations
│
├── infra/                              # Infrastructure as Code
│   ├── main.bicep                      # Orchestrator (subscription-scoped)
│   ├── main.parameters.json            # Environment parameters
│   ├── abbreviations.json              # Resource naming conventions
│   └── modules/
│       ├── openai.bicep                # Azure OpenAI (GPT-4o, GPT-4o-mini, GPT-4.1, embeddings)
│       ├── content-safety.bicep        # Azure AI Content Safety
│       ├── search.bicep                # Azure AI Search (semantic enabled)
│       ├── cosmos.bicep                # Cosmos DB serverless (sessions, threads, compilations)
│       ├── storage.bicep               # Azure Blob Storage (uploads, processed, literature)
│       ├── container-apps.bicep        # Container Apps (API + worker + Lean verifier)
│       ├── static-web-app.bicep        # Static Web App (React frontend)
│       ├── acr.bicep                   # Azure Container Registry
│       ├── network.bicep               # VNet + private DNS zones
│       ├── identity.bicep              # Managed identities + RBAC
│       ├── agent-stores.bicep          # Foundry agent-dedicated stores
│       ├── foundry.bicep               # Foundry Hub + Project
│       ├── front-door.bicep            # Front Door Premium + WAF
│       └── private-endpoint.bicep      # Reusable PE module
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.template
│   ├── main.py                         # FastAPI orchestrator
│   ├── config/
│   │   └── settings.py                 # Azure configuration (pydantic-settings)
│   ├── app/
│   │   ├── models/
│   │   │   └── problem_space.py        # Central data schema (ProblemSpace, all types)
│   │   ├── doe_planner/
│   │   │   ├── planner.py              # Deterministic compiler (5-stage pipeline)
│   │   │   └── design_generators.py    # OAPackage + PyDOE2 generator hierarchy
│   │   ├── safety/
│   │   │   └── governor.py             # Deterministic policy engine
│   │   ├── agents/
│   │   │   ├── foundry_client.py       # Azure Foundry / direct OpenAI client
│   │   │   ├── parser_agent.py         # GPT-4o structured extraction
│   │   │   ├── critic_agent.py         # Design weakness analysis
│   │   │   └── explainer_agent.py      # Decision card generation
│   │   └── services/
│   │       ├── content_understanding.py # PDF protocol ingestion
│   │       ├── content_safety_service.py # Text moderation + Prompt Shields
│   │       ├── cosmos_store.py          # Session persistence
│   │       └── search_service.py        # Semantic Citation Layer
│   └── tests/
│       ├── test_doe_planner.py          # Core integration test
│       ├── test_design_generators.py    # Classical design generation
│       ├── test_safety_governor.py      # Safety checks
│       ├── test_critic_agent.py         # Critic offline logic
│       ├── test_explainer_agent.py      # Explainer offline logic
│       ├── test_search_service.py       # Chunk extraction
│       ├── test_content_understanding.py # PDF parsing
│       ├── test_cosmos_store.py         # Serialization
│       └── test_api_integration.py      # API endpoints
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/client.ts               # Axios API client
│       ├── types/index.ts              # TypeScript interfaces
│       ├── components/
│       │   ├── CandidateCard.tsx        # Design candidate display
│       │   ├── DesignMatrixTable.tsx    # Matrix visualization
│       │   ├── DecisionCardView.tsx     # 6-field decision card
│       │   ├── VerificationBadge.tsx    # Lean verification status
│       │   └── ErrorBoundary.tsx        # React error boundary
│       └── pages/
│           ├── Home.tsx
│           ├── Upload.tsx               # File + text upload
│           ├── Session.tsx              # Compilation + constraints
│           └── Sessions.tsx             # Session list
│
├── lean-verify/                        # Lean 4 verification service
│   ├── Dockerfile                      # Ubuntu + elan + Lean 4
│   ├── requirements.txt
│   ├── main.py                         # FastAPI (port 8001)
│   ├── app/
│   │   ├── models.py                   # VerificationRequest/Response
│   │   ├── verifier.py                 # Generate .lean → lake build → parse
│   │   └── lean_generator.py           # Jinja2 → Lean 4 code
│   ├── lean_templates/
│   │   ├── covering_array.lean.j2      # Pairwise coverage proof
│   │   ├── latin_square.lean.j2        # Bijectivity proof
│   │   └── bibd.lean.j2               # Balance proof (placeholder)
│   └── tests/
│       └── test_lean_generator.py
│
├── lean/                               # Lean 4 library (stretch goal)
│   └── Tessellarium/
│       ├── lakefile.lean
│       ├── lean-toolchain
│       └── Tessellarium/
│           ├── Basic.lean
│           └── CoveringArray.lean
│
├── docs/
│   ├── images/
│   ├── architecture/
│   │   └── data-flow.md
│   └── roadmap/
│       ├── semantic-citation-layer.md
│       └── neurosymbolic-discovery.md
│
├── demo/
│   ├── reagent-stability-assay.json
│   ├── protocol-sample.pdf
│   └── results-sample.csv
│
└── scripts/
    ├── deploy.sh
    ├── build-backend.sh
    └── run-local.sh
```

---

## API endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/upload` | Upload files (PDF, CSV, image) → parse → ProblemSpace |
| `POST` | `/api/parse` | Raw text → Parser Agent → ProblemSpace |
| `POST` | `/api/problem-space/{id}` | Load ProblemSpace directly (testing) |
| `POST` | `/api/compile` | Safety → DOE Planner → 3 candidates |
| `POST` | `/api/constrain/{id}` | Add constraint → recalculate → show cost |
| `GET` | `/api/coverage/{id}` | Coverage map for visualization |
| `GET` | `/api/session/{id}` | Full ProblemSpace |
| `GET` | `/api/sessions` | List session summaries |
| `GET` | `/api/search?q={query}` | Search the Semantic Citation Layer |

---

## The compilation output (What the researcher sees)

A chemist investigating a yield drop in her reagent stability assay uploads a protocol PDF and a CSV of results. Tessellarium parses the inputs and identifies:

- **3 factors:** Temperature (20°C, 30°C, 40°C), Reagent Lot (A, B, C), Incubation Time (1h, 2h)
- **3 hypotheses:** H1 — temperature drift causes the drop; H2 — lot C is degraded; H3 — incubation time is insufficient
- **4 runs already completed** (yielding 92%, 90%, 74%, 68%)
- **Budget:** 4 more runs
- **Constraint added mid-study:** "Lot C is exhausted" — no more reagent available

She clicks **Compile**. Tessellarium returns three candidates. Here is the first — optimized for maximum hypothesis discrimination:

<p align="center">
  <img src="docs/images/ui/compilation-output.png" height="650" alt="Compilation Output — Candidate 1: Max Discrimination"/>
  &nbsp;
  <img src="docs/images/ui/optimization-output.png" height="650" alt="Optimization Output — Constraint cost analysis"/>
</p>

The pairwise coverage heatmap makes the trade-off visible: Lot C is greyed out (excluded by constraint), and two Temperature × Lot pairs are gaps (red ✗). The constraint cost at the bottom quantifies the damage: discrimination between H2 and H3 drops 40%.

She compares this with Candidate 2 (Max Robustness — D-optimal backbone with replication of the weakest pair) and Candidate 3 (Max Coverage — classical orthogonal array filling the most gaps). Each carries the same structure: design matrix, pairwise coverage map, quality metrics, decision card, and constraint costs.

She chooses Candidate 1 because her priority today is separating temperature drift from lot degradation — and this design achieves 100% discrimination for that pair.

The researcher compares all three candidates and chooses based on their current priority — maximum hypothesis separation, statistical robustness, or broad exploration.

---

## Current limitations

- **Code Interpreter** for CSV analysis is planned but not yet implemented (CSV is currently read as raw text)
- **GPT-4o vision** for image interpretation is planned but not yet implemented
- **MOLS algebraic construction** is not implemented — the planner uses orthogonal arrays and covering arrays from OAPackage
- **BIBD verification** in Lean 4 is a placeholder — covering array and Latin square verification are fully implemented
- **Semantic Citation Layer** (literature knowledge base) is on the roadmap; current grounding uses the researcher's own uploaded data
- **Foundry Agent Service** integration is optional — the system falls back to direct Azure OpenAI calls when Foundry is not configured

---

## References

### Foundational theory

- Fisher, R.A. (1935). *The Design of Experiments*. Oliver & Boyd.
- Box, G.E.P., Hunter, J.S., & Hunter, W.G. (2005). *Statistics for Experimenters: Design, Innovation, and Discovery*. Wiley.

### Combinatorial design

- Colbourn, C.J. & Dinitz, J.H. (2007). *Handbook of Combinatorial Designs*. CRC Press.
- Hedayat, A.S., Sloane, N.J.A., & Stufken, J. (1999). *Orthogonal Arrays: Theory and Applications*. Springer.

### Neurosymbolic collaboration

- Xia, H., Gomes, C.P., Selman, B., & Szeider, S. (2026). *Agentic Neurosymbolic Collaboration for Mathematical Discovery: A Case Study in Combinatorial Design*. arXiv:2603.08322.
- Gomes, C.P. & Sellmann, M. (2004). *Streamlined Constraint Reasoning*. CP 2004, LNCS 3258, pp. 274–289.

### DOE computation libraries

- Eendebak, P.T. & Vazquez, A.R. (2019). *OApackage: A Python package for generation and analysis of orthogonal arrays, optimal designs and conference designs*. Journal of Open Source Software, 4(34), 1097.
- Schoen, E.D., Eendebak, P.T. & Nguyen, M.V.M. (2010). *Complete Enumeration of Pure-Level and Mixed-Level Orthogonal Arrays*. Journal of Combinatorial Designs, 18(2), 123–140.

### Knowledge graphs and semantic citation

- Nanopublication Guidelines. https://nanopub.net/guidelines/
- Wang, L. et al. (2025). *CE-KG: Citation-enhanced Knowledge Graph*. ISWC 2025.
- Semantic Scholar Open Data Platform. https://api.semanticscholar.org/

### DoE in industry

- Murray, P.M. et al. (2016). *The application of design of experiments (DoE) reaction optimization*. Org. Biomol. Chem., 14, 2373–2384.
- Weissman, S.A. & Anderson, N.G. (2015). *Design of Experiments (DoE) and Process Optimization*. Org. Process Res. Dev., 19(11), 1605–1633.

### Tools and frameworks

- Lean 4 Theorem Prover. https://leanprover.github.io/
- lean-lsp-mcp. Dressler, O. (2025). https://github.com/oOo0oOo/lean-lsp-mcp
- lean4-skills. Freer, C. (2025). https://github.com/cameronfreer/lean4-skills

---

## Acknowledgments

Tessellarium was developed as part of the Microsoft Innovation Challenge.

Built on Microsoft Azure services: Foundry Agent Service, Azure OpenAI, Azure Content Understanding, Azure AI Content Safety, Azure AI Search, Cosmos DB, Container Apps, Static Web Apps, and Front Door.

The theoretical foundation draws from R.A. Fisher's Design of Experiments tradition and from the combinatorial design theory community. The neurosymbolic architecture is informed by recent work on agentic collaboration for mathematical discovery (Xia et al., 2026). Design generation leverages OAPackage (Eendebak & Vazquez, 2019) and PyDOE2.

Special thanks to the open-source communities behind Lean 4, Mathlib, OAPackage, PyDOE2, and the MCP ecosystem.

---

**License:** MIT

**Tagline:** *Unbiased experimental mosaics, by design.*