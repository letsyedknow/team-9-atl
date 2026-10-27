import os

from google.adk.agents import LlmAgent
from google.adk.tools import google_maps_grounding

from .evacuation_tools import (
    assess_shelter_accessibility,
    build_readiness_brief,
    find_power_dependent_counties,
    find_vulnerable_tracts,
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
        "Use the data tables to rank vulnerable tracts, then ground specific shelters with Google Maps "
        "to confirm they still exist and to check what they are now. Keep the distinction between 'no' and "
        "'unrecorded' in accessibility data explicit. Never confuse a blank accessibility value with a known "
        "'no'. Produce a concrete readiness brief with a plan for what to fix before September."
    ),
    tools=[
        google_maps_grounding,
        find_vulnerable_tracts,
        assess_shelter_accessibility,
        find_power_dependent_counties,
        build_readiness_brief,
    ],
)
