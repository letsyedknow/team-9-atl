import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROJECT_ID = "qwiklabs-gcp-04-edc952746633"
DEFAULT_DATASET = "evac_prod"


def _dataset_name() -> str:
    return os.getenv("EVAC_DATASET", DEFAULT_DATASET)


def _project_id() -> str:
    return os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)


def _table_name(base_name: str) -> str:
    return f"{base_name}_clean"


SURGE_FALLBACK_TABLE = "shelter_surge_noaa"


@lru_cache(maxsize=1)
def _surge_fallback_exists() -> bool:
    try:
        from google.cloud.exceptions import NotFound

        _bigquery_client().get_table(
            f"{_project_id()}.{_dataset_name()}.{_table_name(SURGE_FALLBACK_TABLE)}"
        )
        return True
    except NotFound:
        return False


def _shelters_with_surge_fallback() -> str:
    """Shelters with the surge flag filled from NOAA's surge maps only where the registry is blank.

    A recorded FEMA value always wins. in_surge_source says which one was used, so every answer can
    name its source. If the fallback table has not been loaded yet, the registry is used unchanged.
    """
    shelters = f"`{_project_id()}.{_dataset_name()}.{_table_name('shelters')}`"
    if not _surge_fallback_exists():
        return f"(SELECT s.*, 'registry' AS in_surge_source, CAST(NULL AS INT64) AS surge_first_category FROM {shelters} s)"
    fallback = f"`{_project_id()}.{_dataset_name()}.{_table_name(SURGE_FALLBACK_TABLE)}`"
    return f"""(
          SELECT
            s.* REPLACE (
              COALESCE(SAFE_CAST(s.in_surge_slosh_area AS BOOL), f.in_surge_fallback) AS in_surge_slosh_area
            ),
            IF(SAFE_CAST(s.in_surge_slosh_area AS BOOL) IS NULL AND f.in_surge_fallback IS NOT NULL,
               'noaa_slosh', 'registry') AS in_surge_source,
            f.first_category AS surge_first_category
          FROM {shelters} s
          LEFT JOIN {fallback} f ON CAST(s.shelter_id AS STRING) = f.shelter_id
        )"""


def _bigquery_client():
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - dependency is installed at runtime
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    return bigquery.Client(project=_project_id())


