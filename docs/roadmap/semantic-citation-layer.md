# Roadmap — Semantic Citation Layer

## Status: Future work (documented, not implemented)

---

## The insight

The scientific knowledge graph is conventionally built at paper-to-paper granularity: Paper A cites Paper B. But when Paper A cites Paper B, the citation does not refer to all of B. It refers to a specific result, a method, a dataset, a theorem. The real dependency graph of scientific knowledge is between **semantic units** within papers, not between whole papers.

Formally: if U(p) is the set of semantic units of a paper p, then the paper-to-paper edge exists when there is at least one relation u → v with u ∈ U(p) and v ∈ U(q). The conventional citation graph is the **projection π(G_sem)** of the finer semantic graph. The information lost in the collapse is precisely the internal semantic structure that this layer would recover.

---

## Prior art

This idea has multiple precedents in the literature:

- **Nanopublications** (Groth et al., 2010): represent scientific claims as individual, identifiable, citable, and reusable named graphs. Each assertion is encapsulated with provenance and publication information. The only data model that supports publishing at the granularity of individual statements.

- **CE-KG** (Wang et al., ISWC 2025): extracts SPO triples from conclusion sections, fuses citation sentiments and contexts, enables credibility tracing from knowledge claims to microscopic evidence.

- **Micropublications** (Clark et al.): a multi-layered semantic model for claims, evidence, arguments, and annotations in biomedical communications.

- **CiTO** (Citation Typing Ontology): provides an ontological base for typing citation relations — supports, contradicts, extends, reuses-method, measured-by, under-condition.

- **Finding-citation graphs** (2024, biomedicine): a graph of 14.25 million nodes and 76 million edges, with nodes for papers and findings. Demonstrates that sub-paper-level graphs are buildable at scale.

- **Cited Text Spans (CTS)**: a 2024 survey on citation text generation defines CTS as the specific fragment of the cited paper that a citation refers to. Directly validates the claim that citation targets are sub-document.

- **FINECITE** (2025): the first integral definition of citation context based on the semantic structure of the citing text.

---

## What it would do in Tessellarium

Instead of performing RAG over complete papers, Tessellarium would retrieve nodes about **factors, interactions, experimental ranges, measurement methods, and contradictory results** directly from the semantic citation graph. These nodes would then be converted into hypotheses, constraints, priors, and experimental gaps that feed the DOE Planner.

The retrieval would not be a lateral feature but the **epistemological front-end** of the compiler: structured scientific knowledge entering the system as typed evidence, not as unstructured text chunks.

---

## Proposed MVP progression

### MVP 1 — Citation-statement graph

Nodes for paper, citation act, entities, and spans from the citing text. Already provides value: enables search and navigation by *how* something is cited, not just *how many times*. Tools like scite demonstrate commercial viability at this level.

### MVP 2 — Claim/finding graph

Extract local semantic units — claim, result, method, protocol, dataset, theorem, evidence fragment — and align citation acts with candidate targets within the cited paper. This is the jump from statement-level search to semantic-edge retrieval. Uses CTS, FINECITE, and finding-citation graph techniques.

### MVP 3 — Canonical semantic graph

Merge equivalent nodes across papers. Create typed relations: supports, contradicts, generalizes, reuses-method, measured-by, under-condition. At this level, the researcher no longer navigates literature — they navigate a map of assertions and evidence. This is the most valuable and most delicate layer due to fusion errors and over-normalization.

---

## What is demonstrated vs. what is open

**Demonstrated:** the architectural viability of sub-paper graphs at scale (finding-citation graph: 14.25M nodes, 76M edges). Claim extraction from abstracts and conclusions. Citation context and intent classification.

**Open:** exact content-to-content alignment within the cited paper. Cross-paper canonicalization of equivalent claims. CLAIM-BENCH (2025) finds significant LLM limitations in linking claims and evidence dispersed across full papers.

---

## Recommended approach

Start narrow. A domain where vocabulary, methods, and evidence types are relatively stable (e.g., combinatorial chemistry, DOE methodology literature). Use structured full text from S2ORC, combine with metadata from OpenAlex, and build incrementally with human review on the most critical edges.

Do not attempt "all of science" from day one.

---

## Key references

- Nanopublication Guidelines. https://nanopub.net/guidelines/
- Wang, L. et al. (2025). *CE-KG: Citation-enhanced Knowledge Graph*. ISWC 2025.
- Semantic Scholar Open Data Platform. https://api.semanticscholar.org/
- OpenAlex. https://openalex.org/
- OpenCitations. https://opencitations.net/
- scite. https://scite.ai/
- GROBID. https://github.com/kermitt2/grobid
