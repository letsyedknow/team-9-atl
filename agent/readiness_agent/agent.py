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

from .callbacks import check_wheelchair_callback, load_map_data_callback
from .evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_power_dependent_counties,
    find_vulnerable_tracts,
    identify_risky_shelters,
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

Tools:
- Prefer the purpose-built readiness tools for standard questions.
- For ad hoc BigQuery access, use only the read-only MCP tool against project `{PROJECT_ID}` and
  dataset `{DATASET_ID}`, tables ending in `_clean`.
- Ground specific shelters with Google Maps to confirm they still exist and what they are now, and
  say what the grounding changed. When Maps lists a wheelchair-accessible entrance for a shelter
  with no registry record, say so as "Google Maps lists ..., not verified": it does not prove a
  usable entrance or that the shelter admits people, and it never turns "not recorded" into "yes".
- Surge flags marked in_surge_source "noaa_slosh" (in the map data and in the readiness tools'
  results) were blank in the FEMA registry and filled from NOAA NHC surge maps, a worst-case
  planning composite, not a forecast. Say so whenever you cite one and give surge_first_category
  when it helps. A registry value always wins. The shelters table itself holds only FEMA's value;
  the fallback is table shelter_surge_noaa_clean, which you may also query read-only.
- When an answer lists shelters whose wheelchair record is not recorded, do not stop at "not
  recorded": ground up to 10 of them (highest capacity first) with Google Maps by name and address
  in the same turn, and show what Maps lists beside the registry value, labelled "Google Maps lists
  ..., unverified". Never ask the user whether to check first, and never use an area question
  ("which shelters take wheelchairs") for this.
- Wheelchair and generator have no stored fallback. Google Maps wheelchair lookups are on-demand
  and live, never stored; do not treat them as registry values or count them as "yes".
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
    before_agent_callback=[load_map_data_callback, check_wheelchair_callback],
    tools=[
        google_maps_grounding,
        bigquery_mcp,
        find_vulnerable_tracts,
        assess_shelter_accessibility,
        find_power_dependent_counties,
        identify_risky_shelters,
        build_readiness_brief,
    ],
)
