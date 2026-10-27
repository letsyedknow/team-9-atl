import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from .map_data import SHELTER_COLUMNS, SUSPECT_HIGH, SUSPECT_LOW, shelter_record

load_dotenv()

DEFAULT_PROJECT_ID = "qwiklabs-gcp-04-edc952746633"
DEFAULT_DATASET = "evac_prod"

# Every tool result names its dataset and table, so every figure the agent quotes can cite it
# (Constitution III).
SOURCES = {
    "shelters": "FEMA NSS registry · shelters_clean",
    "tracts": "ACS 5-yr and CDC SVI · vulnerability_tracts_clean",
    "power": "HHS emPOWER · power_dependent_counties_clean",
}

MAX_SHELTER_IDS = 25
LIVE_CHECK_STATUSES = ("exists", "renamed", "closed", "unknown")


def _dataset_name() -> str:
    return os.getenv("EVAC_DATASET", DEFAULT_DATASET)


def _project_id() -> str:
    return os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)


def _table_name(base_name: str) -> str:
    return f"{base_name}_clean"


def _table(base_name: str) -> str:
    return f"`{_project_id()}.{_dataset_name()}.{_table_name(base_name)}`"


def _bigquery():
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - dependency is installed at runtime
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc
    return bigquery


def _bigquery_client():
    return _bigquery().Client(project=_project_id())


def _run_query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    bigquery = _bigquery()
    client = _bigquery_client()
    job_config = bigquery.QueryJobConfig()
    if params:
        job_config.query_parameters = params

    rows = client.query(sql, job_config=job_config)
    return [dict(row) for row in rows.result()]


def _scalar(name: str, type_: str, value: Any):
    return _bigquery().ScalarQueryParameter(name, type_, value)


