"""
Tessellarium — Design Generators

Generate → Filter → Score → Repair → Assess pipeline for classical DOE.

Generators produce designs from known families (OAPackage, PyDOE2, algebraic).
The quality assessor computes metrics (D-efficiency, GWLP) on ANY design,
including greedy ones. This lets the researcher compare candidates on equal footing.

All external library calls are in try/except — the system works if
OAPackage and/or PyDOE2 are not installed.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.models.problem_space import ProblemSpace, DesignFamily
from app.doe_planner.utils import combo_key

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

OA_ENUM_MAX_ARRAYS_PER_STEP = 100
OA_ENUM_MAX_FACTORS = 6
OA_ENUM_MAX_RUNS = 48
OA_DOPT_MAX_RESTARTS = 20
ROBUSTNESS_BACKBONE_FRACTION = 0.7


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class GeneratedDesign:
    """A design produced by a generator."""
    rows: list[dict[str, str]]
    family: DesignFamily
    source: str
    properties: dict = field(default_factory=dict)

    @property
    def num_runs(self) -> int:
        return len(self.rows)


@dataclass
class DesignQuality:
    """Statistical quality metrics for any design."""
    d_efficiency: Optional[float] = None
    a_efficiency: Optional[float] = None
    gwlp: Optional[list[float]] = None
    rank: Optional[int] = None
    source_library: str = "none"


@dataclass
class FilterResult:
    """Result of applying constraints to a generated design."""
    surviving_rows: list[dict[str, str]]
    removed_count: int
    original_count: int
    pairwise_coverage_before: float
    pairwise_coverage_after: float

    @property
    def damage_fraction(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.removed_count / self.original_count

    @property
    def is_structurally_intact(self) -> bool:
        """Design retains >=90% of original pairwise coverage."""
        if self.pairwise_coverage_before == 0:
            return True
        return self.pairwise_coverage_after >= 0.9 * self.pairwise_coverage_before


# ─── Abstract Generator ──────────────────────────────────────────────────────

class DesignGenerator(ABC):
    """
    Base class for experimental design generators.
    Each generator wraps one library/algorithm.
    Returning None means "I can't produce a design for this problem."
    """

    @abstractmethod
    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        """Generate a design within the budget. Returns None on failure."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""
        ...

    def _get_available_level_counts(self, ps: ProblemSpace) -> list[int]:
        """Get number of available levels per factor."""
        return [len(ps.get_available_levels(f.id)) for f in ps.factors]

    def _map_indices_to_ids(
        self, matrix, ps: ProblemSpace,
    ) -> list[dict[str, str]]:
        """
        Map a numeric matrix (numpy array or list of lists) to
        factor_id -> level_id dicts using available levels.
        """
        try:
            import numpy as np
            if isinstance(matrix, np.ndarray):
                matrix = matrix.tolist()
        except ImportError:
            pass

        factors = ps.factors
        rows = []
        for row in matrix:
            combo = {}
            for col_idx, factor in enumerate(factors):
                available = ps.get_available_levels(factor.id)
                level_idx = int(row[col_idx])
                if 0 <= level_idx < len(available):
                    combo[factor.id] = available[level_idx].id
                else:
                    combo[factor.id] = available[min(level_idx, len(available) - 1)].id
            rows.append(combo)
        return rows


# ─── OAPackage: Orthogonal Array Enumeration ─────────────────────────────────

