"""
Tessellarium — Lean 4 Verifier

Orchestrates: generate .lean → write to temp project → lake build → parse result.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from app.models import VerificationRequest, VerificationResponse, VerificationStatus
from app.lean_generator import (
    generate_covering_array_proof,
    generate_latin_square_proof,
    generate_bibd_proof,
)

logger = logging.getLogger(__name__)

LAKEFILE_CONTENT = """import Lake
open Lake DSL

package tessVerify where
  leanOptions := #[
    ⟨`autoImplicit, false⟩
  ]

@[default_target]
lean_lib TessVerify where
  srcDir := "."
"""

LEAN_TOOLCHAIN = "leanprover/lean4:stable"


async def verify(request: VerificationRequest) -> VerificationResponse:
    """
    Main verification entry point.
    Generates Lean code, compiles it, returns the result.
    """
    start_ms = _now_ms()

    # Generate the Lean proof code
    lean_code = _generate_lean_code(request)
    if lean_code.startswith("--"):
        return VerificationResponse(
            status=VerificationStatus.NOT_ATTEMPTED,
            property_verified=request.property_to_verify,
            proof_time_ms=_now_ms() - start_ms,
            details=lean_code.lstrip("- "),
        )

    # Write to temp project and compile
    try:
        result = await _compile_lean(
            lean_code,
            timeout=request.timeout_seconds,
        )
        result.proof_time_ms = _now_ms() - start_ms
        result.property_verified = request.property_to_verify
        return result
    except asyncio.TimeoutError:
        return VerificationResponse(
            status=VerificationStatus.TIMEOUT,
            property_verified=request.property_to_verify,
            proof_time_ms=_now_ms() - start_ms,
            details=f"Lean compilation timed out after {request.timeout_seconds}s",
        )
    except Exception as e:
        logger.warning("Verification error: %s", e)
        return VerificationResponse(
            status=VerificationStatus.NOT_ATTEMPTED,
            property_verified=request.property_to_verify,
            proof_time_ms=_now_ms() - start_ms,
            details=f"Verification error: {e}",
        )


def _generate_lean_code(request: VerificationRequest) -> str:
    """Dispatch to the appropriate generator."""
    family = request.design_family.lower().replace("-", "_").replace(" ", "_")

    if family in ("covering_array", "fractional_factorial", "orthogonal_array"):
        return generate_covering_array_proof(
            request.design_matrix, strength=request.strength,
        )
    elif family == "latin_square":
        return generate_latin_square_proof(request.design_matrix)
    elif family == "bibd":
        return generate_bibd_proof(
            request.design_matrix, lambda_val=request.lambda_val,
        )
    else:
        return f"-- Unsupported design family: {request.design_family}"


async def _compile_lean(lean_code: str, timeout: int) -> VerificationResponse:
    """
    Write Lean code to a temp project and compile with lake build.
    """
    tmpdir = tempfile.mkdtemp(prefix="tess_verify_")

    try:
        project_dir = Path(tmpdir)

        # Write lakefile.lean
        (project_dir / "lakefile.lean").write_text(LAKEFILE_CONTENT)

        # Write lean-toolchain
        (project_dir / "lean-toolchain").write_text(LEAN_TOOLCHAIN + "\n")

        # Write the verification file
        (project_dir / "TessVerify.lean").write_text(lean_code)

        # Run lake build with timeout
        proc = await asyncio.create_subprocess_exec(
            "lake", "build",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "LAKE_HOME": str(project_dir / ".lake")},
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return VerificationResponse(
                status=VerificationStatus.TIMEOUT,
                property_verified="",
                details=f"Lean compilation timed out after {timeout}s",
            )

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        combined = stdout_text + stderr_text

        if proc.returncode == 0:
            return VerificationResponse(
                status=VerificationStatus.VERIFIED,
                property_verified="",
                details="Lean compilation succeeded — all proofs checked.",
            )
        else:
            # Parse error for counterexample hints
            counterexample = _extract_counterexample(combined)
            return VerificationResponse(
                status=VerificationStatus.FAILED,
                property_verified="",
                details=_truncate(combined, 1000),
                counterexample=counterexample,
            )

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _extract_counterexample(error_output: str) -> dict | None:
    """Try to extract a counterexample hint from Lean error output."""
    lines = error_output.strip().split("\n")
    errors = [
        line for line in lines
        if "error" in line.lower() or "failed" in line.lower()
    ]
    if errors:
        return {"error_lines": errors[:5]}
    return None


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def _now_ms() -> int:
    return int(time.time() * 1000)
