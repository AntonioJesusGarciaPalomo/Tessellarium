# Roadmap — Neurosymbolic Design Discovery

## Status: Future work (validated by external research, not implemented)

---

## The opportunity

Tessellarium today selects among known combinatorial design families: full factorial, fractional factorial, Latin square, BIBD, orthogonal array, covering array. The DOE Planner has logic to decide which family fits the problem structure. But there are situations where **no standard family fits well**: heterogeneous factors with different numbers of levels, non-contiguous exclusion constraints, small budgets relative to the design space, and hypothesis structures that cut across factors in non-standard ways.

In those situations, the planner falls back to greedy covering selection — effective, but without the structural guarantees that named design families provide. The question is: **can Tessellarium synthesize novel designs** when the catalogue runs out?

---

## External validation: Xia et al. (2026)

A Cornell/TU Wien collaboration (Xia, Gomes, Selman, Szeider, arXiv:2603.08322, March 2026) demonstrated that the same neurosymbolic architecture Tessellarium uses — LLM interprets + solver computes + human directs — can produce **new mathematical results** in combinatorial design theory.

### What they discovered

A tight lower bound of 4n(n−1)/9 on the imbalance of Latin squares for n ≡ 1 (mod 3), achieved via a novel class of near-perfect permutations. The result was formally verified in Lean 4 (~340 lines).

### How the collaboration worked

**Phase 1 — Dead end (3 days).** The LLM agent and symbolic tools (Rust solver, SageMath) exhaustively explored algebraic constructions for perfect permutations. Result: negative. No algebraic structure found.

**Phase 2 — Human pivot (minutes).** The researcher changed the question: from "find objects with zero imbalance" to "what is the minimum positive imbalance?" This reframing — transforming a search problem into an optimization problem — was the most consequential step. The LLM did not propose it.

**Phase 3 — Discovery (one hour).** The LLM inspected shift correlations for dozens of permutations and noticed that all values were even — a parity constraint no human had observed. The proof is four lines of modular arithmetic, but finding the pattern required systematic numerical inspection that the LLM excels at.

**Phase 4 — Verification.** Multi-model review caught two errors in the proof draft (a circulant generality trap and a σ/σ⁻¹ mismatch). Lean 4 formally verified the corrected proof.

**Phase 5 — Construction.** Simulated annealing found near-perfect permutations for all n ≡ 1 (mod 3) up to n = 52, each achieving the proven optimal imbalance.

### Key finding on multi-model reliability

Multi-model deliberation among frontier LLMs proved **reliable for criticism** (catching errors in proofs) but **unreliable for constructive claims** (confidently asserting wrong scaling bounds). This asymmetry has direct implications for system design: use LLMs as critics, not as generators of mathematical claims.

---

## How this extends Tessellarium

### Current architecture (implemented)

```
Problem Space → DOE Planner → selects from known families → 3 candidates
```

### Extended architecture (future)

```
Problem Space → DOE Planner → known family fits? 
                                  ├── Yes → compile from family → 3 candidates
                                  └── No  → Neurosymbolic Discovery Loop:
                                              1. LLM proposes candidate construction
                                              2. Solver verifies properties (coverage, balance, orthogonality)
                                              3. If properties fail → LLM refines → loop
                                              4. If properties pass → Lean 4 verifies formally
                                              5. Return novel design with verified properties
```

The LLM generates candidate designs based on the problem structure. The solver checks combinatorial properties. The loop iterates until a design with verifiable properties is found or a timeout is reached. This is exactly the pattern Xia et al. used, applied to design synthesis instead of theorem proving.

---

## Practical considerations

### Timescale

The paper's discovery took 5 days and ~15 interactive sessions. Design synthesis for a specific experimental problem would be simpler (constructing a matrix, not proving a theorem), but still an offline process — minutes to hours, not seconds. The researcher would launch the search and receive results asynchronously.

### Type of result

The paper discovered a theorem (universal, permanent). Tessellarium would produce a design matrix (a solution to a specific instance). Formal verification of an instance matrix (checking that it satisfies properties) is computationally simpler than proving a universal bound.

### Skill graph composition

Rather than synthesizing designs from scratch, the planner could compose known combinatorial primitives: "start with a Latin square base, apply constraint exclusion, repair coverage with greedy fill, verify partial orthogonality in the non-excluded region." This compositional approach connects to the CAP-PKG capability packaging framework — each combinatorial primitive as a packaged skill, with semantic discovery of which primitives to compose.

---

## What this would enable

- Design of experiments for **non-standard factor structures** where no catalogue design exists
- Automatic adaptation when constraints invalidate standard designs mid-study
- Discovery of **domain-specific design families** optimized for recurring experimental patterns in a given field
- Formal verification that synthesized designs have the properties they claim

---

## Key references

- Xia, H., Gomes, C.P., Selman, B., & Szeider, S. (2026). *Agentic Neurosymbolic Collaboration for Mathematical Discovery: A Case Study in Combinatorial Design*. arXiv:2603.08322.
- Gomes, C.P. & Sellmann, M. (2004). *Streamlined Constraint Reasoning*. CP 2004.
- Romera-Paredes, B. et al. (2024). *Mathematical discoveries from program search with large language models*. Nature, 625, 468–475.
- Davies, A. et al. (2021). *Advancing mathematics by guiding human intuition with AI*. Nature, 600, 70–74.
- lean-lsp-mcp. Dressler, O. (2025). https://github.com/oOo0oOo/lean-lsp-mcp
- lean4-skills. Freer, C. (2025). https://github.com/cameronfreer/lean4-skills