def _run_query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
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
    state: str | None = None,
    county: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the tracts with the highest vulnerability indicators for no-vehicle households and age/disability risk."""
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    county_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('power_dependent_counties')}`"
    tract_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('vulnerability_tracts')}`"

    filters = []
    if state:
        filters.append("c.state = @state")
    if county:
        filters.append("LOWER(c.county) = LOWER(@county)")
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
          v.mobile_homes,
          ST_GEOGPOINT(v.lon, v.lat) AS geo
        FROM {tract_table} v
        JOIN {county_table} c ON c.fips_code = v.county_fips
        {where_clause}
        ORDER BY v.households_no_vehicle DESC, v.pct_no_vehicle DESC, v.pct_age_65_plus DESC
        LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if state:
        params.insert(0, bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        params.insert(0, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=params)


def assess_shelter_accessibility(
    state: str | None = None,
    county: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
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
          shelter_id,
          shelter_name,
          county_fips,
          COALESCE(county_name, county_parish) AS county,
          evacuation_capacity,
          CASE
            WHEN evacuation_capacity IS NOT NULL AND (evacuation_capacity < 0 OR evacuation_capacity > 100000)
              THEN TRUE
            ELSE FALSE
          END AS has_suspect_capacity,
          wheelchair_accessible,
          generator_onsite,
          is_medical,
          in_surge_slosh_area,
          in_surge_source,
          surge_first_category,
          CASE
            WHEN wheelchair_accessible IS NULL THEN 'unrecorded'
            WHEN wheelchair_accessible = TRUE THEN 'yes'
            ELSE 'no'
          END AS accessibility_status,
          CASE
            WHEN generator_onsite IS NULL THEN 'unrecorded'
            WHEN generator_onsite = TRUE THEN 'yes'
            ELSE 'no'
          END AS generator_status,
          CASE
            WHEN in_surge_slosh_area IS NULL THEN 'unrecorded'
            WHEN in_surge_slosh_area = TRUE THEN 'yes'
            ELSE 'no'
          END AS surge_status,
          CASE
            WHEN wheelchair_accessible IS NULL THEN 1
            ELSE 0
          END AS accessibility_gap,
          ST_GEOGPOINT(longitude, latitude) AS geo
        FROM {_shelters_with_surge_fallback()}
        {where_clause}
        ORDER BY
          accessibility_gap DESC,
          IF(evacuation_capacity IS NOT NULL AND evacuation_capacity BETWEEN 0 AND 100000, evacuation_capacity, -1) DESC,
          shelter_name ASC
        LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if state:
        params.insert(0, bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        params.insert(0, bigquery.ScalarQueryParameter("county", "STRING", county))

    return _run_query(sql, params=params)


def find_power_dependent_counties(
    state: str | None = None,
    county: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
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


def identify_risky_shelters(
    state: str | None = "GA",
    county: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Identify risky shelters vs. non-risky shelters using census tract spatial mapping and FEMA NRI hurricane hazard metrics, and return capacity for each category and shelter.

    Classification criteria (from Shelter_clean.ipynb):
    - Risky ('High Exposure Risk'): in_surge_slosh_area is TRUE OR tract hurricane annual frequency (HRCN_AFREQ) > 0.1.
    - Not Risky:
      - 'Designated Resilient': Not risky AND generator_onsite is TRUE.
      - 'Standard Shelter': Not risky AND generator_onsite is not TRUE.
    """
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-bigquery is required. Install dependencies from agent/requirements.txt."
        ) from exc

    shelters_table = _shelters_with_surge_fallback()
    hazard_table = f"`{_project_id()}.{_dataset_name()}.{_table_name('hazard_tracts')}`"

    filters = []
    if state:
        filters.append("s.state = @state")
    if county:
        filters.append("(LOWER(s.county_name) = LOWER(@county) OR LOWER(s.county_parish) = LOWER(@county))")
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    cte_sql = f"""
        WITH mapped_shelters AS (
          SELECT
            s.shelter_id,
            s.shelter_name,
            s.address_1,
            s.city,
            s.county_fips,
            COALESCE(s.county_name, s.county_parish) AS county_name,
            s.state,
            s.latitude,
            s.longitude,
            s.evacuation_capacity,
            s.post_impact_capacity,
            s.wheelchair_accessible,
            s.generator_onsite,
            s.in_surge_slosh_area,
            s.in_surge_source,
            s.surge_first_category,
            t.geo_id AS tract_geo_id
          FROM {shelters_table} s
          LEFT JOIN `bigquery-public-data.geo_census_tracts.us_census_tracts_national` t
            ON ST_CONTAINS(t.tract_geom, ST_GEOGPOINT(s.longitude, s.latitude))
            AND (s.county_fips IS NULL OR t.state_fips_code = SUBSTR(s.county_fips, 1, 2))
          {where_clause}
        ),
        classified_shelters AS (
          SELECT
            m.*,
            h.HRCN_AFREQ,
            h.HRCN_EXPP,
            h.HRCN_EALT,
            h.HRCN_EALP,
            CASE
              WHEN m.evacuation_capacity IS NOT NULL
                   AND (m.evacuation_capacity < 0 OR m.evacuation_capacity > 100000)
                THEN TRUE
              ELSE FALSE
            END AS has_suspect_capacity,
            CASE
              WHEN m.evacuation_capacity IS NOT NULL
                   AND m.evacuation_capacity BETWEEN 0 AND 100000
                THEN m.evacuation_capacity
              ELSE NULL
            END AS clean_evacuation_capacity,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN TRUE
              ELSE FALSE
            END AS is_risky,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN 'Risky'
              ELSE 'Not Risky'
            END AS risk_status,
            CASE
              WHEN COALESCE(SAFE_CAST(m.in_surge_slosh_area AS BOOL), FALSE) = TRUE
                   OR COALESCE(h.HRCN_AFREQ, 0.0) > 0.1
                THEN 'High Exposure Risk'
              WHEN COALESCE(SAFE_CAST(m.generator_onsite AS BOOL), FALSE) = TRUE
                THEN 'Designated Resilient'
              ELSE 'Standard Shelter'
            END AS hurricane_designation,
            CASE
              WHEN m.in_surge_slosh_area IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.in_surge_slosh_area AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS surge_status,
            CASE
              WHEN m.generator_onsite IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.generator_onsite AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS generator_status,
            CASE
              WHEN m.wheelchair_accessible IS NULL THEN 'unrecorded'
              WHEN SAFE_CAST(m.wheelchair_accessible AS BOOL) = TRUE THEN 'yes'
              ELSE 'no'
            END AS wheelchair_status
          FROM mapped_shelters m
          LEFT JOIN {hazard_table} h
            ON m.tract_geo_id = h.geo_id
        )
    """

    risk_summary_sql = f"""
        {cte_sql}
        SELECT
          risk_status,
          is_risky,
          COUNT(*) AS total_shelters,
          COUNTIF(clean_evacuation_capacity IS NOT NULL AND clean_evacuation_capacity > 0) AS shelters_with_evac_capacity,
          COUNTIF(evacuation_capacity IS NULL OR evacuation_capacity <= 0) AS shelters_missing_or_zero_capacity,
          COUNTIF(has_suspect_capacity) AS suspect_capacity_shelters,
          COALESCE(SUM(clean_evacuation_capacity), 0) AS total_evacuation_capacity,
          COALESCE(SUM(evacuation_capacity), 0) AS raw_evacuation_capacity_incl_suspect,
          ROUND(AVG(clean_evacuation_capacity), 1) AS avg_evacuation_capacity,
          COALESCE(SUM(post_impact_capacity), 0) AS total_post_impact_capacity,
          ROUND(AVG(post_impact_capacity), 1) AS avg_post_impact_capacity,
          COUNTIF(wheelchair_status = 'yes') AS wheelchair_yes_count,
          COUNTIF(wheelchair_status = 'no') AS wheelchair_no_count,
          COUNTIF(wheelchair_status = 'unrecorded') AS wheelchair_unrecorded_count,
          COUNTIF(generator_status = 'yes') AS generator_yes_count,
          COUNTIF(generator_status = 'no') AS generator_no_count,
          COUNTIF(generator_status = 'unrecorded') AS generator_unrecorded_count,
          COUNTIF(surge_status = 'yes') AS surge_yes_count,
          COUNTIF(surge_status = 'no') AS surge_no_count,
          COUNTIF(surge_status = 'unrecorded') AS surge_unrecorded_count,
          COUNTIF(in_surge_source = 'noaa_slosh') AS surge_from_noaa_count
        FROM classified_shelters
        GROUP BY risk_status, is_risky
        ORDER BY is_risky DESC
    """

    designation_summary_sql = f"""
        {cte_sql}
        SELECT
          hurricane_designation,
          is_risky,
          COUNT(*) AS total_shelters,
          COUNTIF(has_suspect_capacity) AS suspect_capacity_shelters,
          COALESCE(SUM(clean_evacuation_capacity), 0) AS total_evacuation_capacity,
          COALESCE(SUM(evacuation_capacity), 0) AS raw_evacuation_capacity_incl_suspect,
          ROUND(AVG(clean_evacuation_capacity), 1) AS avg_evacuation_capacity,
          COALESCE(SUM(post_impact_capacity), 0) AS total_post_impact_capacity,
          COUNTIF(surge_status = 'yes') AS in_surge_count,
          COUNTIF(surge_status = 'no') AS not_in_surge_count,
          COUNTIF(surge_status = 'unrecorded') AS surge_unrecorded_count,
          COUNTIF(in_surge_source = 'noaa_slosh') AS surge_from_noaa_count,
          ROUND(AVG(IF(surge_status = 'yes', 1.0, 0.0)) * 100, 2) AS in_surge_percent,
          COUNTIF(generator_status = 'yes') AS generator_count,
          COUNTIF(generator_status = 'no') AS generator_no_count,
          COUNTIF(generator_status = 'unrecorded') AS generator_unrecorded_count,
          ROUND(AVG(IF(generator_status = 'yes', 1.0, 0.0)) * 100, 2) AS generator_percent,
          COUNTIF(wheelchair_status = 'yes') AS wheelchair_yes_count,
          COUNTIF(wheelchair_status = 'no') AS wheelchair_no_count,
          COUNTIF(wheelchair_status = 'unrecorded') AS wheelchair_unrecorded_count,
          ROUND(AVG(HRCN_AFREQ), 4) AS hrcn_freq_mean,
          MIN(HRCN_AFREQ) AS hrcn_freq_min,
          MAX(HRCN_AFREQ) AS hrcn_freq_max,
          COUNTIF(HRCN_AFREQ IS NULL) AS hrcn_freq_nulls
        FROM classified_shelters
        GROUP BY hurricane_designation, is_risky
        ORDER BY is_risky DESC, hurricane_designation ASC
    """

    shelter_list_sql = f"""
        {cte_sql}
        SELECT
          shelter_id,
          shelter_name,
          address_1,
          city,
          county_fips,
          county_name,
          state,
          clean_evacuation_capacity AS evacuation_capacity,
          evacuation_capacity AS raw_evacuation_capacity,
          has_suspect_capacity,
          post_impact_capacity,
          is_risky,
          risk_status,
          hurricane_designation,
          in_surge_slosh_area,
          in_surge_source,
          surge_first_category,
          surge_status,
          generator_onsite,
          generator_status,
          wheelchair_accessible,
          wheelchair_status,
          tract_geo_id,
          ROUND(HRCN_AFREQ, 4) AS hrcn_afreq,
          HRCN_EXPP AS hrcn_expp,
          HRCN_EALT AS hrcn_ealt,
          HRCN_EALP AS hrcn_ealp,
          ST_GEOGPOINT(longitude, latitude) AS geo
        FROM classified_shelters
        WHERE is_risky = @is_risky
        ORDER BY COALESCE(clean_evacuation_capacity, -1) DESC, shelter_name ASC
        LIMIT @limit
    """

    base_params: list[Any] = []
    if state:
        base_params.append(bigquery.ScalarQueryParameter("state", "STRING", state.upper()))
    if county:
        base_params.append(bigquery.ScalarQueryParameter("county", "STRING", county))

    risky_params = list(base_params) + [
        bigquery.ScalarQueryParameter("is_risky", "BOOL", True),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    not_risky_params = list(base_params) + [
        bigquery.ScalarQueryParameter("is_risky", "BOOL", False),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]

    return {
        "state": state.upper() if state else None,
        "county": county,
        "capacity_by_risk": _run_query(risk_summary_sql, params=base_params),
        "capacity_by_designation": _run_query(designation_summary_sql, params=base_params),
        "risky_shelters": _run_query(shelter_list_sql, params=risky_params),
        "not_risky_shelters": _run_query(shelter_list_sql, params=not_risky_params),
        "fema_attribution": (
            "This product uses the Federal Emergency Management Agency's National Risk Index "
            "but is not endorsed by FEMA."
        ),
    }


def build_readiness_brief(
    state: str,
    county: str,
    shelter_limit: int = 5,
    tract_limit: int = 5,
) -> dict[str, Any]:
    """Construct a concise readiness brief containing the biggest risk tracts and the shelters most in need of verification."""
    if not state or not county:
        raise ValueError("Both state and county are required.")

    vulnerable = find_vulnerable_tracts(state=state, county=county, limit=tract_limit)
    shelters = assess_shelter_accessibility(state=state, county=county, limit=shelter_limit)
    power = find_power_dependent_counties(state=state, county=county, limit=5)
    risk_analysis = identify_risky_shelters(state=state, county=county, limit=shelter_limit)

    return {
        "state": state.upper(),
        "county": county,
        "vulnerable_tracts": vulnerable,
        "shelters_to_verify": shelters,
        "medical_dependency": power,
        "shelter_risk_and_capacity": risk_analysis,
        "recommendation": (
            "Prioritize shelters with missing accessibility data, high surge exposure, and low verified capacity; "
            "avoid routing evacuees to High Exposure Risk shelters during active landfalls and route vulnerable tracts "
            "to nearest Designated Resilient or verified Standard shelters."
        ),
    }

