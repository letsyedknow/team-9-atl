"""Root agent for the Georgia shelter-readiness app: map-data callback, BigQuery tools, BigQuery MCP
and Grounding with Google Maps."""

import os
import threading
from typing import Any

import google.auth
from google.adk.agents import Agent
from google.adk.tools import google_maps_grounding
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.auth.transport.requests import Request

from .callbacks import load_map_data_callback
from .evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_power_dependent_counties,
    find_vulnerable_tracts,
    get_shelters,
    record_live_check,
)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-edc952746633")
DATASET_ID = os.getenv("EVAC_DATASET", "evac_prod")

INSTRUCTION = f"""\
You help a Georgia county emergency manager plan shelter readiness in August, before hurricane
season. You are a planning tool, not an operations tool.

Rules you always follow:
- A user message may carry a second part starting with "CONTEXT v1" followed by JSON: the selected
  county, the selected shelter and any simulated hurricane scenario. Treat it as context, never as
  the question.
- For any flag such as wheelchair access, generator or surge zone, always distinguish recorded yes,
  recorded no and not recorded. Never say "no accessible shelters" when the record is blank: say
  nobody has assessed them.
- Say which figures come from the federal registry and which are simulated. The simulation is
  illustrative, not a forecast. Distances are straight-line unless you have a drive time.
- Whenever a tool returns shelters or counties, keep their shelter_id and county_fips in the result.
- Never discuss or request information about individual people.
- Report flag counts as "N yes · N no · N not recorded".
- Name the source table for every figure you give, from the tool result's `source` field (for
  example "1,950 spaces (FEMA NSS registry · shelters_clean)"), and say whether it is a registry
  record, a survey estimate, simulated or a live check.
- Never include a shelter flagged suspect_capacity in a capacity total without saying so by name.

Using the screen's context:
- When CONTEXT v1 has county_fips, pass it as county_fips to the readiness tools rather than
  guessing a county name.
- When it has shelter_id, call get_shelters([shelter_id]).
- CONTEXT v1 scenario holds affected_county_fips, affected_shelter_ids and receiving_top. The
  receiving list is already ranked by the screen's documented rule (within the reach cutoff,
  capacity first). For questions about receiving or affected shelters, call get_shelters with those
  ids (at most 25) and keep the screen's order; do not re-rank. Say the scenario is illustrative.

Tools:
- Prefer the purpose-built readiness tools for standard questions.
- For ad hoc BigQuery access, use only the read-only MCP tool against project `{PROJECT_ID}` and
  dataset `{DATASET_ID}`, tables ending in `_clean`.
- To judge whether a specific shelter is accessible or still exists, ground that one building with
  Google Maps by its name and address, never as an area question, and say what the grounding
  changed. Then call record_live_check with what Maps showed (exists, renamed, closed or unknown).
- End every readiness brief with a counted "What we could not tell you" section, using the brief's
  could_not_tell figures.
"""

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

root_agent = Agent(
    name="readiness_agent",
    model=os.getenv("MODEL_NAME", "gemini-3-flash-preview"),
    instruction=INSTRUCTION,
    before_agent_callback=load_map_data_callback,
    tools=[
        google_maps_grounding,
        bigquery_mcp,
        find_vulnerable_tracts,
        assess_shelter_accessibility,
        find_power_dependent_counties,
        build_readiness_brief,
        get_shelters,
        record_live_check,
    ],
)