def _flag_counts(shelters: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = {"yes": 0, "no": 0, "unrecorded": 0}
    for s in shelters:
        counts[s[key].lower()] += 1
    return counts


def _survey(value: Any) -> Any:
    """CDC SVI publishes -999 for missing; a missing estimate is None, never a number."""
    return None if isinstance(value, (int, float)) and value < 0 else value


def find_vulnerable_tracts(
    state: str | None = None,
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the tracts with the most households without a vehicle, then the highest no-vehicle,
    age 65+ and disability shares. Pass county_fips (e.g. "13051") when the screen gives one.

    pct_disability is an ACS survey estimate via CDC SVI; a missing value (-999 at source) is
    returned as None. Every tract keeps its county_fips.
    """
    filters = []
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("c.state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(c.county) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("v.county_fips = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT
          v.geo_id AS tract_id,
          v.county_fips,
          c.county AS county_name,
          v.households_no_vehicle,
          v.pct_no_vehicle,
          v.pct_age_65_plus,
          v.pct_disability,
          v.mobile_homes
        FROM {_table('vulnerability_tracts')} v
        JOIN {_table('power_dependent_counties')} c ON c.fips_code = v.county_fips
        {where_clause}
        ORDER BY v.households_no_vehicle DESC, v.pct_no_vehicle DESC, v.pct_age_65_plus DESC
        LIMIT @limit
    """

    tracts = [
        {**row, **{k: _survey(row.get(k)) for k in ("pct_no_vehicle", "pct_age_65_plus", "pct_disability")}}
        for row in _run_query(sql, params=params)
    ]
    return {"tracts": tracts, "source": SOURCES["tracts"]}


def assess_shelter_accessibility(
    state: str | None = "GA",
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the shelters most in need of verification across a county or state: those with no
    wheelchair-access record first, then by recorded capacity. Pass county_fips when the screen
    gives one.

    Flags are YES / NO / UNRECORDED. UNRECORDED means nobody assessed it; it is never "no".
    Capacities below 0 or above 100,000 are flagged suspect_capacity and never rank first.
    """
    filters = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(county_name) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("county_fips = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))

    sql = f"""
        SELECT {", ".join(SHELTER_COLUMNS)}
        FROM {_table('shelters')}
        WHERE {" AND ".join(filters)}
        ORDER BY
          wheelchair_accessible IS NULL DESC,
          IF(evacuation_capacity < {SUSPECT_LOW} OR evacuation_capacity > {SUSPECT_HIGH}, 0,
             evacuation_capacity) DESC,
          shelter_name ASC
        LIMIT @limit
    """

    shelters = [shelter_record(row) for row in _run_query(sql, params=params)]
    return {
        "shelters": shelters,
        "wheelchair": _flag_counts(shelters, "wheelchair_accessible"),
        "source": SOURCES["shelters"],
    }


def get_shelters(shelter_ids: list[str]) -> dict[str, Any]:
    """Return the registry records for specific shelters, in the order given (at most 25). Use it
    for the CONTEXT v1 shelter_id, or for a scenario's receiving_top / affected_shelter_ids.

    Flags are YES / NO / UNRECORDED. UNRECORDED means nobody assessed it; it is never "no".
    """
    if len(shelter_ids) > MAX_SHELTER_IDS:
        raise ValueError(f"At most {MAX_SHELTER_IDS} shelter ids per call; got {len(shelter_ids)}.")
    if not shelter_ids:
        return {"shelters": [], "source": SOURCES["shelters"]}

    sql = f"""
        SELECT {", ".join(SHELTER_COLUMNS)}
        FROM {_table('shelters')}
        WHERE CAST(shelter_id AS STRING) IN UNNEST(@ids)  -- shelter_id is INT64 in shelters_clean
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = [_bigquery().ArrayQueryParameter("ids", "STRING", [str(i) for i in shelter_ids])]
    by_id = {str(row["shelter_id"]): shelter_record(row) for row in _run_query(sql, params=params)}
    return {
        "shelters": [by_id[str(i)] for i in shelter_ids if str(i) in by_id],
        "source": SOURCES["shelters"],
    }


def find_power_dependent_counties(
    state: str | None = None,
    county: str | None = None,
    county_fips: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return counties ranked by electricity-dependent medical-equipment demand.

    emPOWER is published per county: say how many, never which tract or block.
    """
    filters = []
    params = [_scalar("limit", "INT64", limit)]
    if state:
        filters.append("state = @state")
        params.append(_scalar("state", "STRING", state.upper()))
    if county:
        filters.append("LOWER(county) = LOWER(@county)")
        params.append(_scalar("county", "STRING", county))
    if county_fips:
        filters.append("fips_code = @county_fips")
        params.append(_scalar("county_fips", "STRING", county_fips))
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
          fips_code AS county_fips
        FROM {_table('power_dependent_counties')}
        {where_clause}
        ORDER BY power_dependent_dme DESC
        LIMIT @limit
    """

    return {"counties": _run_query(sql, params=params), "source": SOURCES["power"]}


def record_live_check(shelter_id: str, status: str, place_id: str | None = None) -> dict[str, Any]:
    """Report what Google Maps showed for one shelter you grounded: status is exists, renamed,
    closed or unknown. Call it after grounding a specific shelter. Nothing is stored; only the
    place_id is kept, by the frontend, for the session."""
    if status not in LIVE_CHECK_STATUSES:
        raise ValueError(f"status must be one of {', '.join(LIVE_CHECK_STATUSES)}; got {status!r}.")
    return {
        "live_check": {
            "shelter_id": str(shelter_id),
            "status": status,
            "place_id": place_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    }


def build_readiness_brief(
    state: str,
    county: str | None = None,
    county_fips: str | None = None,
    shelter_limit: int = 5,
    tract_limit: int = 5,
) -> dict[str, Any]:
    """Construct a concise readiness brief: the riskiest tracts, the shelters most in need of
    verification, medical power dependence, and a counted list of what could not be determined."""
    if not state or not (county or county_fips):
        raise ValueError("A state and either a county or a county_fips are required.")

    where = {"state": state, "county": county, "county_fips": county_fips}
    vulnerable = find_vulnerable_tracts(**where, limit=tract_limit)
    shelters = assess_shelter_accessibility(**where, limit=shelter_limit)
    power = find_power_dependent_counties(**where, limit=5)
    to_verify = shelters["shelters"]

    return {
        "state": state.upper(),
        "county": county,
        "county_fips": county_fips,
        "vulnerable_tracts": vulnerable["tracts"],
        "shelters_to_verify": to_verify,
        "medical_dependency": power["counties"],
        "sources": {
            "vulnerable_tracts": vulnerable["source"],
            "shelters_to_verify": shelters["source"],
            "medical_dependency": power["source"],
        },
        "could_not_tell": {
            "wheelchair_unrecorded": _flag_counts(to_verify, "wheelchair_accessible")["unrecorded"],
            "generator_unrecorded": _flag_counts(to_verify, "generator_onsite")["unrecorded"],
            "shelters_considered": len(to_verify),
            "notes": [
                "Distances are straight-line; drive times are not included.",
                "emPOWER is county-level: it says how many, never which block.",
                "Whether a shelter will be open during a storm is not known from this data.",
            ],
        },
        "recommendation": (
            "Prioritize shelters with missing accessibility data, high surge exposure, and low verified capacity; "
            "then route vulnerable tracts to the nearest workable shelter candidates."
        ),
    }
