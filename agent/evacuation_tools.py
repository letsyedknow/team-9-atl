import os
from typing import Any, Dict, List, Optional


DEFAULT_DATASET = "evacuation_readiness"


def _dataset_name() -> str:
    return os.getenv("EVAC_DATASET", DEFAULT_DATASET)


def _project_id() -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT is not set. Export it before calling the tools."
        )
    return project_id


def _bigquery_client():
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - dependency is installed at runtime
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    return bigquery.Client(project=_project_id())


def _run_query(sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    client = _bigquery_client()
    job_config = bigquery.QueryJobConfig()
    if params:
        job_config.query_parameters = params

    rows = client.query(sql, job_config=job_config)
    return [dict(row) for row in rows.result()]


def find_vulnerable_tracts(
    state: str,
    county: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return the tracts with the highest vulnerability indicators for no-vehicle households and age/disability risk."""
    if not state:
        raise ValueError("state is required, for example 'FL' or 'SC'.")

    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    county_filter = "" if not county else "AND county_name = @county"
    sql = f"""
        SELECT
          tract_id,
          county_name,
          households_no_vehicle,
          pct_no_vehicle,
          pct_age_65_plus,
          pct_disability,
          mobile_homes,
          ST_GEOGPOINT(longitude, latitude) AS geo
        FROM `{_project_id()}.{_dataset_name()}.vulnerability_tracts`
        WHERE state = @state
          {county_filter}
        ORDER BY households_no_vehicle DESC, pct_no_vehicle DESC, pct_age_65_plus DESC
        LIMIT @limit
    """

    params = [
        bigquery.ScalarQueryParameter("state", "STRING", state.upper()),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if county:
        params.insert(1, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=[p for p in params])


def assess_shelter_accessibility(
    state: str,
    county: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return shelters ranked by accessibility gap and readiness concern across a county or state."""
    if not state:
        raise ValueError("state is required, for example 'FL' or 'SC'.")

    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    county_filter = "" if not county else "AND county = @county"
    sql = f"""
        SELECT
          shelter_name,
          county,
          evacuation_capacity,
          wheelchair_accessible,
          generator_onsite,
          is_medical,
          in_surge_slosh_area,
          CASE
            WHEN wheelchair_accessible IS NULL THEN 'unrecorded'
            WHEN wheelchair_accessible = TRUE THEN 'yes'
            ELSE 'no'
          END AS accessibility_status,
          CASE
            WHEN wheelchair_accessible IS NULL THEN 1
            ELSE 0
          END AS accessibility_gap,
          ST_GEOGPOINT(longitude, latitude) AS geo
        FROM `{_project_id()}.{_dataset_name()}.shelters`
        WHERE state = @state
          {county_filter}
        ORDER BY accessibility_gap DESC, evacuation_capacity DESC, shelter_name ASC
        LIMIT @limit
    """

    params = [
        bigquery.ScalarQueryParameter("state", "STRING", state.upper()),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if county:
        params.insert(1, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=[p for p in params])


def build_readiness_brief(
    state: str,
    county: str,
    shelter_limit: int = 5,
    tract_limit: int = 5,
) -> Dict[str, Any]:
    """Construct a concise readiness brief containing the biggest risk tracts and the shelters most in need of verification."""
    if not state or not county:
        raise ValueError("Both state and county are required.")

    vulnerable = find_vulnerable_tracts(state=state, county=county, limit=tract_limit)
    shelters = assess_shelter_accessibility(state=state, county=county, limit=shelter_limit)

    return {
        "state": state.upper(),
        "county": county,
        "vulnerable_tracts": vulnerable,
        "shelters_to_verify": shelters,
        "recommendation": (
            "Prioritize shelters with missing accessibility data, high surge exposure, and low verified capacity; "
            "then route vulnerable tracts to the nearest workable shelter candidates."
        ),
    }


def function_tool(fn):
    """Wrap a Python function as an ADK tool if the SDK is installed."""
    try:
        from google.adk.tools import FunctionTool
    except ImportError:  # pragma: no cover
        return fn
    return FunctionTool(func=fn)
