![Tessellarium Banner](docs/images/brand/tessellarium-banner.png)

### Decisive Experiment Compiler

*Unbiased experimental mosaics, by design.*

---

## The problem

A researcher has competing hypotheses, partial data — protocols in PDF, results in CSV, images from assays — real-world constraints such as limited budgets, depleted materials, and safety-sensitive domains, and one urgent question: **what experiment should I run next?**

Today, the answer comes from intuition, conversations with colleagues, or a language model that generates plausible text without formal guarantees. None of these sources compute which experiment is optimal, what combinatorial coverage it achieves, which hypotheses it can and cannot discriminate, or what the researcher loses if a constraint prevents it from being executed.

Existing scientific assistants — Google AI co-scientist, Microsoft Discovery, Sapio ELaiN, Labguru — interpret protocols, summarize literature, and suggest next steps as free text. None of them formulates the next experiment as an optimization problem with verifiable properties.

---

## The goal

Tessellarium treats the design of the next experiment as a **constrained combinatorial optimization problem**.

Given competing hypotheses, partial evidence, material and safety constraints, and a fixed run budget, it computes the minimal experimental matrix that maximizes hypothesis discrimination using established combinatorial design families: covering arrays, Latin squares, BIBDs, orthogonal arrays, and fractional factorials.

Its output is not a conversational recommendation but a **concrete experimental artifact**: the design matrix, the combinatorial family selected with its justification, the verifiable properties of the design, and the explicit cost of each constraint in terms of lost discrimination capability.

---

## Theoretical foundation

The system is grounded in Fisher's theory of experimental design, where experiments are not improvised but constructed with formal mathematical structure.

The core engine is a **deterministic Python planner — not a language model** — that enumerates untested factor-level combinations, identifies which ones discriminate between specific hypothesis pairs, and selects the smallest subset that maximizes discrimination under constraints.

The LLM's role is strictly limited to interpreting unstructured inputs (protocols, data, images) and explaining outputs in natural language. It never generates the experimental plan.

---

## How it works

**1. Multimodal ingestion.**
The researcher uploads a protocol (PDF), experimental results (CSV), and optionally an assay image. Azure Content Understanding extracts document structure, Code Interpreter analyzes the data, and GPT-4o vision interprets the image.

**2. Problem space construction.**
A Parser Agent (GPT-4o) structures all extracted information into a unified representation: factors and their levels, competing hypotheses with epistemic and operative states, existing evidence, constraints, and already-tested combinations.

**3. Safety gate.**
A deterministic Safety Governor analyzes the problem space for clinically or biologically sensitive domains. Sensitive regions are excluded from the factor space *before* compilation — safety is a constraint on the input, not a filter on the output. The system reports what discrimination is lost by each exclusion.

**4. Deterministic compilation.**
The DOE Planner — pure Python, zero LLM — computes the coverage map, builds the discrimination matrix between hypothesis pairs, and compiles three complementary candidates: one optimized for maximum discrimination, one for robustness and replication, and one for combinatorial coverage of unexplored factor interactions.

**5. Explanation and verification.**
An Explainer Agent generates a six-field decision card for each candidate: recommendation, rationale, evidence used, assumptions, limits, and what observation would change the recommendation. Design properties can optionally be verified formally in Lean 4.

**6. Recalculation under constraints.**
When the researcher adds a constraint ("Lot C is exhausted"), the system recalculates the full plan and quantifies exactly which hypothesis pairs can no longer be distinguished and why.

---

## Key differentiators

**Compiler, not assistant.** The experiment design engine is deterministic code that selects combinatorial families and generates optimal matrices under constraints. The LLM interprets inputs and explains outputs but never produces the experimental plan.

**Safety as a compilation constraint.** Sensitive domains are excluded from the search space before the planner runs, not filtered after. The system shows what discrimination is lost per exclusion.

**Three candidates per compilation.** Each cycle produces designs optimized for discrimination, robustness, and coverage, giving the researcher an informed choice aligned with their current priority.

**Transparent constraint costs.** Every restriction is quantified: the researcher sees exactly what hypothesis pairs become indistinguishable and why.

---

## Applied examples

### Pharmaceutical process optimization

In pharmaceutical development, Design of Experiments (DoE) is a standard methodology for reaction optimization under Quality by Design (QbD) frameworks. A typical esterification process with six factors (temperature, acid equivalents, reaction time, solvent, catalyst loading, water content) requires a sequential workflow — scoping, screening, RSM optimization, robustness — consuming 30-40 experiments across weeks.

Tessellarium compresses this workflow: given competing hypotheses about the root cause of yield drops ("insufficient acid" vs "time too short" vs "acid×time interaction"), it compiles a single covering array of 12 runs that discriminates between all three hypotheses while respecting material and regulatory constraints (e.g., ICH solvent restrictions). When a reagent becomes unavailable mid-study, the system recalculates and quantifies the discrimination lost.

### Agronomic field trials

A 7×7 field trial with two blocking factors (soil moisture gradient, sun exposure gradient), two treatment factors (7 fertilizer formulations, 7 irrigation levels), and spatial constraints (equipment failure in column 4, safety exclusion of fertilizer G near a watercourse) requires a pair of Mutually Orthogonal Latin Squares (MOLS) that respect all exclusions.

Tessellarium constructs the MOLS algebraically, applies constraint exclusions, and reports: "Without irrigation levels R5-R7 in column 4, the interaction fertilizer×irrigation in the central zone cannot be fully characterized. Discrimination between H2 (irrigation insufficient) and H3 (interaction effect) drops 14%."

---

## Architecture

The system separates three types of reasoning following the same neurosymbolic principle recently validated for mathematical discovery in combinatorial design theory *(Xia et al., 2026)*:

> The LLM interprets and explains.
> Deterministic code computes and optimizes.
> The researcher directs and decides.

### Azure services

| Service | Role |
|---|---|
| **Foundry Agent Service** | Agent orchestration (Parser, Critic, Explainer) |
| **Azure OpenAI** (GPT-4o, GPT-4o-mini) | Interpretation, explanation, vision |
| **Azure Content Understanding** | PDF protocol ingestion |
| **Azure AI Content Safety** | Prompt Shields, domain-specific categories |
| **Azure AI Search** | Hybrid search for grounded citations |
| **Cosmos DB** | Session persistence |
| **Container Apps** | Backend hosting |
| **Static Web Apps** | Frontend hosting |
| **Lean 4** *(optional)* | Formal verification of design properties |

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
git clone https://github.com/<your-org>/tessellarium.git
cd tessellarium

# Backend
cd backend
cp .env.template .env
# Edit .env with your Azure credentials
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm start
```

### Run the integration test (no Azure credentials needed)

```bash
cd backend
python tests/test_doe_planner.py
```

This test simulates the full pipeline: a reagent stability assay with 3 factors, 3 hypotheses, 4 completed runs, a budget of 4 more runs, constraint addition ("Lot C exhausted"), recalculation with discrimination cost, and a clinical safety block. All components are deterministic — no API calls required.

### Deploy to Azure

```bash
# Provision infrastructure and deploy
azd auth login
azd init
azd up
```

This provisions all Azure resources via Bicep (OpenAI, Content Safety, AI Search, Cosmos DB, Container Apps, Static Web Apps) and deploys the backend and frontend.

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
│   ├── main.bicep                      # Orchestrator
│   ├── main.parameters.json            # Environment parameters
│   ├── abbreviations.json              # Resource naming
│   └── modules/
│       ├── openai.bicep                # Azure OpenAI (GPT-4o + GPT-4o-mini)
│       ├── content-safety.bicep        # Azure AI Content Safety
│       ├── search.bicep                # Azure AI Search
│       ├── cosmos.bicep                # Cosmos DB serverless
│       ├── container-apps.bicep        # Container Apps + registry
│       └── static-web-app.bicep        # Static Web App
│
├── backend/
│   ├── Dockerfile                      # Container image
│   ├── requirements.txt                # Python dependencies
│   ├── .env.template                   # Environment template
│   ├── main.py                         # FastAPI orchestrator
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                 # Azure configuration
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── problem_space.py        # Central data schema
│   │   ├── doe_planner/
│   │   │   ├── __init__.py
│   │   │   └── planner.py              # Deterministic compiler
│   │   ├── safety/
│   │   │   ├── __init__.py
│   │   │   └── governor.py             # Deterministic policy engine
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   └── parser_agent.py         # GPT-4o structured extraction
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── content_understanding.py
│   │       ├── cosmos_store.py
│   │       └── search_service.py
│   └── tests/
│       └── test_doe_planner.py         # Integration test
│
├── frontend/
│   ├── package.json
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── components/
│       ├── pages/
│       └── styles/
│
├── lean/                               # Formal verification (stretch goal)
│   └── Tessellarium/
│       ├── lakefile.lean
│       ├── lean-toolchain
│       └── Tessellarium/
│           ├── Basic.lean
│           └── CoveringArray.lean
│
├── docs/
│   ├── images/
│   │   ├── brand/
│   │   │   └── tessellarium-banner.png # Project banner
│   │   ├── architecture/
│   │   ├── ui/
│   │   └── demos/
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
| `POST` | `/api/upload` | Upload files (PDF, CSV, image) |
| `POST` | `/api/parse` | Raw text → Parser Agent → ProblemSpace |
| `POST` | `/api/problem-space/{id}` | Load ProblemSpace directly (testing) |
| `POST` | `/api/compile` | Safety → DOE Planner → 3 candidates |
| `POST` | `/api/constrain/{id}` | Add constraint → recalculate → show cost |
| `GET` | `/api/coverage/{id}` | Coverage map for visualization |
| `GET` | `/api/session/{id}` | Full ProblemSpace |

---

## References

### Foundational theory

- Fisher, R.A. (1935). *The Design of Experiments*. Oliver & Boyd.
- Box, G.E.P., Hunter, J.S., & Hunter, W.G. (2005). *Statistics for Experimenters: Design, Innovation, and Discovery*. Wiley.

### Combinatorial design

- Colbourn, C.J. & Dinitz, J.H. (2007). *Handbook of Combinatorial Designs*. CRC Press.
- Hedayat, A.S., Sloane, N.J.A., & Stufken, J. (1999). *Orthogonal Arrays: Theory and Applications*. Springer.

### Neurosymbolic collaboration and Latin squares

- Xia, H., Gomes, C.P., Selman, B., & Szeider, S. (2026). *Agentic Neurosymbolic Collaboration for Mathematical Discovery: A Case Study in Combinatorial Design*. arXiv:2603.08322.
- Gomes, C.P. & Sellmann, M. (2004). *Streamlined Constraint Reasoning*. CP 2004, LNCS 3258, pp. 274–289.

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

Built on Microsoft Azure services: Foundry Agent Service, Azure OpenAI, Azure Content Understanding, Azure AI Content Safety, Azure AI Search, Cosmos DB, Container Apps, and Static Web Apps.

The theoretical foundation draws from R.A. Fisher's Design of Experiments tradition and from the combinatorial design theory community. The neurosymbolic architecture is informed by recent work on agentic collaboration for mathematical discovery (Xia et al., 2026).

Special thanks to the open-source communities behind Lean 4, Mathlib, PyDOE2, and the MCP ecosystem.

---

**License:** MIT

**Tagline:** *Unbiased experimental mosaics, by design.*