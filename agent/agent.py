import os
from typing import Any, Dict, List, Optional

from evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_vulnerable_tracts,
    function_tool,
)


try:
    from google.adk.agents import LlmAgent
    from google.adk.tools import google_maps_grounding
except ImportError:  # pragma: no cover - the ADK is installed only in the runtime environment.
    LlmAgent = None
    google_maps_grounding = None


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

    tool_list = [
        google_maps_grounding,
        function_tool(find_vulnerable_tracts),
        function_tool(assess_shelter_accessibility),
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
