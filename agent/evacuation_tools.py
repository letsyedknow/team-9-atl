import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROJECT_ID = "qwiklabs-gcp-04-edc952746633"
DEFAULT_DATASET = "evacuation_readiness"


def _dataset_name() -> str:
    return os.getenv("EVAC_DATASET", DEFAULT_DATASET)


def _project_id() -> str:
    return os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)


def _table_name(base_name: str) -> str:
    return f"{base_name}_clean"


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
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return the tracts with the highest vulnerability indicators for no-vehicle households and age/disability risk."""
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    shelter_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('shelters')}`"
    tract_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('vulnerability_tracts')}`"

    filters = []
    if state:
        filters.append("state = @state")
    if county:
        filters.append("LOWER(county_name) = LOWER(@county)")
    shelter_filter = " AND ".join(filters)
    county_filter = ""
    if shelter_filter:
        county_filter = (
            "WHERE county_fips IN ("
            f"SELECT DISTINCT county_fips FROM {shelter_table} "
            f"WHERE {shelter_filter}"
            ")"
        )

    sql = f"""
        SELECT
          geo_id AS tract_id,
          county_fips,
          (SELECT county_name FROM {shelter_table} WHERE county_fips = v.county_fips LIMIT 1)
            AS county_name,
          households_no_vehicle,
          pct_no_vehicle,
          pct_age_65_plus,
          pct_disability,
          mobile_homes,
          ST_GEOGPOINT(lon, lat) AS geo
        FROM {tract_table} v
        {county_filter}
        ORDER BY households_no_vehicle DESC, pct_no_vehicle DESC, pct_age_65_plus DESC
        LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if state:
        params.insert(0, bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        params.insert(0, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=params)


def assess_shelter_accessibility(
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return shelters ranked by accessibility gap and readiness concern across a county or state."""
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    filters = []
    if state:
        filters.append("state = @state")
    if county:
        filters.append("LOWER(county_name) = LOWER(@county)")
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT
          shelter_name,
          county_name AS county,
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
        FROM `{_project_id()}.{_dataset_name()}.{_table_name('shelters')}`
        {where_clause}
        ORDER BY accessibility_gap DESC, evacuation_capacity DESC, shelter_name ASC
        LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if state:
        params.insert(0, bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        params.insert(0, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=params)


def find_power_dependent_counties(
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return counties ranked by electricity-dependent medical-equipment demand."""
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    filters = []
    if state:
        filters.append("state = @state")
    if county:
        filters.append("LOWER(county) = LOWER(@county)")
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT
          county,
          state,
          power_dependent_dme,
          power_dependent_devices_dme,
          facility_esrd_dialysis_any_dme,
          o2_services_any_dme,
          home_health_services_any_dme,
          athome_hospice_any_dme,
          any_healthcare_srvc_any_dme,
          fips_code
        FROM `{_project_id()}.{_dataset_name()}.{_table_name('power_dependent_counties')}`
        {where_clause}
        ORDER BY power_dependent_dme DESC
        LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if state:
        params.insert(0, bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        params.insert(0, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=params)


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
    power = find_power_dependent_counties(state=state, county=county, limit=5)

    return {
        "state": state.upper(),
        "county": county,
        "vulnerable_tracts": vulnerable,
        "shelters_to_verify": shelters,
        "medical_dependency": power,
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
