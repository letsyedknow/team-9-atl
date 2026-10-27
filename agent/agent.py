import os
import threading
from typing import Any

import google.auth
from google.adk.agents import LlmAgent
from google.adk.tools import google_maps_grounding
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.auth.transport.requests import Request

from .evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_power_dependent_counties,
    find_vulnerable_tracts,
)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET_ID = os.getenv("EVAC_DATASET", "evac_prod")

_bigquery_mcp_credentials = None
_bigquery_mcp_credentials_lock = threading.Lock()


def _bigquery_mcp_headers(_: Any) -> dict[str, str]:
    global _bigquery_mcp_credentials
    with _bigquery_mcp_credentials_lock:
        if _bigquery_mcp_credentials is None:
            _bigquery_mcp_credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
        if not _bigquery_mcp_credentials.valid or not _bigquery_mcp_credentials.token:
            _bigquery_mcp_credentials.refresh(Request())
        return {"Authorization": f"Bearer {_bigquery_mcp_credentials.token}"}


bigquery_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://bigquery.googleapis.com/mcp",
        timeout=10,
        sse_read_timeout=300,
    ),
    tool_filter=["execute_sql_readonly"],
    header_provider=_bigquery_mcp_headers,
)

root_agent = LlmAgent(
    name="evacuation_readiness_agent",
    model=os.getenv("MODEL_NAME", "gemini-3-flash-preview"),
    description=(
        "An emergency-planning agent that uses BigQuery data and Google Maps grounding to find "
        "the most vulnerable tracts and the shelters that must be verified before hurricane season."
    ),
    instruction=(
        "You are an emergency readiness assistant for a county emergency manager. "
        f"For ad hoc BigQuery access, use only the read-only MCP tool and query project `{PROJECT_ID}` "
        f"and the `{DATASET_ID}` dataset; use tables ending in `_clean`. "
        "Prefer the purpose-built readiness tools for standard questions. "
        "Use the data tables to rank vulnerable tracts, then ground specific shelters with Google Maps "
        "to confirm they still exist and to check what they are now. Keep the distinction between 'no' and "
        "'unrecorded' in accessibility data explicit. Never confuse a blank accessibility value with a known "
        "'no'. Produce a concrete readiness brief with a plan for what to fix before September."
    ),
    tools=[
        google_maps_grounding,
        bigquery_mcp,
        find_vulnerable_tracts,
        assess_shelter_accessibility,
        find_power_dependent_counties,
        build_readiness_brief,
    ],
)
