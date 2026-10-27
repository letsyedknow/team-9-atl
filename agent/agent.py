import os
import threading
from typing import Any, Dict, List, Optional

from evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_power_dependent_counties,
    find_vulnerable_tracts,
    function_tool,
)


try:
    from google.adk.agents import LlmAgent
    from google.adk.tools import google_maps_grounding
except ImportError:  # pragma: no cover - the ADK is installed only in the runtime environment.
    LlmAgent = None
    google_maps_grounding = None

try:
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )
except ImportError:  # pragma: no cover - available with the ADK MCP extra.
    McpToolset = None
    StreamableHTTPConnectionParams = None


_BIGQUERY_MCP_CREDENTIALS = None
_BIGQUERY_MCP_CREDENTIALS_LOCK = threading.Lock()


def _bigquery_mcp_headers(_: Any) -> Dict[str, str]:
    """Provide fresh ADC bearer credentials to the remote BigQuery MCP server."""
    global _BIGQUERY_MCP_CREDENTIALS

    import google.auth
    from google.auth.transport.requests import Request

    with _BIGQUERY_MCP_CREDENTIALS_LOCK:
        if _BIGQUERY_MCP_CREDENTIALS is None:
            _BIGQUERY_MCP_CREDENTIALS, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
        if not _BIGQUERY_MCP_CREDENTIALS.valid or not _BIGQUERY_MCP_CREDENTIALS.token:
            _BIGQUERY_MCP_CREDENTIALS.refresh(Request())

        return {
            "Authorization": f"Bearer {_BIGQUERY_MCP_CREDENTIALS.token}",
        }


def create_agent() -> "LlmAgent":
    """Construct the evacuation readiness agent.

    This agent keeps one reasoning loop and uses Google Maps grounding to validate the current state "
    "of shelters while a custom Python tool quantifies the vulnerability and shelter-readiness gaps "
    "using the BigQuery tables in the target dataset."
    """
    if LlmAgent is None:
        raise RuntimeError(
            "The Google ADK runtime is not installed. Install dependencies from agent/requirements.txt."
        )
    if McpToolset is None:
        raise RuntimeError(
            "ADK MCP support is not installed. Install dependencies from agent/requirements.txt."
        )

    project_id = os.getenv(
        "GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633"
    )
    dataset_id = os.getenv("EVAC_DATASET", "evacuation_readiness")
    bigquery_mcp = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="https://bigquery.googleapis.com/mcp",
            timeout=10,
            sse_read_timeout=300,
        ),
        tool_filter=["execute_sql_readonly"],
        header_provider=_bigquery_mcp_headers,
    )

    tool_list = [
        google_maps_grounding,
        bigquery_mcp,
        function_tool(find_vulnerable_tracts),
        function_tool(assess_shelter_accessibility),
        function_tool(find_power_dependent_counties),
        function_tool(build_readiness_brief),
    ]

    return LlmAgent(
        name="evacuation_readiness_agent",
        model=os.getenv("MODEL_NAME", "gemini-3.0-flash"),
        description=(
            "An emergency-planning agent that uses BigQuery data and Google Maps grounding to find "
            "the most vulnerable tracts and the shelters that must be verified before hurricane season."
        ),
        instruction=(
            "You are an emergency readiness assistant for a county emergency manager. "
            f"For ad hoc BigQuery access, use only the read-only MCP tool and query project `{project_id}` "
            f"and the `{dataset_id}` dataset; use tables ending in `_clean`. "
            "Prefer the purpose-built readiness tools for standard questions. "
            "Use the data tables to rank vulnerable tracts, then ground specific shelters with Google Maps "
            "to confirm they still exist and to check what they are now. Keep the distinction between 'no' and "
            "'unrecorded' in accessibility data explicit. Never confuse a blank accessibility value with a known "
            "'no'. Produce a concrete readiness brief with a plan for what to fix before September."
        ),
        tools=tool_list,
    )


if __name__ == "__main__":
    agent = create_agent()
    print(f"Agent created: {agent.name}")
