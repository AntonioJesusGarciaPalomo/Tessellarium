"""
Tessellarium — Content Understanding Service Test

Tests _parse_result with sample Content Understanding API responses.
All tests work offline — no API calls.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.content_understanding import ContentUnderstandingService


def _make_service() -> ContentUnderstandingService:
    """Create a service instance (no real endpoint needed for parse tests)."""
    return ContentUnderstandingService(
        endpoint="https://fake.cognitiveservices.azure.com",
        api_key="fake-key",
    )


def test_parse_fields_response():
    """CU response with structured fields → markdown text."""
    print("Test: Parse structured fields response")

    service = _make_service()
    raw = {
        "fields": {
            "objective": {
                "content": "Determine the optimal temperature and reagent combination for maximum yield",
            },
            "factors": {
                "valueArray": [
                    {"content": "Temperature (20°C, 30°C, 40°C)"},
                    {"content": "Reagent Lot (A, B, C)"},
                    {"content": "Incubation Time (1h, 2h)"},
                ],
            },
            "constraints": "Lot C supply limited to 5 runs. No experiments above 45°C (safety).",
            "materials": {
                "valueArray": [
                    {"content": "Reagent Lot A (500mL available)"},
                    {"content": "Reagent Lot B (300mL available)"},
                    {"content": "Reagent Lot C (50mL remaining)"},
                ],
            },
            "acceptance_criteria": "Yield >= 85% with RSD < 5%",
        },
    }

    result = service._parse_result(raw)

    assert result is not None, "Result should not be None"
    assert "Experimental Objective" in result
    assert "optimal temperature" in result
    assert "Factors and Levels" in result
    assert "Temperature" in result
    assert "Reagent Lot" in result
    assert "Constraints" in result
    assert "Lot C supply" in result
    assert "Materials" in result
    assert "Acceptance Criteria" in result
    assert "85%" in result
    print(f"   Output length: {len(result)} chars")
    print("   PASSED")


def test_parse_contents_response():
    """CU response with contents array (paragraph-level extraction)."""
    print("Test: Parse contents array response")

    service = _make_service()
    raw = {
        "contents": [
            {"content": "Protocol: Reagent Stability Assay v2.1"},
            {"content": "Objective: Investigate the root cause of yield drop observed in batches 47-49."},
            {"content": "Three factors are under investigation: temperature (20, 30, 40 °C), reagent lot (A, B, C), and incubation time (1h, 2h)."},
            {"content": "Previous results show lot C at 30°C gives 74% yield vs 90% for lot A."},
        ],
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Full Document Text" in result
    assert "Reagent Stability Assay" in result
    assert "root cause" in result
    assert "three factors" in result.lower()
    assert "lot C" in result
    print(f"   Output length: {len(result)} chars")
    print("   PASSED")


def test_parse_table_response():
    """CU response with a table."""
    print("Test: Parse table response")

    service = _make_service()
    raw = {
        "tables": [
            {
                "cells": [
                    {"rowIndex": 0, "columnIndex": 0, "content": "Run"},
                    {"rowIndex": 0, "columnIndex": 1, "content": "Temperature"},
                    {"rowIndex": 0, "columnIndex": 2, "content": "Lot"},
                    {"rowIndex": 0, "columnIndex": 3, "content": "Yield"},
                    {"rowIndex": 1, "columnIndex": 0, "content": "1"},
                    {"rowIndex": 1, "columnIndex": 1, "content": "20°C"},
                    {"rowIndex": 1, "columnIndex": 2, "content": "A"},
                    {"rowIndex": 1, "columnIndex": 3, "content": "92%"},
                    {"rowIndex": 2, "columnIndex": 0, "content": "2"},
                    {"rowIndex": 2, "columnIndex": 1, "content": "30°C"},
                    {"rowIndex": 2, "columnIndex": 2, "content": "C"},
                    {"rowIndex": 2, "columnIndex": 3, "content": "74%"},
                ],
            },
        ],
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Table 1" in result
    assert "Temperature" in result
    assert "92%" in result
    assert "74%" in result
    # Should have markdown table separators
    assert "---" in result
    print(f"   Output length: {len(result)} chars")
    print("   PASSED")


def test_parse_kv_pairs_response():
    """CU response with key-value pairs."""
    print("Test: Parse key-value pairs response")

    service = _make_service()
    raw = {
        "keyValuePairs": [
            {"key": {"content": "Protocol ID"}, "value": {"content": "RSA-2024-047"}},
            {"key": {"content": "Author"}, "value": {"content": "Dr. Smith"}},
            {"key": {"content": "Date"}, "value": {"content": "2024-11-15"}},
            {"key": {"content": "Max Runs"}, "value": {"content": "8"}},
        ],
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Protocol ID" in result
    assert "RSA-2024-047" in result
    assert "Dr. Smith" in result
    print("   PASSED")


def test_parse_combined_response():
    """CU response with contents + fields + tables (realistic)."""
    print("Test: Parse combined response")

    service = _make_service()
    raw = {
        "contents": [
            {"content": "Reagent Stability Assay Protocol"},
        ],
        "fields": {
            "objective": "Determine root cause of yield drop in batches 47-49",
            "factors": {
                "valueArray": [
                    {"content": "Temperature: 20°C, 30°C, 40°C"},
                    {"content": "Reagent Lot: A, B, C"},
                ],
            },
            "safety": "Do not exceed 45°C. Lot C may contain degraded components.",
        },
        "tables": [
            {
                "cells": [
                    {"rowIndex": 0, "columnIndex": 0, "content": "Lot"},
                    {"rowIndex": 0, "columnIndex": 1, "content": "Status"},
                    {"rowIndex": 1, "columnIndex": 0, "content": "A"},
                    {"rowIndex": 1, "columnIndex": 1, "content": "Available"},
                    {"rowIndex": 2, "columnIndex": 0, "content": "C"},
                    {"rowIndex": 2, "columnIndex": 1, "content": "Low stock"},
                ],
            },
        ],
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Experimental Objective" in result
    assert "yield drop" in result
    assert "Factors" in result
    assert "Temperature" in result
    assert "Safety" in result
    assert "45°C" in result
    assert "Table 1" in result
    assert "Low stock" in result
    print(f"   Output length: {len(result)} chars")
    print("   PASSED")


def test_parse_nested_analyze_result():
    """CU response wrapped in analyzeResult (some API versions)."""
    print("Test: Parse nested analyzeResult wrapper")

    service = _make_service()
    raw = {
        "analyzeResult": {
            "content": "Full text of the protocol document extracted by CU.",
        },
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Full text of the protocol" in result
    print("   PASSED")


def test_parse_empty_response():
    """Empty CU response → None."""
    print("Test: Parse empty response returns None")

    service = _make_service()
    result = service._parse_result({})

    assert result is None, f"Expected None, got: {result!r}"
    print("   PASSED")


def test_parse_string_fields():
    """CU fields as plain strings (not dicts)."""
    print("Test: Parse plain string fields")

    service = _make_service()
    raw = {
        "fields": {
            "objective": "Maximize yield of esterification reaction",
            "constraints": "Budget limited to 12 runs. Solvent X unavailable.",
        },
    }

    result = service._parse_result(raw)

    assert result is not None
    assert "Maximize yield" in result
    assert "12 runs" in result
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Content Understanding Service Tests")
    print("=" * 70)
    print()

    test_parse_fields_response()
    test_parse_contents_response()
    test_parse_table_response()
    test_parse_kv_pairs_response()
    test_parse_combined_response()
    test_parse_nested_analyze_result()
    test_parse_empty_response()
    test_parse_string_fields()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
