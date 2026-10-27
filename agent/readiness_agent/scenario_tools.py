import json
from datetime import UTC, datetime
from datetime import date as Date
from typing import Any

from .evacuation_tools import _dataset_name, _project_id, _run_query

CONTEXT_PREFIX = "CONTEXT v1 "
RANGE_LABEL = "scenario range from 27 past storms"
TOP_COUNTIES = 20
N_DRAWS = 400
SEED = 20261027
CASES = ("low", "base", "high")
AFFECTED_SHARE = 0.10
DIALYSIS_DOWN_SHARE = 0.50
CATEGORY_FLOOR_KT = {0: 34, 1: 64, 2: 83, 3: 96, 4: 113, 5: 137}
RELOCATION_SHARE = {"low": 0.10, "base": 0.20, "high": 0.40}


def _context(tool_context: Any) -> dict[str, Any]:
    content = getattr(tool_context, "user_content", None)
    for part in getattr(content, "parts", None) or []:
        text = (getattr(part, "text", None) or "").strip()
        if text.startswith(CONTEXT_PREFIX):
            try:
                return json.loads(text[len(CONTEXT_PREFIX):])
            except json.JSONDecodeError:
                return {}
    return {}


def _track_lonlats(scenario: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = (scenario or {}).get("track") or {}
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if geometry.get("type") == "Point":
        coords = [coords]
    return [(float(c[0]), float(c[1])) for c in coords if len(c) >= 2]


def _band(values) -> dict[str, float]:
    import numpy as np

    p10, p50, p90 = np.quantile(values, [0.1, 0.5, 0.9], axis=0)
    return {"p10": round(float(p10), 3), "p50": round(float(p50), 3), "p90": round(float(p90), 3)}


def _people(values) -> dict[str, int]:
    return {k: round(v) for k, v in _band(values).items()}


def run_scenario(
    lat: float | None = None,
    lon: float | None = None,
    heading_deg: float | None = None,
    date: str | None = None,
    intensity_kt: float | None = None,
    category: int | None = None,
    county_fips: str | None = None,
    case: str = "base",
    tool_context: Any = None,
) -> dict[str, Any]:
    """Model a hurricane scenario for Georgia counties: outage share ranges, power-dependent residents, oxygen, home-health and dialysis patients at risk, and, for a selected county, reachable medical shelters and dialysis centres with live drive times and evacuation delay.

    Uses the track drawn on the map (sent in CONTEXT v1) when there is one; otherwise matches past storms that passed near (lat, lon) with a similar heading, time of year and intensity. Call it whenever the user asks what a storm would do, who is at risk, or where people could go. All numbers come from this tool; report them as a scenario range from 27 past storms.
    """
    case = case if case in CASES else "base"
    ctx = _context(tool_context)
    scenario_ctx = ctx.get("scenario") or {}
    lonlats = _track_lonlats(scenario_ctx)
    if len(lonlats) < 2 and (lat is None or lon is None):
        return {
            "status": "needs_track_or_position",
            "message": "Draw a track on the map, or give the storm's lat, lon, heading and date.",
        }

    import numpy as np

    from .scenario import data, engine, storms
    from .scenario.receiving import receiving_sites

    county_fips = county_fips or ctx.get("county_fips")
    category = category if category is not None else scenario_ctx.get("category")
    month = Date.fromisoformat(date).month if date else datetime.now(UTC).month

    match: dict[str, Any] | None = None
    if len(lonlats) >= 2:
        tracks = [storms.drawn_track(lonlats, int(category if category is not None else 3))]
        source, used = "drawn_track", []
        likelihood = storms.pattern_frequency(
            track=tracks[0], min_intensity_kt=CATEGORY_FLOOR_KT[int(category or 0)]
        )
        origin = storms.classify_origin(lonlats[0][1], lonlats[0][0])
    else:
        analogs = storms.analog_tracks(lat, lon, heading_deg or 0.0, month, intensity_kt)
        if category is not None:
            analogs = [storms.rescale(a, int(category)) for a in analogs]
        if not analogs:
            return {"status": "no_matching_past_storms", "lat": lat, "lon": lon, "month": month}
        tracks = [a.track for a in analogs]
        source = "matched_past_storms"
        likelihood = storms.pattern_frequency(
            lat=lat, lon=lon, heading_deg=heading_deg, month=month, min_intensity_kt=intensity_kt
        )
        used = [f"{a.name} {a.season}" for a in analogs]
        origin = storms.classify_origin(lat, lon)
        match = {
            "matched": len(analogs),
            "share_reaching_georgia_100km": round(
                sum(a.reached_ga_100km for a in analogs) / len(analogs), 2
            ),
        }

    result = engine.run(tracks, n_draws=N_DRAWS, seed=SEED)
    counties = data.counties()
    risk = engine.people_at_risk(result, counties)
    outage = result.outage
    p50 = np.median(outage, axis=0)

    order = np.argsort(-np.median(risk["power_dependent"], axis=0))
    picked = list(order[:TOP_COUNTIES])
    index = {c["county_fips"]: i for i, c in enumerate(counties)}
    if county_fips in index and index[county_fips] not in picked:
        picked.append(index[county_fips])

    rows = []
    for i in picked:
        c = counties[i]
        rows.append({
            "county_fips": c["county_fips"],
            "county_name": c["county_name"],
            "outage_share": _band(outage[:, i]),
            "peak_wind_kt": round(float(result.peak_wind_kt[i]), 1),
            "hours_ts_winds": round(float(result.hours_34kt[i]), 1),
            "ts_winds_arrive_h": None if np.isnan(result.ts_arrival_h[i])
            else round(float(result.ts_arrival_h[i]), 1),
            "power_dependent": {"residents": c["power_dependent"],
                                "at_risk": _people(risk["power_dependent"][:, i])},
            "oxygen_users": {"residents": c["oxygen"], "at_risk": _people(risk["oxygen"][:, i])},
            "home_health_users": {"residents": c["home_health"],
                                  "at_risk": _people(risk["home_health"][:, i])},
            "dialysis_patients": {"patients": c["dialysis_patients"],
                                  "centres_down": bool(p50[i] >= DIALYSIS_DOWN_SHARE)},
            "nursing_home_beds": c.get("nursing_home_beds", 0),
            "assisted_living_beds": c.get("assisted_living_beds", 0),
            "status": "censored_count" if c.get("power_dependent_censored") else "modelled",
        })

    receiving = None
    if county_fips in index:
        i = index[county_fips]
        down = {counties[j]["county_fips"] for j in np.where(p50 >= DIALYSIS_DOWN_SHARE)[0]}
        surge_cat = int(category) if category else None
        receiving = receiving_sites(
            counties[i], data.sites(), down, surge_cat, origin, case,
            None if np.isnan(result.ts_arrival_h[i]) else float(result.ts_arrival_h[i]),
            relocation_share=RELOCATION_SHARE[case],
            power_dependent_at_risk=float(np.median(risk["power_dependent"][:, i])),
        )

    statewide = {
        "counties_affected": _people((outage >= AFFECTED_SHARE).sum(axis=1)),
        "power_dependent_at_risk": _people(risk["power_dependent"].sum(axis=1)),
        "oxygen_users_at_risk": _people(risk["oxygen"].sum(axis=1)),
        "dialysis_patients_at_risk": _people(risk["dialysis"].sum(axis=1)),
        "facility_beds_exposed": _people(risk["facility_beds"].sum(axis=1)),
    }
    affected = [counties[j]["county_fips"] for j in np.where(p50 >= AFFECTED_SHARE)[0]]
    affected_set = set(affected)
    affected_shelters = [
        s["shelter_id"] for s in data.sites().get("medical_shelters", [])
        if s["county_fips"] in affected_set
        or (category and int(category) in s.get("in_surge", []))
    ]
    return {
        "affected_county_fips": affected,
        "affected_shelter_ids": affected_shelters,
        "receiving_top": [r.get("shelter_id") or r.get("ccn") for r in (receiving or {}).get("sites", [])],
        "scenario": {
            "source": source,
            "origin": origin,
            "category": category,
            "month": month,
            "past_storms_used": used[:12],
            "match": match,
            "likelihood": likelihood,
            "support": "outside_labeled_support" if any(result.outside_support)
            else "within_labeled_support",
            "range_label": RANGE_LABEL,
            "assumptions": {
                "affected_threshold_share": AFFECTED_SHARE,
                "dialysis_down_share": DIALYSIS_DOWN_SHARE,
                "relocation_share": RELOCATION_SHARE[case],
                "case": case,
            },
        },
        "statewide": statewide,
        "counties": rows,
        "receiving": receiving,
    }


def season_county_risk(county_fips: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Season-long hurricane risk per Georgia county from about 2,000 simulated storms based on every storm since 1950 near Georgia: chance per year of losing power to at least 25% of customers, power-dependent residents affected in a typical and a 1-in-10 year, dialysis patients displaced, and people left without a powered seat. Without county_fips, returns the counties with the most people left uncovered."""
    from google.cloud import bigquery

    table = f"`{_project_id()}.{_dataset_name()}.scenario_season_county`"
    if county_fips:
        return _run_query(
            f"SELECT * FROM {table} WHERE county_fips = @fips",
            [bigquery.ScalarQueryParameter("fips", "STRING", county_fips)],
        )
    return _run_query(
        f"SELECT * FROM {table} ORDER BY uncovered_1in10 DESC LIMIT @limit",
        [bigquery.ScalarQueryParameter("limit", "INT64", limit)],
    )


def gap_sensitivity() -> list[dict[str, Any]]:
    """Unknowns in Georgia's records ranked by how much each changes the number of power-dependent and dialysis patients left without a powered seat or a chair in a 1-in-10 season, with the record to collect to resolve each one."""
    table = f"`{_project_id()}.{_dataset_name()}.scenario_fix_ranking`"
    return _run_query(f"SELECT * FROM {table} ORDER BY swing DESC")
