"""
Tessellarium — DOE Planner

The Decisive Experiment Compiler.
This module is 100% deterministic Python. No LLM calls.

Given a ProblemSpace (factors, levels, hypotheses, constraints, budget,
already-tested combinations), it computes:

1. The full combinatorial space and coverage map
2. Which untested combinations discriminate between hypothesis pairs
3. Three experiment candidates optimized for different objectives
4. The cost of each constraint in terms of lost discrimination

Design family selection follows Fisher's DOE tradition:
- Full factorial when affordable
- Fractional factorial for many factors, few runs
- Latin square when there are exactly 2 blocking factors
- Covering array when there are constraints or invalid combinations
- BIBD when block size < number of treatments
"""

from itertools import product as cartesian_product
from typing import Optional
import logging
from collections import defaultdict

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Constraint,
    ExperimentCandidate, DesignMatrix, DiscriminationPair,
    CoverageCell, CandidateStrategy, DesignFamily, ExperimentalRun,
    ConstraintCost, AffectedPair,
)


logger = logging.getLogger(__name__)


class DOEPlanner:
    """
    Deterministic experiment compiler.
    Receives a ProblemSpace, returns 3 ExperimentCandidates.
    """

    def __init__(self, problem_space: ProblemSpace):
        self.ps = problem_space

    def compile(self) -> list[ExperimentCandidate]:
        """
        Main compilation pipeline:
        1. Build coverage map
        2. Compute discrimination matrix
        3. Generate 3 candidates
        4. Calculate constraint costs
        """
        self._build_coverage_map()
        discrimination_matrix = self._compute_discrimination_matrix()

        candidates = [
            self._compile_candidate(
                CandidateStrategy.MAX_DISCRIMINATION,
                discrimination_matrix,
            ),
            self._compile_candidate(
                CandidateStrategy.MAX_ROBUSTNESS,
                discrimination_matrix,
            ),
            self._compile_candidate(
                CandidateStrategy.MAX_COVERAGE,
                discrimination_matrix,
            ),
        ]

        self.ps.candidates = candidates
        return candidates

    # ─── Coverage Map ────────────────────────────────────────────────────

    def _build_coverage_map(self):
        """
        Enumerate ALL possible combinations of available factor levels.
        Mark which are tested, which are excluded, which are discriminative.
        """
        factors = self.ps.factors
        if not factors:
            self.ps.coverage_map = []
            self.ps.total_combinations = 0
            self.ps.tested_combinations = 0
            return

        # Get available levels per factor
        factor_levels: list[list[tuple[str, str]]] = []
        for factor in factors:
            available = self.ps.get_available_levels(factor.id)
            factor_levels.append([(factor.id, lvl.id) for lvl in available])

        # Generate all combinations
        all_combos = []
        for combo_tuple in cartesian_product(*factor_levels):
            combo = {fid: lid for fid, lid in combo_tuple}
            all_combos.append(combo)

        # Build excluded set from constraints
        excluded_set = self._build_excluded_set()

        # Build tested set from completed runs
        tested_set = set()
        tested_map = {}
        for run in self.ps.completed_runs:
            key = self._combo_key(run.combination)
            tested_set.add(key)
            tested_map[key] = run.id

        # Build coverage map
        coverage_map = []
        for combo in all_combos:
            key = self._combo_key(combo)
            is_excluded = key in excluded_set
            is_tested = key in tested_set
            exclusion_reason = excluded_set.get(key)

            cell = CoverageCell(
                combination=combo,
                is_tested=is_tested,
                run_id=tested_map.get(key),
                is_excluded=is_excluded,
                exclusion_reason=exclusion_reason,
            )
            coverage_map.append(cell)

        self.ps.coverage_map = coverage_map
        self.ps.total_combinations = len(all_combos)
        self.ps.tested_combinations = sum(1 for c in coverage_map if c.is_tested)

    def _build_excluded_set(self) -> dict[str, str]:
        """Build a dict of excluded combination keys → reason."""
        excluded = {}
        for constraint in self.ps.constraints:
            if constraint.excluded_factor_id and constraint.excluded_level_id:
                # Exclude specific level of a factor
                for cell in self._combos_with_level(
                    constraint.excluded_factor_id,
                    constraint.excluded_level_id,
                ):
                    key = self._combo_key(cell)
                    excluded[key] = constraint.description
            elif constraint.excluded_factor_id and not constraint.excluded_level_id:
                # Exclude entire factor — all levels
                factor = self.ps.get_factor_by_id(constraint.excluded_factor_id)
                if factor:
                    for level in factor.levels:
                        for cell in self._combos_with_level(
                            constraint.excluded_factor_id, level.id,
                        ):
                            key = self._combo_key(cell)
                            excluded[key] = constraint.description

            # Exclude specific combinations
            for combo in constraint.excluded_combinations:
                key = self._combo_key(combo)
                excluded[key] = constraint.description

        return excluded

    def _combos_with_level(
        self, factor_id: str, level_id: str
    ) -> list[dict[str, str]]:
        """All combinations that include a specific factor-level pair."""
        factors = self.ps.factors
        factor_levels: list[list[tuple[str, str]]] = []
        for factor in factors:
            if factor.id == factor_id:
                factor_levels.append([(factor.id, level_id)])
            else:
                available = self.ps.get_available_levels(factor.id)
                factor_levels.append([(factor.id, lvl.id) for lvl in available])
        combos = []
        for combo_tuple in cartesian_product(*factor_levels):
            combos.append({fid: lid for fid, lid in combo_tuple})
        return combos

    # ─── Discrimination Matrix ───────────────────────────────────────────

    def _compute_discrimination_matrix(self) -> dict[str, DiscriminationPair]:
        """
        For each pair of hypotheses, find which untested combinations
        would discriminate between them.

        A combination discriminates H_a from H_b if:
        1. It includes at least one distinguishing factor, AND
        2. It varies the distinguishing factor(s) relative to at least one
           tested run (same non-distinguishing levels, different distinguishing
           level), OR it covers a distinguishing factor-level not yet seen.
        3. If no completed runs exist, any untested combo with a
           distinguishing factor is informative.
        """
        # Clear stale annotations from previous compilations
        for cell in self.ps.coverage_map:
            cell.is_discriminative_for = []

        hypotheses = self.ps.hypotheses
        if len(hypotheses) < 2:
            return {}

        tested_combos = [run.combination for run in self.ps.completed_runs]
        all_factor_ids = {f.id for f in self.ps.factors}

        pairs: dict[str, DiscriminationPair] = {}

        for i, h_a in enumerate(hypotheses):
            for h_b in hypotheses[i + 1:]:
                pair_key = f"{h_a.id}-vs-{h_b.id}"

                distinguishing = set(h_a.distinguishing_factors) | set(
                    h_b.distinguishing_factors
                )
                if not distinguishing:
                    distinguishing = all_factor_ids

                non_distinguishing = all_factor_ids - distinguishing

                discriminating_combos = []
                for cell in self.ps.coverage_map:
                    if cell.is_tested or cell.is_excluded:
                        continue

                    combo = cell.combination
                    combo_dist_factors = {
                        fid for fid in combo if fid in distinguishing
                    }
                    if not combo_dist_factors:
                        continue

                    if not tested_combos:
                        discriminating_combos.append(combo)
                        cell.is_discriminative_for.append(pair_key)
                        continue

                    is_discriminating = False

                    # Check for a tested run that matches on non-distinguishing
                    # factors but differs on at least one distinguishing factor
                    for tested in tested_combos:
                        non_dist_match = all(
                            combo.get(fid) == tested.get(fid)
                            for fid in non_distinguishing
                            if fid in combo and fid in tested
                        )
                        if not non_dist_match:
                            continue
                        dist_differs = any(
                            combo.get(fid) != tested.get(fid)
                            for fid in distinguishing
                            if fid in combo and fid in tested
                        )
                        if dist_differs:
                            is_discriminating = True
                            break

                    # Also discriminating if it covers a distinguishing
                    # factor-level not yet seen in any tested run
                    if not is_discriminating:
                        for fid in combo_dist_factors:
                            level = combo.get(fid)
                            if level and not any(
                                t.get(fid) == level for t in tested_combos
                            ):
                                is_discriminating = True
                                break

                    if is_discriminating:
                        discriminating_combos.append(combo)
                        cell.is_discriminative_for.append(pair_key)

                total_possible = sum(
                    1 for c in self.ps.coverage_map if not c.is_excluded
                )
                power = (
                    len(discriminating_combos) / total_possible
                    if total_possible > 0
                    else 0.0
                )

                pairs[pair_key] = DiscriminationPair(
                    hypothesis_a_id=h_a.id,
                    hypothesis_b_id=h_b.id,
                    discriminating_combinations=discriminating_combos,
                    discrimination_power=round(power, 3),
                )

        return pairs

    # ─── Candidate Compilation ───────────────────────────────────────────

    def _compile_candidate(
        self,
        strategy: CandidateStrategy,
        discrimination_matrix: dict[str, DiscriminationPair],
    ) -> ExperimentCandidate:
        """Compile one candidate with the given optimization strategy."""

        untested = self.ps.get_untested_combinations()
        budget = self.ps.max_runs_budget or len(untested)

        if strategy == CandidateStrategy.MAX_DISCRIMINATION:
            selected, justification = self._select_max_discrimination(
                untested, discrimination_matrix, budget
            )
            design_family = self._select_design_family(selected)
            design_source = "greedy"

        elif strategy == CandidateStrategy.MAX_COVERAGE:
            selected, justification, design_family, design_source = (
                self._select_max_coverage_classical(
                    untested, discrimination_matrix, budget
                )
            )

        else:  # MAX_ROBUSTNESS
            selected, justification, design_family, design_source = (
                self._select_max_robustness_classical(
                    untested, discrimination_matrix, budget
                )
            )

        # Build discrimination pairs for this candidate
        candidate_pairs = self._discrimination_for_subset(
            selected, discrimination_matrix
        )

        total_score = (
            sum(p.discrimination_power for p in candidate_pairs)
            / len(candidate_pairs)
            if candidate_pairs
            else 0.0
        )

        # Calculate constraint costs
        constraint_costs = self._calculate_constraint_costs(
            discrimination_matrix
        )

        # Quality assessment — ALL candidates, regardless of source
        quality = self._assess_quality(selected)

        design_matrix = DesignMatrix(
            rows=selected,
            num_runs=len(selected),
            design_family=design_family,
            design_source=design_source,
            design_properties=self._compute_design_properties(
                selected, design_family
            ),
            d_efficiency=quality.d_efficiency,
            a_efficiency=quality.a_efficiency,
            gwlp=quality.gwlp,
            design_rank=quality.rank,
        )

        return ExperimentCandidate(
            strategy=strategy,
            design_matrix=design_matrix,
            discrimination_pairs=candidate_pairs,
            total_discrimination_score=round(total_score, 3),
            justification=justification,
            constraint_costs=constraint_costs,
        )

    def _select_max_discrimination(
        self,
        untested: list[dict],
        disc_matrix: dict[str, DiscriminationPair],
        budget: int,
    ) -> tuple[list[dict], str]:
        """
        Greedy selection: pick combinations that discriminate the most
        hypothesis pairs.
        """
        # Score each untested combination by how many pairs it discriminates
        combo_scores: list[tuple[dict, int]] = []
        for combo in untested:
            key = self._combo_key(combo)
            score = 0
            for pair in disc_matrix.values():
                if any(
                    self._combo_key(c) == key
                    for c in pair.discriminating_combinations
                ):
                    score += 1
            combo_scores.append((combo, score))

        # Sort by discrimination score descending
        combo_scores.sort(key=lambda x: x[1], reverse=True)

        selected = [combo for combo, _ in combo_scores[:budget]]
        n_pairs = len(disc_matrix)

        justification = (
            f"Selected {len(selected)} runs (budget: {budget}) "
            f"optimized for maximum discrimination across {n_pairs} "
            f"hypothesis pairs. Greedy selection by pair coverage."
        )
        return selected, justification

    def _select_max_robustness(
        self,
        untested: list[dict],
        disc_matrix: dict[str, DiscriminationPair],
        budget: int,
    ) -> tuple[list[dict], str]:
        """
        Select combinations that provide replication for the weakest
        hypothesis pair (the one with lowest discrimination power).
        This ensures the most uncertain distinction gets more evidence.
        """
        if not disc_matrix:
            return untested[:budget], "No hypothesis pairs to optimize for."

        # Find the pair with LOWEST discrimination power (weakest link)
        weakest_pair = min(disc_matrix.values(), key=lambda p: p.discrimination_power)

        # Prioritize combinations that discriminate this pair
        pair_combos = {
            self._combo_key(c) for c in weakest_pair.discriminating_combinations
        }

        priority = []
        others = []
        for combo in untested:
            if self._combo_key(combo) in pair_combos:
                priority.append(combo)
            else:
                others.append(combo)

        selected = (priority + others)[:budget]

        justification = (
            f"Selected {len(selected)} runs (budget: {budget}) "
            f"prioritizing robustness for weakest pair: "
            f"{weakest_pair.hypothesis_a_id} vs {weakest_pair.hypothesis_b_id} "
            f"(power: {weakest_pair.discrimination_power:.3f}). "
            f"{min(len(priority), budget)} runs target this pair directly."
        )
        return selected, justification

    def _select_max_coverage(
        self,
        untested: list[dict],
        budget: int,
    ) -> tuple[list[dict], str]:
        """
        Select combinations that maximize pairwise coverage of factor-level
        interactions. This is the covering array approach.
        """
        if not untested:
            return [], "No untested combinations available."

        # Greedy covering: pick combos that cover the most new pairs
        factors = self.ps.factors
        all_pairs_to_cover = set()
        for i, f1 in enumerate(factors):
            for f2 in factors[i + 1:]:
                for l1 in self.ps.get_available_levels(f1.id):
                    for l2 in self.ps.get_available_levels(f2.id):
                        pair = (f1.id, l1.id, f2.id, l2.id)
                        all_pairs_to_cover.add(pair)

        # Remove already-covered pairs from completed runs
        for run in self.ps.completed_runs:
            for i, f1 in enumerate(factors):
                for f2 in factors[i + 1:]:
                    if f1.id in run.combination and f2.id in run.combination:
                        pair = (
                            f1.id, run.combination[f1.id],
                            f2.id, run.combination[f2.id],
                        )
                        all_pairs_to_cover.discard(pair)

        uncovered = set(all_pairs_to_cover)
        selected = []
        selected_keys: set[str] = set()

        for _ in range(min(budget, len(untested))):
            if not uncovered:
                break

            # Score each untested combo by how many uncovered pairs it covers
            best_combo = None
            best_count = -1
            for combo in untested:
                if self._combo_key(combo) in selected_keys:
                    continue
                count = 0
                for i, f1 in enumerate(factors):
                    for f2 in factors[i + 1:]:
                        if f1.id in combo and f2.id in combo:
                            pair = (f1.id, combo[f1.id], f2.id, combo[f2.id])
                            if pair in uncovered:
                                count += 1
                if count > best_count:
                    best_count = count
                    best_combo = combo

            if best_combo is None or best_count == 0:
                break

            selected.append(best_combo)
            selected_keys.add(self._combo_key(best_combo))

            # Remove covered pairs
            for i, f1 in enumerate(factors):
                for f2 in factors[i + 1:]:
                    if f1.id in best_combo and f2.id in best_combo:
                        pair = (
                            f1.id, best_combo[f1.id],
                            f2.id, best_combo[f2.id],
                        )
                        uncovered.discard(pair)

        total_pairs = len(all_pairs_to_cover)
        covered = total_pairs - len(uncovered)
        coverage_pct = (covered / total_pairs * 100) if total_pairs > 0 else 0

        justification = (
            f"Selected {len(selected)} runs (budget: {budget}) "
            f"optimized for pairwise coverage. "
            f"Covers {covered}/{total_pairs} factor-level pairs "
            f"({coverage_pct:.1f}% pairwise coverage)."
        )
        return selected, justification

    # ─── Classical Design Pipelines ──────────────────────────────────────

    def _select_max_coverage_classical(
        self,
        untested: list[dict],
        disc_matrix: dict[str, DiscriminationPair],
        budget: int,
    ) -> tuple[list[dict], str, DesignFamily, str]:
        """
        Try classical designs for MAX_COVERAGE, falling back to greedy.
        Returns: (selected_rows, justification, design_family, design_source)
        """
        try:
            from app.doe_planner.design_generators import (
                generate_best_design, COVERAGE_CHAIN,
                filter_by_constraints, repair_coverage,
                compute_pairwise_coverage,
            )

            design = generate_best_design(self.ps, budget, COVERAGE_CHAIN)
            if design is not None:
                filtered = filter_by_constraints(design.rows, self.ps)

                if filtered.removed_count == 0:
                    rows = filtered.surviving_rows[:budget]
                    source = design.source
                elif filtered.is_structurally_intact:
                    rows = filtered.surviving_rows[:budget]
                    source = design.source
                else:
                    budget_remaining = budget - len(filtered.surviving_rows)
                    rows = repair_coverage(
                        filtered.surviving_rows, untested,
                        max(0, budget_remaining), self.ps,
                    )
                    source = f"{design.source}+repair"

                coverage = compute_pairwise_coverage(rows, self.ps)

                justification = (
                    f"Classical design ({source}): {len(rows)} runs "
                    f"(budget: {budget}). "
                    f"Family: {design.family.value}. "
                    f"Pairwise coverage: {coverage*100:.1f}%. "
                    + (f"Constraint filtering removed "
                       f"{filtered.removed_count} rows. "
                       if filtered.removed_count > 0 else "")
                    + (f"D-efficiency: "
                       f"{design.properties.get('d_efficiency', 'N/A')}. "
                       if 'd_efficiency' in design.properties else "")
                )
                return rows, justification, design.family, source

        except Exception as e:
            logger.info(
                "Classical coverage generation failed: %s. Using greedy.", e
            )

        selected, justification = self._select_max_coverage(untested, budget)
        return selected, justification, self._select_design_family(selected), "greedy"

    def _select_max_robustness_classical(
        self,
        untested: list[dict],
        disc_matrix: dict[str, DiscriminationPair],
        budget: int,
    ) -> tuple[list[dict], str, DesignFamily, str]:
        """
        Try classical D-optimal design for robustness backbone,
        then add replication of weakest pair. Falls back to greedy.
        """
        try:
            from app.doe_planner.design_generators import (
                generate_best_design, ROBUSTNESS_CHAIN,
                filter_by_constraints, ROBUSTNESS_BACKBONE_FRACTION,
            )

            backbone_budget = max(1, int(budget * ROBUSTNESS_BACKBONE_FRACTION))
            replication_budget = budget - backbone_budget

            design = generate_best_design(
                self.ps, backbone_budget, ROBUSTNESS_CHAIN,
            )

            if design is not None:
                filtered = filter_by_constraints(design.rows, self.ps)
                backbone_rows = filtered.surviving_rows[:backbone_budget]
                family = design.family
                source = design.source
            else:
                backbone_rows, _ = self._select_max_coverage(
                    untested, backbone_budget,
                )
                family = self._select_design_family(backbone_rows)
                source = "greedy"

            replication_rows: list[dict] = []
            if disc_matrix and replication_budget > 0:
                weakest = min(
                    disc_matrix.values(),
                    key=lambda p: p.discrimination_power,
                )
                pair_keys = {
                    self._combo_key(c)
                    for c in weakest.discriminating_combinations
                }
                backbone_keys = {
                    self._combo_key(r) for r in backbone_rows
                }
                for combo in untested:
                    if len(replication_rows) >= replication_budget:
                        break
                    key = self._combo_key(combo)
                    if key in pair_keys and key not in backbone_keys:
                        replication_rows.append(combo)

            selected = backbone_rows + replication_rows
            full_source = (
                f"{source}+replication" if replication_rows else source
            )

            weakest_info = ""
            if disc_matrix:
                weakest = min(
                    disc_matrix.values(),
                    key=lambda p: p.discrimination_power,
                )
                weakest_info = (
                    f" Weakest pair: {weakest.hypothesis_a_id} vs "
                    f"{weakest.hypothesis_b_id} "
                    f"(power: {weakest.discrimination_power:.3f}). "
                    f"{len(replication_rows)} replication runs added."
                )

            justification = (
                f"Hybrid robustness ({full_source}): "
                f"{len(backbone_rows)} backbone + "
                f"{len(replication_rows)} replication = "
                f"{len(selected)} runs (budget: {budget}). "
                f"Family: {family.value}.{weakest_info}"
            )

            return selected, justification, family, full_source

        except Exception as e:
            logger.info(
                "Classical robustness generation failed: %s. Using greedy.", e
            )

        selected, justification = self._select_max_robustness(
            untested, disc_matrix, budget,
        )
        return (
            selected, justification,
            self._select_design_family(selected), "greedy",
        )

    def _assess_quality(self, selected: list[dict]) -> "DesignQuality":
        """Compute OAPackage quality metrics. Graceful fallback."""
        try:
            from app.doe_planner.design_generators import (
                DesignQualityAssessor, DesignQuality,
            )
            return DesignQualityAssessor.assess(selected, self.ps)
        except Exception:
            from app.doe_planner.design_generators import DesignQuality
            return DesignQuality(source_library="none")

    def _count_total_pairs(self) -> int:
        """Count total 2-way factor-level tuples."""
        factors = self.ps.factors
        total = 0
        for i, f1 in enumerate(factors):
            for f2 in factors[i + 1:]:
                total += (
                    len(self.ps.get_available_levels(f1.id))
                    * len(self.ps.get_available_levels(f2.id))
                )
        return total

    # ─── Design Family Selection ─────────────────────────────────────────

    def _select_design_family(self, selected: list[dict]) -> DesignFamily:
        """
        Determine which design family best describes the selected runs.
        """
        factors = self.ps.factors
        n_factors = len(factors)
        n_runs = len(selected)

        if n_factors == 0 or n_runs == 0:
            return DesignFamily.CUSTOM

        levels_per_factor = [
            len(self.ps.get_available_levels(f.id)) for f in factors
        ]
        total_full = 1
        for lv in levels_per_factor:
            total_full *= lv

        # Full factorial if we're running all combinations
        if n_runs >= total_full:
            return DesignFamily.FULL_FACTORIAL

        # Latin square: exactly 2 blocking factors + 1 treatment,
        # all with same number of levels = n, and n runs
        blocking = [f for f in factors if f.is_blocking_factor]
        if (
            len(blocking) == 2
            and n_factors == 3
            and len(set(levels_per_factor)) == 1
            and levels_per_factor[0] == n_runs
        ):
            return DesignFamily.LATIN_SQUARE

        # Check if any constraints exist → covering array
        has_constraints = any(
            c for c in self.ps.constraints
            if c.excluded_combinations or c.excluded_level_id
        )
        if has_constraints:
            return DesignFamily.COVERING_ARRAY

        # Fractional factorial if uniform levels and runs < full
        if len(set(levels_per_factor)) == 1 and n_runs < total_full:
            return DesignFamily.FRACTIONAL_FACTORIAL

        # Orthogonal array for uniform levels with specific ratios
        if len(set(levels_per_factor)) == 1:
            v = levels_per_factor[0]
            if n_runs % (v * v) == 0:
                return DesignFamily.ORTHOGONAL_ARRAY

        return DesignFamily.COVERING_ARRAY

    # ─── Constraint Cost Analysis ────────────────────────────────────────

    def _calculate_constraint_costs(
        self,
        disc_matrix: dict[str, DiscriminationPair],
    ) -> list[ConstraintCost]:
        """
        For each constraint, calculate what discrimination is lost.
        This answers: "what do I lose if I can't use lot C?"
        """
        costs = []
        for constraint in self.ps.constraints:
            affected_pairs = []
            for pair_key, pair in disc_matrix.items():
                excluded_count = 0
                for combo in pair.discriminating_combinations:
                    if self._is_excluded_by_constraint(combo, constraint):
                        excluded_count += 1
                if excluded_count > 0:
                    total = len(pair.discriminating_combinations)
                    affected_pairs.append(AffectedPair(
                        pair=pair_key,
                        excluded_runs=excluded_count,
                        total_discriminating=total,
                        lost_fraction=round(
                            excluded_count / total if total > 0 else 0, 3
                        ),
                    ))

            if affected_pairs:
                costs.append(ConstraintCost(
                    constraint_id=constraint.id,
                    constraint_description=constraint.description,
                    affected_hypothesis_pairs=affected_pairs,
                ))

        return costs

    def _is_excluded_by_constraint(
        self, combo: dict, constraint: Constraint
    ) -> bool:
        """Check if a combination is excluded by a specific constraint."""
        if constraint.excluded_factor_id and constraint.excluded_level_id:
            fid = constraint.excluded_factor_id
            lid = constraint.excluded_level_id
            if combo.get(fid) == lid:
                return True
        for excl_combo in constraint.excluded_combinations:
            if all(combo.get(k) == v for k, v in excl_combo.items()):
                return True
        return False

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _discrimination_for_subset(
        self,
        subset: list[dict],
        disc_matrix: dict[str, DiscriminationPair],
    ) -> list[DiscriminationPair]:
        """Compute discrimination pairs covered by a subset of combinations."""
        subset_keys = {self._combo_key(c) for c in subset}
        result = []
        for pair_key, pair in disc_matrix.items():
            covered = [
                c
                for c in pair.discriminating_combinations
                if self._combo_key(c) in subset_keys
            ]
            if covered:
                total = len(pair.discriminating_combinations)
                power = len(covered) / total if total > 0 else 0.0
                result.append(
                    DiscriminationPair(
                        hypothesis_a_id=pair.hypothesis_a_id,
                        hypothesis_b_id=pair.hypothesis_b_id,
                        discriminating_combinations=covered,
                        discrimination_power=round(power, 3),
                    )
                )
        return result

    def _compute_design_properties(
        self, selected: list[dict], family: DesignFamily
    ) -> dict:
        """Compute verifiable properties of the design."""
        props = {
            "num_factors": len(self.ps.factors),
            "num_runs": len(selected),
        }

        if family == DesignFamily.FULL_FACTORIAL:
            props["type"] = "complete"

        if family == DesignFamily.COVERING_ARRAY:
            # Compute actual pairwise coverage
            factors = self.ps.factors
            total_pairs = 0
            covered_pairs = 0
            for i, f1 in enumerate(factors):
                for f2 in factors[i + 1:]:
                    for l1 in self.ps.get_available_levels(f1.id):
                        for l2 in self.ps.get_available_levels(f2.id):
                            total_pairs += 1
                            pair = (f1.id, l1.id, f2.id, l2.id)
                            for combo in selected:
                                if (
                                    combo.get(f1.id) == l1.id
                                    and combo.get(f2.id) == l2.id
                                ):
                                    covered_pairs += 1
                                    break
            props["strength"] = 2
            props["total_pairs"] = total_pairs
            props["covered_pairs"] = covered_pairs
            props["coverage_fraction"] = (
                round(covered_pairs / total_pairs, 3)
                if total_pairs > 0
                else 0
            )

        if family == DesignFamily.LATIN_SQUARE:
            levels = [
                len(self.ps.get_available_levels(f.id))
                for f in self.ps.factors
            ]
            props["order"] = levels[0] if levels else 0
            props["is_valid_latin_square"] = self._verify_latin_square(selected)

        return props

    def _verify_latin_square(self, selected: list[dict]) -> bool:
        """Verify that a design is a valid Latin square."""
        if not selected or len(self.ps.factors) != 3:
            return False
        factors = self.ps.factors
        n = len(selected)
        # Check each symbol appears once per row and once per column
        row_factor, col_factor, sym_factor = (
            factors[0].id,
            factors[1].id,
            factors[2].id,
        )
        rows_seen: dict[str, set] = defaultdict(set)
        cols_seen: dict[str, set] = defaultdict(set)
        for combo in selected:
            r, c, s = combo[row_factor], combo[col_factor], combo[sym_factor]
            if s in rows_seen[r] or s in cols_seen[c]:
                return False
            rows_seen[r].add(s)
            cols_seen[c].add(s)
        return True

    @staticmethod
    def _combo_key(combo: dict[str, str]) -> str:
        """Deterministic string key for a combination."""
        return "|".join(f"{k}={v}" for k, v in sorted(combo.items()))
