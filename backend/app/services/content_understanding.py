"""
Tessellarium — Azure Content Understanding client for PDF ingestion.

Calls the Content Understanding REST API to extract structured content
from protocol PDFs. Falls back to local PDF text extraction if the
service is unavailable.
"""

import asyncio
import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default analyzer for experimental protocols
DEFAULT_ANALYZER_ID = "tessellarium-protocol"

# Polling config
POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 60  # 2 minutes max


class ContentUnderstandingService:
    """
    Extracts structured information from protocol PDFs using
    Azure Content Understanding REST API.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        api_version: str = "2025-05-01-preview",
        analyzer_id: str = DEFAULT_ANALYZER_ID,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._api_version = api_version
        self._analyzer_id = analyzer_id
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Ocp-Apim-Subscription-Key"] = api_key

    async def analyze_protocol(
        self, pdf_bytes: bytes, filename: str,
    ) -> Optional[str]:
        """
        Submit a PDF to Content Understanding, poll for results,
        and return structured text suitable for the Parser Agent.

        Returns None if the service is unavailable or analysis fails.
        """
        try:
            raw_result = await self._submit_and_poll(pdf_bytes, filename)
            if raw_result is None:
                return None
            return self._parse_result(raw_result)
        except Exception as e:
            logger.warning(
                "Content Understanding analysis failed for %s: %s. "
                "Falling back to local extraction.",
                filename, e,
            )
            return None

    async def _submit_and_poll(
        self, pdf_bytes: bytes, filename: str,
    ) -> Optional[dict]:
        """Submit the PDF and poll the operation URL until completion."""
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/"
            f"{self._analyzer_id}:analyze"
            f"?api-version={self._api_version}"
        )

        encoded = base64.b64encode(pdf_bytes).decode("utf-8")
        body = {
            "url": f"data:application/pdf;base64,{encoded}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Submit analysis
            response = await client.post(
                url, json=body, headers=self._headers,
            )

            if response.status_code == 202:
                # Async operation — poll the operation URL
                operation_url = response.headers.get("operation-location")
                if not operation_url:
                    logger.warning("No operation-location header in 202 response")
                    return None
                return await self._poll_operation(client, operation_url)

            elif response.status_code == 200:
                # Synchronous result
                return response.json()

            else:
                logger.warning(
                    "Content Understanding returned %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                return None

    async def _poll_operation(
        self, client: httpx.AsyncClient, operation_url: str,
    ) -> Optional[dict]:
        """Poll an async operation URL until it completes or times out."""
        for _ in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            response = await client.get(
                operation_url, headers=self._headers,
            )

            if response.status_code != 200:
                logger.warning(
                    "Poll returned %d: %s",
                    response.status_code, response.text[:300],
                )
                return None

            result = response.json()
            status = result.get("status", "").lower()

            if status == "succeeded":
                return result.get("result", result)
            elif status in ("failed", "cancelled"):
                logger.warning("Analysis %s: %s", status, result.get("error", ""))
                return None
            # else: "running" / "notStarted" — keep polling

        logger.warning("Content Understanding polling timed out")
        return None

    def _parse_result(self, raw_result: dict) -> str:
        """
        Convert Content Understanding output into clean structured text
        for the Parser Agent.

        The CU response contains contents/fields with extracted values.
        We format them into a markdown-like protocol summary.
        """
        sections = []
        sections.append("# Extracted Protocol Content\n")

        # Handle the contents array (pages/paragraphs from CU)
        contents = raw_result.get("contents", [])
        if contents:
            full_text = []
            for item in contents:
                if isinstance(item, dict):
                    text = item.get("content", item.get("text", ""))
                    if text:
                        full_text.append(text.strip())
                elif isinstance(item, str):
                    full_text.append(item.strip())
            if full_text:
                sections.append("## Full Document Text\n")
                sections.append("\n\n".join(full_text))
                sections.append("")

        # Handle structured fields from custom analyzer
        fields = raw_result.get("fields", {})
        if fields:
            field_map = {
                "objective": "## Experimental Objective",
                "factors": "## Factors and Levels",
                "levels": "## Factor Levels",
                "controls": "## Controls",
                "constraints": "## Constraints",
                "materials": "## Materials and Reagents",
                "acceptance_criteria": "## Acceptance Criteria",
                "methods": "## Methods",
                "results": "## Results",
                "observations": "## Observations",
                "hypotheses": "## Hypotheses",
                "equipment": "## Equipment",
                "safety": "## Safety Considerations",
            }

            for field_key, heading in field_map.items():
                value = fields.get(field_key)
                if value is None:
                    continue

                content = self._extract_field_value(value)
                if content:
                    sections.append(f"{heading}\n")
                    sections.append(content)
                    sections.append("")

        # Handle tables if present
        tables = raw_result.get("tables", [])
        for i, table in enumerate(tables):
            sections.append(f"## Table {i + 1}\n")
            sections.append(self._format_table(table))
            sections.append("")

        # Handle key-value pairs
        kv_pairs = raw_result.get("keyValuePairs", [])
        if kv_pairs:
            sections.append("## Additional Key-Value Pairs\n")
            for pair in kv_pairs:
                key = pair.get("key", {}).get("content", "Unknown")
                val = pair.get("value", {}).get("content", "")
                if val:
                    sections.append(f"- **{key}**: {val}")
            sections.append("")

        # If we got nothing structured, try the raw content/analyzeResult
        if len(sections) <= 1:
            analyze_result = raw_result.get("analyzeResult", {})
            if analyze_result:
                return self._parse_result(analyze_result)

            # Last resort: dump readable content
            content = raw_result.get("content", "")
            if content:
                sections.append("## Document Content\n")
                sections.append(content)

        result = "\n".join(sections).strip()
        return result if result and result != "# Extracted Protocol Content" else None

    @staticmethod
    def _extract_field_value(value) -> Optional[str]:
        """Extract text from a CU field value (can be string, dict, or list)."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            content = value.get("content", value.get("valueString", ""))
            if content:
                return content
            items = value.get("valueArray", [])
            if items:
                parts = []
                for item in items:
                    if isinstance(item, str):
                        parts.append(f"- {item}")
                    elif isinstance(item, dict):
                        parts.append(f"- {item.get('content', item.get('valueString', str(item)))}")
                return "\n".join(parts)
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(f"- {item}")
                elif isinstance(item, dict):
                    parts.append(f"- {item.get('content', item.get('valueString', str(item)))}")
            return "\n".join(parts) if parts else None
        return str(value) if value else None

    @staticmethod
    def _format_table(table: dict) -> str:
        """Format a CU table into markdown."""
        cells = table.get("cells", [])
        if not cells:
            return "(empty table)"

        max_row = max(c.get("rowIndex", 0) for c in cells) + 1
        max_col = max(c.get("columnIndex", 0) for c in cells) + 1

        grid = [["" for _ in range(max_col)] for _ in range(max_row)]
        for cell in cells:
            r = cell.get("rowIndex", 0)
            c = cell.get("columnIndex", 0)
            grid[r][c] = cell.get("content", "").strip()

        lines = []
        for i, row in enumerate(grid):
            lines.append("| " + " | ".join(row) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in row) + " |")

        return "\n".join(lines)


async def extract_text_from_pdf(pdf_bytes: bytes) -> Optional[str]:
    """
    Fallback: extract raw text from a PDF using pdfplumber.
    Used when Content Understanding is not configured.
    """
    try:
        import pdfplumber
        import io

        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return "\n\n".join(text_parts) if text_parts else None

    except ImportError:
        logger.warning("pdfplumber not installed. Cannot extract PDF text locally.")
        return None
    except Exception as e:
        logger.warning("Local PDF extraction failed: %s", e)
        return None