class OAEnumerationGenerator(DesignGenerator):
    """
    Generate strength-2 orthogonal arrays using OAPackage's extend_arraylist.
    Produces designs with genuine strength-2 coverage.
    Practical limits: <=6 factors, <=48 runs.
    """

    @property
    def name(self) -> str:
        return "OAPackage OA Enumeration"

    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        try:
            import oapackage
            import numpy as np
        except ImportError:
            return None

        level_counts = self._get_available_level_counts(ps)
        n_factors = len(level_counts)

        if n_factors > OA_ENUM_MAX_FACTORS or budget > OA_ENUM_MAX_RUNS:
            return None
        if any(l < 2 for l in level_counts) or n_factors < 2:
            return None

        from math import gcd
        from functools import reduce

        def lcm(a: int, b: int) -> int:
            return a * b // gcd(a, b)

        base_lcm = reduce(lcm, level_counts)
        candidate_run_sizes = [
            base_lcm * m for m in range(1, budget // base_lcm + 1)
            if base_lcm * m <= budget
        ]
        if not candidate_run_sizes:
            return None

        best_design = None
        best_d_eff = -1.0

        for run_size in reversed(candidate_run_sizes):
            try:
                arrayclass = oapackage.arraydata_t(
                    level_counts, run_size, 2, n_factors,
                )
                arrays = [arrayclass.create_root()]
                options = oapackage.OAextend()
                options.setAlgorithmAuto(arrayclass)

                for _ in range(n_factors - 2):
                    extensions = oapackage.extend_arraylist(arrays, arrayclass, options)
                    if not extensions:
                        break
                    if len(extensions) > OA_ENUM_MAX_ARRAYS_PER_STEP:
                        d_effs = np.array([a.Defficiency() for a in extensions])
                        top_idx = np.argsort(d_effs)[::-1][:OA_ENUM_MAX_ARRAYS_PER_STEP]
                        extensions = [extensions[i] for i in top_idx]
                    arrays = extensions

                if not arrays or arrays[0].n_columns < n_factors:
                    continue

                d_effs = [a.Defficiency() for a in arrays]
                best_idx = int(np.argmax(d_effs))
                best_array = arrays[best_idx]
                d_eff = d_effs[best_idx]

                if d_eff > best_d_eff:
                    np_array = np.array(best_array)
                    rows = self._map_indices_to_ids(np_array, ps)
                    gwlp = list(best_array.GWLP())

                    best_design = GeneratedDesign(
                        rows=rows,
                        family=DesignFamily.ORTHOGONAL_ARRAY,
                        source="oa_enumerate",
                        properties={
                            "strength": 2,
                            "run_size": run_size,
                            "d_efficiency": round(d_eff, 6),
                            "gwlp": [round(g, 6) for g in gwlp],
                            "rank": best_array.rank(),
                            "arrays_enumerated": len(arrays),
                        },
                    )
                    best_d_eff = d_eff

            except Exception as e:
                logger.debug("OA enumeration failed for N=%d: %s", run_size, e)
                continue

        return best_design


# ─── OAPackage: D-Optimal Design ─────────────────────────────────────────────

class DoptimizeGenerator(DesignGenerator):
    """
    Generate D-optimal designs using OAPackage's coordinate-exchange algorithm.
    Optimizes T = alpha1*D_eff + alpha2*Ds_eff + alpha3*D1_eff.
    """

    def __init__(self, alpha: Optional[list[float]] = None):
        self.alpha = alpha or [1, 2, 0]

    @property
    def name(self) -> str:
        return f"OAPackage Doptimize (alpha={self.alpha})"

    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        try:
            import oapackage
            import numpy as np
        except ImportError:
            return None

        level_counts = self._get_available_level_counts(ps)
        n_factors = len(level_counts)

        if n_factors < 1 or budget < n_factors + 1:
            return None

        try:
            arrayclass = oapackage.arraydata_t(
                level_counts, budget, 0, n_factors,
            )
            nrestarts = min(OA_DOPT_MAX_RESTARTS, max(5, budget))

            scores, dds, designs, ngenerated = oapackage.Doptimize(
                arrayclass,
                nrestarts=nrestarts,
                optimfunc=self.alpha,
                selectpareto=True,
                verbose=0,
            )

            if not designs:
                return None

            best_idx = int(np.argmax(scores))
            best_array = designs[best_idx]

            np_array = np.array(best_array)
            rows = self._map_indices_to_ids(np_array, ps)

            d_eff = best_array.Defficiency()
            gwlp = list(best_array.GWLP())

            return GeneratedDesign(
                rows=rows,
                family=DesignFamily.ORTHOGONAL_ARRAY
                    if any(g == 0.0 for g in gwlp[1:3])
                    else DesignFamily.FRACTIONAL_FACTORIAL,
                source="oa_doptimize",
                properties={
                    "alpha": self.alpha,
                    "d_efficiency": round(d_eff, 6),
                    "gwlp": [round(g, 6) for g in gwlp],
                    "rank": best_array.rank(),
                    "nrestarts": nrestarts,
                    "designs_generated": len(designs),
                },
            )

        except Exception as e:
            logger.warning("Doptimize failed: %s", e)
            return None


# ─── PyDOE2: Generalized Subset Design ───────────────────────────────────────

class PyDOEGSDGenerator(DesignGenerator):
    """PyDOE2 Generalized Subset Design for mixed-level fractional factorials."""

    @property
    def name(self) -> str:
        return "PyDOE2 GSD"

    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        try:
            import pyDOE2
        except ImportError:
            return None

        level_counts = self._get_available_level_counts(ps)
        total = 1
        for lv in level_counts:
            total *= lv

        if total <= budget:
            return None  # Full factorial fits

        for reduction in range(2, total + 1):
            try:
                design = pyDOE2.gsd(level_counts, reduction=reduction)
                if len(design) <= budget:
                    rows = self._map_indices_to_ids(design, ps)
                    return GeneratedDesign(
                        rows=rows,
                        family=DesignFamily.FRACTIONAL_FACTORIAL,
                        source="pydoe2_gsd",
                        properties={"reduction": reduction},
                    )
            except Exception:
                continue

        return None


# ─── PyDOE2: Full Factorial ───────────────────────────────────────────────────

class PyDOEFullFactGenerator(DesignGenerator):
    """PyDOE2 Full Factorial — used when budget covers all combinations."""

    @property
    def name(self) -> str:
        return "PyDOE2 Full Factorial"

    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        try:
            import pyDOE2
        except ImportError:
            return None

        level_counts = self._get_available_level_counts(ps)
        total = 1
        for lv in level_counts:
            total *= lv

        if total > budget:
            return None

        try:
            design = pyDOE2.fullfact(level_counts)
            rows = self._map_indices_to_ids(design, ps)
            return GeneratedDesign(
                rows=rows,
                family=DesignFamily.FULL_FACTORIAL,
                source="pydoe2_fullfact",
                properties={"type": "complete"},
            )
        except Exception as e:
            logger.warning("Full factorial failed: %s", e)
            return None


# ─── PyDOE2: Fractional Factorial (2-level only) ─────────────────────────────

class PyDOEFracFactGenerator(DesignGenerator):
    """PyDOE2 Fractional Factorial — only when ALL factors have exactly 2 levels."""

    @property
    def name(self) -> str:
        return "PyDOE2 Fractional Factorial"

    def generate(self, ps: ProblemSpace, budget: int) -> Optional[GeneratedDesign]:
        try:
            import pyDOE2
        except ImportError:
            return None

        level_counts = self._get_available_level_counts(ps)
        if not all(lv == 2 for lv in level_counts):
            return None

        n_factors = len(level_counts)
        if n_factors < 3:
            return None

        for p in range(1, n_factors):
            n_runs = 2 ** (n_factors - p)
            if n_runs > budget:
                continue

            gen = self._build_generators(n_factors, p)
            if gen is None:
                continue

            try:
                design = pyDOE2.fracfact(gen)
                design = ((design + 1) / 2).astype(int)
                rows = self._map_indices_to_ids(design, ps)
                return GeneratedDesign(
                    rows=rows,
                    family=DesignFamily.FRACTIONAL_FACTORIAL,
                    source="pydoe2_fracfact",
                    properties={"generators": gen, "runs": n_runs},
                )
            except Exception:
                continue

        return None

    @staticmethod
    def _build_generators(n_factors: int, p: int) -> Optional[str]:
        """Build generator string for 2^(k-p) design."""
        if n_factors > 26:
            return None
        independent = n_factors - p
        letters = [chr(ord('a') + i) for i in range(independent)]

        from itertools import combinations
        generated = []
        for combo_len in range(independent, 1, -1):
            for combo in combinations(letters, combo_len):
                if len(generated) >= p:
                    break
                generated.append(''.join(combo))
            if len(generated) >= p:
                break

        if len(generated) < p:
            return None

        return ' '.join(letters + generated[:p])


# ─── Constraint Filtering ────────────────────────────────────────────────────

def compute_pairwise_coverage(
    rows: list[dict[str, str]], ps: ProblemSpace,
) -> float:
    """Fraction of 2-way factor-level tuples covered by the rows."""
    factors = ps.factors
    total_pairs = 0
    covered_pairs = 0

    for i, f1 in enumerate(factors):
        for f2 in factors[i + 1:]:
            avail1 = ps.get_available_levels(f1.id)
            avail2 = ps.get_available_levels(f2.id)
            for l1 in avail1:
                for l2 in avail2:
                    total_pairs += 1
                    if any(
                        r.get(f1.id) == l1.id and r.get(f2.id) == l2.id
                        for r in rows
                    ):
                        covered_pairs += 1

    return covered_pairs / total_pairs if total_pairs > 0 else 0.0


def filter_by_constraints(
    rows: list[dict[str, str]], ps: ProblemSpace,
) -> FilterResult:
    """Remove rows containing excluded factor-levels."""
    excluded: dict[str, str] = {}
    for constraint in ps.constraints:
        if constraint.excluded_factor_id and constraint.excluded_level_id:
            fid = constraint.excluded_factor_id
            lid = constraint.excluded_level_id
            for row in rows:
                if row.get(fid) == lid:
                    excluded[combo_key(row)] = constraint.description
        elif constraint.excluded_factor_id and not constraint.excluded_level_id:
            factor = ps.get_factor_by_id(constraint.excluded_factor_id)
            if factor:
                for level in factor.levels:
                    for row in rows:
                        if row.get(constraint.excluded_factor_id) == level.id:
                            excluded[combo_key(row)] = constraint.description
        for combo in constraint.excluded_combinations:
            excluded[combo_key(combo)] = constraint.description

    surviving = [r for r in rows if combo_key(r) not in excluded]
    cov_before = compute_pairwise_coverage(rows, ps)
    cov_after = compute_pairwise_coverage(surviving, ps)

    return FilterResult(
        surviving_rows=surviving,
        removed_count=len(rows) - len(surviving),
        original_count=len(rows),
        pairwise_coverage_before=cov_before,
        pairwise_coverage_after=cov_after,
    )


def repair_coverage(
    current_rows: list[dict[str, str]],
    untested_pool: list[dict[str, str]],
    budget_remaining: int,
    ps: ProblemSpace,
) -> list[dict[str, str]]:
    """Greedily add rows from untested_pool to restore pairwise coverage."""
    factors = ps.factors
    covered = set()
    for row in current_rows:
        for i, f1 in enumerate(factors):
            for f2 in factors[i + 1:]:
                if f1.id in row and f2.id in row:
                    covered.add((f1.id, row[f1.id], f2.id, row[f2.id]))

    all_pairs = set()
    for i, f1 in enumerate(factors):
        for f2 in factors[i + 1:]:
            for l1 in ps.get_available_levels(f1.id):
                for l2 in ps.get_available_levels(f2.id):
                    all_pairs.add((f1.id, l1.id, f2.id, l2.id))

    uncovered = all_pairs - covered
    if not uncovered:
        return current_rows

    selected_keys = {combo_key(r) for r in current_rows}
    result = list(current_rows)

    for _ in range(budget_remaining):
        if not uncovered:
            break
        best_combo = None
        best_count = 0
        for combo in untested_pool:
            key = combo_key(combo)
            if key in selected_keys:
                continue
            count = sum(
                1 for i, f1 in enumerate(factors)
                for f2 in factors[i + 1:]
                if f1.id in combo and f2.id in combo
                and (f1.id, combo[f1.id], f2.id, combo[f2.id]) in uncovered
            )
            if count > best_count:
                best_count = count
                best_combo = combo
        if best_combo is None or best_count == 0:
            break
        result.append(best_combo)
        selected_keys.add(combo_key(best_combo))
        for i, f1 in enumerate(factors):
            for f2 in factors[i + 1:]:
                if f1.id in best_combo and f2.id in best_combo:
                    uncovered.discard(
                        (f1.id, best_combo[f1.id], f2.id, best_combo[f2.id])
                    )

    return result


# ─── Quality Assessor ─────────────────────────────────────────────────────────

class DesignQualityAssessor:
    """
    Computes OAPackage quality metrics for ANY design matrix.
    The unifying component: greedy, PyDOE2, and OAPackage designs
    all get the same assessment on equal footing.
    """

    @staticmethod
    def assess(
        rows: list[dict[str, str]], ps: ProblemSpace,
    ) -> DesignQuality:
        """Convert design to OAPackage array_link and compute metrics."""
        try:
            import oapackage
            import numpy as np
        except ImportError:
            return DesignQuality(source_library="none")

        if not rows or not ps.factors:
            return DesignQuality(source_library="none")

        try:
            factors = ps.factors
            n_runs = len(rows)
            n_factors = len(factors)
            matrix = np.zeros((n_runs, n_factors), dtype=int)

            for row_idx, row in enumerate(rows):
                for col_idx, factor in enumerate(factors):
                    available = ps.get_available_levels(factor.id)
                    level_id = row.get(factor.id)
                    for lvl_idx, lvl in enumerate(available):
                        if lvl.id == level_id:
                            matrix[row_idx, col_idx] = lvl_idx
                            break

            al = oapackage.array_link(matrix.astype(np.int32))

            d_eff = al.Defficiency()
            gwlp = list(al.GWLP())
            rank_val = al.rank()

            try:
                a_eff = al.Aefficiency()
            except Exception:
                a_eff = None

            return DesignQuality(
                d_efficiency=round(d_eff, 6),
                a_efficiency=round(a_eff, 6) if a_eff is not None else None,
                gwlp=[round(g, 6) for g in gwlp],
                rank=rank_val,
                source_library="oapackage",
            )

        except Exception as e:
            logger.warning("Quality assessment failed: %s", e)
            return DesignQuality(source_library="none")


# ─── Generator Chains ─────────────────────────────────────────────────────────

COVERAGE_CHAIN: list[DesignGenerator] = [
    OAEnumerationGenerator(),
    DoptimizeGenerator(alpha=[1, 0, 0]),
    PyDOEGSDGenerator(),
    PyDOEFullFactGenerator(),
]

ROBUSTNESS_CHAIN: list[DesignGenerator] = [
    DoptimizeGenerator(alpha=[1, 2, 0]),
    OAEnumerationGenerator(),
    PyDOEGSDGenerator(),
    PyDOEFullFactGenerator(),
]


def generate_best_design(
    ps: ProblemSpace,
    budget: int,
    chain: list[DesignGenerator],
) -> Optional[GeneratedDesign]:
    """Try each generator in the chain until one succeeds."""
    for generator in chain:
        logger.debug("Trying generator: %s", generator.name)
        try:
            result = generator.generate(ps, budget)
            if result is not None and result.num_runs > 0:
                logger.info(
                    "Generator '%s' produced %d-run %s design.",
                    generator.name, result.num_runs, result.source,
                )
                return result
        except Exception as e:
            logger.warning("Generator '%s' failed: %s", generator.name, e)
            continue
    return None
