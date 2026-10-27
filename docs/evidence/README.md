# External evidence for the Georgia story

Every row was accessed on **2026-10-27**. Confidence:

- **high:** a primary source (government, FEMA, NWS, Red Cross, or a state plan) opened and quoted, or a number computed by a script in this folder.
- **medium:** reputable press opened and quoted.
- **unverified:** the page could not be opened, or only a search snippet was seen. Do not quote unverified rows.

Scripts in this folder:

- `capacity_checks.py`: `uv run --with duckdb python docs/evidence/capacity_checks.py ~/work/c4data/GA/shelters/data.parquet`
- `dch_roster_counts.py`: `python3 docs/evidence/dch_roster_counts.py` (live call to Georgia DCH)

## Five strongest facts for the pitch

1. **Georgia is a receiving state, measured by GDOT.** As Milton approached in 2024, GDOT reported I-75 northbound volumes 342% above normal on Monday evening, Oct 7, and 280% above normal at 8 a.m. Tuesday, Oct 8. The segment runs from the Florida line to Macon. I-95 northbound volumes were 264% and 89% above normal at the same times. ([GDOT release, reprinted by AllOnGeorgia](https://allongeorgia.com/georgia-state-news/georgia-dot-significant-increases-in-traffic-volumes-seen-on-georgia-interstates-as-hurricane-milton-approaches-floridas-west-coast/))
2. **The state's own plan says the coast cannot shelter its own residents.** Georgia's State Shelter Plan says "Coastal Georgia Counties may not be able to safely open emergency shelters". Each coastal county relies on county-to-county agreements to shelter residents who lack transport. Chatham County opens no local shelters before landfall. Inland counties' shelter lists are therefore the coastal plan. ([GEMA State Shelter Plan, p.47-48](https://gema.georgia.gov/document/document/state-shelter-plan/download); [CEMA](https://www.chathamemergency.org/PrepareNow/PreparednessArticle?articleId=Sheltering))
3. **Two school rows are 43.5% of Georgia's reported shelter capacity.** Commerce High School (270,135) and Commerce Primary School (225,112) together hold 495,247 of 1,138,056 reported evacuation spaces. Commerce had 7,387 residents in 2020. ([capacity_checks.py](capacity_checks.py); [Georgia legislature census table](https://www.legis.ga.gov/api/document/docs/default-source/reapportionment-document-library/2020-census-count-by-city-name.pdf?sfvrsn=5519a15_2))
4. **Medical-needs people are routed away from general shelters, to a plan that isn't public.** The State Shelter Plan says "Individuals who are identified as having medical needs will not be in general population shelters". The Department of Public Health (DPH) runs Medical Support Shelters under a plan "published under a separate cover", which we could not find online. ([State Shelter Plan, Annex A](https://gema.georgia.gov/document/document/state-shelter-plan/download))
5. **Georgia's own licensing roster shows how many assisted-living residents the federal data misses.** Georgia's Department of Community Health (DCH) feed, GaMap2Care, lists 326 assisted living communities (27,226 licensed beds) and 1,568 personal care homes (19,341 beds). The six coastal counties hold 20 assisted living communities (1,302 beds) and 49 personal care homes (461 beds). Cite these aggregate counts only: the feed has no stated licence and carries personal contact data, so it cannot be loaded (section 6). ([dch_roster_counts.py](dch_roster_counts.py); [GaMap2Care](https://forms.dch.georgia.gov/HFRD/GaMap2Care.html))

## 1. Hurricane Isaias, October 2026: corrections to our notes

Our notes (`strategy.md`) say: "Isaias hit Georgia Oct 8 to 10, 2026 (all 159 counties under emergency, federal declaration EM-3657)". That sentence merges two different declarations. Isaias was a Gulf landfall, and Georgia felt it as an inland wind and rain event, not a coastal evacuation.

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Landfall near Destin, FL, Category 2, 01:30 UTC Oct 10 (Fri evening local time) | 105 mph | [NHC update](https://www.nhc.noaa.gov/archive/2026/al09/al092026.update.10100129.shtml) via [Wikipedia](https://en.wikipedia.org/wiki/Hurricane_Isaias_(2026)) | 2026-10-27 | medium |
| Kemp's updated **state** emergency, Oct 8, covered all 159 counties. It mentions no shelters or evacuations | 159 counties | [gov.georgia.gov](https://gov.georgia.gov/press-releases/2026-10-08/gov-kemp-declares-state-emergency-ahead-hurricane-isaias) | 2026-10-27 | high |
| **Federal** EM-3657-GA, declared Oct 9, incident period Oct 8-15 | 76 counties | [OpenFEMA API](https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=disasterNumber%20eq%203657), [FEMA 3657](https://www.fema.gov/disaster/3657) | 2026-10-27 | high |
| EM-3657 covers Public Assistance only. Individual Assistance was not declared. Emergency protective measures are 75% federal | n/a | [FEMA release HQ-26-165](https://www.fema.gov/press-release/20261010/president-donald-j-trump-approves-emergency-declaration-georgia) | 2026-10-27 | high |
| None of the six coastal counties (Chatham, Bryan, Liberty, McIntosh, Glynn, Camden) is designated | 0 | OpenFEMA API above | 2026-10-27 | high |
| Georgia power outages, late morning Saturday Oct 10 (GEMA/HS) | 120,368 customers | [AJC recap](https://www.ajc.com/news/2026/10/hurricane-isaias-affects-georgia/) | 2026-10-27 | medium |
| No Georgia deaths found. AJC reports one death in Alabama and one in Florida; Wikipedia lists 9 deaths (FL 6, AL 2, SC 1) | 0 in GA | [AJC](https://www.ajc.com/news/2026/10/hurricane-isaias-affects-georgia/), [Wikipedia](https://en.wikipedia.org/wiki/Hurricane_Isaias_(2026)) | 2026-10-27 | medium |
| Georgia evacuee sites were small and local: an Exchange Club RV park in Albany, a shelter at First Baptist Church of Leesburg (Lee County), and a city campground in Moultrie limited by saturated ground | 3 sites | [WALB, Oct 9](https://www.walb.com/2026/10/09/free-evacuation-sites-available-south-georgia/) | 2026-10-27 | medium |
| Red Cross evacuation centers were in FL, MS and AL; no Georgia Red Cross shelter opening found | 21 centers | Red Cross page returned 403; search summary only | 2026-10-27 | unverified |
| No reports of Florida evacuees on I-75 in Georgia; Panhandle evacuation traffic was on I-10 | n/a | search across CNN, weather.com, WSB | 2026-10-27 | unverified (absence) |

**Pitch implication:** use Isaias as context, not as a shelter-failure story. The honest framing is that Isaias tested Georgia's inland counties, while the coastal plan, which runs through inland host counties, was never activated.

## 2. Georgia as receiving state

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Milton 2024: I-75 NB, FL line to Macon, 8 a.m. Tue Oct 8, vs normal | +280% | [GDOT via AllOnGeorgia](https://allongeorgia.com/georgia-state-news/georgia-dot-significant-increases-in-traffic-volumes-seen-on-georgia-interstates-as-hurricane-milton-approaches-floridas-west-coast/) | 2026-10-27 | high (GDOT text, reprint) |
| Milton 2024: Monday evening peak, I-75 NB / I-95 NB | +342% / +264% | same | 2026-10-27 | high |
| Milton 2024: I-95 NB, FL line to I-16, Tue 8 a.m. | +89% | same | 2026-10-27 | high |
| Irma 2017: GDOT says some areas saw traffic volumes rise by as much as | 600% | [GDOT Milepost Fall 2017, p.4](https://www.dot.ga.gov/PartnerSmart/Public/Documents/publications/MilePost/Milepost_Fall2017-web.pdf) | 2026-10-27 | high |
| Irma 2017: I-75 NB at Ocala (FL), hourly volume vs same day of 2016 | +1,236% | [FDOT evacuation report appendix, p.9](https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/info/co/news/newsreleases/020118-fdot-evacuation-report-appendix.pdf) | 2026-10-27 | high |
| Irma 2017: Florida's emergency shoulder lane ended at the GA line, causing congestion there | n/a | same, p.17 | 2026-10-27 | high |
| I-16 contraflow, Matthew 2016: Savannah to US 441 (Dublin), all four lanes westbound | 4 lanes | [GA DPS](https://dps.georgia.gov/press-releases/2016-10-06/hurricane-matthew-travel-advisory) | 2026-10-27 | high |
| Irma 2017: coastal Georgia ordered to evacuate; I-16 made one-way inland | ~540,000 | [AP via WRDW](https://www.wrdw.com/content/news/Nearly-540000-ordered-to-flee-Georgia-coast-ahead-of-Irma-443159803.html) | 2026-10-27 | medium |
| Dorian 2019: I-16 contraflow; third all-coast evacuation since 2016 | 3 in 4 yrs | [News4Jax](https://www.news4jax.com/news/2019/09/02/georgia-governor-orders-mandatory-coastal-evacuations/) | 2026-10-27 | medium |
| GEMA's points for I-16 contraflow intersections (2011 District 5 plan) | 32 points | [ArcGIS layer](https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/Contraflow_Intersections/FeatureServer/0) | 2026-10-27 | high |
| Michael 2018, Helene 2024: no northbound evacuation volume data found | n/a | n/a | 2026-10-27 | gap |

## 3. Georgia shelters hosting evacuees (actual use)

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Irma 2017: peak night (Mon), people in Red Cross and community shelters in Georgia | 5,500+ people, 40 shelters | [Red Cross Georgia](https://www.redcross.org/local/georgia/about-us/news-and-events/news/Hurricane-Irma-Red-Cross-and-community-partners-shelter-over-108000-people-overnight.html) | 2026-10-27 | high |
| Irma 2017: state goal before landfall, 50+ shelters, 7,000 beds; state parks for 10,000 | 7,000 / 10,000 | [WJLA/Sinclair](https://local21news.com/news/nation-world/watch-live-georgia-governor-provides-update-on-hurricane-irma) | 2026-10-27 | medium |
| Irma 2017: Augusta hosted Chatham's plan evacuees; some shelters at capacity | ~2,000 in 7 shelters | [GPB](https://www.gpb.org/news/2017/09/14/irma-recovery-continues-158k-without-power-in-georgia) | 2026-10-27 | medium |
| Michael 2018: Georgia Red Cross shelters, overnight stays, people | 11 / 2,844 / 847 | [Red Cross Georgia](https://www.redcross.org/local/georgia/about-us/news-and-events/press-releases/georgia-relief-efforts-transition.html) | 2026-10-27 | high |
| Ian 2022: evacuees staying in Georgia state parks | ~400 | [Atlanta News First](https://www.atlantanewsfirst.com/2022/09/28/hundreds-hurricane-ian-evacuees-head-georgia-state-parks-wait-out-storm/) | 2026-10-27 | medium |
| Helene 2024: people in Red Cross shelters across Georgia | 680+, 35 shelters | [Red Cross Georgia](https://www.redcross.org/local/georgia/about-us/news-and-events/news/ruins-recovery-hope-georgia-one-year-after-hurricane-helene.html) | 2026-10-27 | high |
| Helene 2024: Lowndes Co. (Valdosta), 3 shelters, 157 people; 99% of the county lost power | 157 | [NWS Tallahassee impact narratives, p.8](https://www.weather.gov/media/tae/TropicalEventSummary/PSHTAE_2024AL09_Helene_ImpactNarratives.pdf) | 2026-10-27 | high |
| Milton 2024: GEMA told evacuees "resources in South Georgia are limited"; state parks open to RVs | n/a | [GEMA Milton page](https://gema.georgia.gov/hurricane-milton) | 2026-10-27 | high |
| Milton 2024: Atlanta Motor Speedway campgrounds for evacuees | n/a | [AJC](https://www.ajc.com/news/georgia-news/atlanta-motor-speedway-opens-campgrounds-for-evacuees-of-hurricane-milton/3OXKL4R3DVBC5N4RXLNVAD53FE/) | 2026-10-27 | medium |
| Georgia World Congress Center used as a hurricane evacuee shelter | n/a | none found | 2026-10-27 | unverified |

**Use carefully:** actual peaks (5,500 for Irma, 680+ for Helene) are tiny next to the 1,138,056 reported capacity. Do not present that gap as spare capacity. The plan expects 5-10% of the population to seek public shelter (section 4), and the binding limits are staffing, medical support and power, not floor space.

## 4. Who runs sheltering in Georgia

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Georgia DHS is lead agency for ESF-6 (mass care), with DCA and the Red Cross | n/a | [GEMA ESF-6 annex](https://gema.georgia.gov/document/document/esf-6-mass-care-emergency-assistance-temporary-housing-and-human-assistance/download) | 2026-10-27 | high |
| "ARC is expected to provide most mass care services for affected residents within Georgia" | n/a | same | 2026-10-27 | high |
| Each recognized emergency management agency may open a shelter; most shelters are Red Cross-managed; "every County is a sheltering County" | 161 EMAs | [State Shelter Plan](https://gema.georgia.gov/document/document/state-shelter-plan/download) | 2026-10-27 | high |
| Planning ratio: "between 5% and 10% of the population will seek a public sheltering option" | 5-10% | same | 2026-10-27 | high |
| DPH opens and manages Medical Support Shelters in a large coastal evacuation; medical-needs people do not go to general shelters | n/a | same, Annex A | 2026-10-27 | high |
| DPH Medical Support Shelter Plan ("published under a separate cover") | n/a | not found online | 2026-10-27 | unverified |
| Coastal counties may not be able to open shelters; county-to-county agreements cover residents without transport (critical transportation need, CTN) | n/a | same, p.47-48 | 2026-10-27 | high |
| Chatham: "Shelters will not be opened locally for any category of hurricane prior to landfall"; older study estimate: 231,243 at risk, ~30,061 needing public shelter (study year not stated) | 30,061 | [CEMA](https://www.chathamemergency.org/PrepareNow/PreparednessArticle?articleId=Sheltering) | 2026-10-27 | high (quote) |
| Georgia Hurricane Evacuation Study (USACE/Dewberry): 6 coastal + 5 inland counties; "No evacuation shelters will be opened in the 11 counties" | 11 counties | [Dewberry](https://www.dewberry.com/insights-news/post/blog/2024/07/03/georgia-hurricane-evacuation-study-and-its-impact-on-the-2024-atlantic-hurricane-season) | 2026-10-27 | medium |
| GEMA hurricane evacuation zones (updated 2023-08-23): 11 counties, zones A-D plus X (Charlton) | 27 polygons | [ArcGIS layer 11](https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/Georgia_Hurricane_Evacuation_Zones/FeatureServer/11) | 2026-10-27 | high |
| Georgia Hurricane Plan exists (GEMA plan index) | n/a | [Plan library index](https://gema.georgia.gov/document/publication/plan-library-index/download); no public full text found | 2026-10-27 | high (existence) |
| A published statewide shelter deficit number | n/a | none found | 2026-10-27 | gap |

## 5. Shelter failures (power, generators, capacity)

The record is thin. Nothing below documents a Georgia shelter failing outright.

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Irma 2017: >923,000 customers out; "a large number of requests for generators from local governments" | 923,000 | [GEMA](https://gema.georgia.gov/press-releases/2017-09-11/gemahs-state-and-local-agencies-responding-hurricane-irma) | 2026-10-27 | high |
| Irma 2017: Augusta shelters "at capacity and cannot accept any additional evacuees" (Trinity on the Hill) | n/a | [GPB](https://www.gpb.org/news/2017/09/14/irma-recovery-continues-158k-without-power-in-georgia) | 2026-10-27 | medium |
| Irma 2017: Augusta after-action report mentions "shelters that temporarily lost power" | n/a | [Augusta after-action report](https://forms.augustaga.gov/WebLink/0/doc/108607/Page3.aspx); page needs cookies, search snippet only | 2026-10-27 | unverified |
| Helene 2024: South Georgia Medical Center (a hospital, not a shelter) generators "briefly failed" | n/a | [AJC](https://www.ajc.com/news/atlanta-news/valdosta-battered-by-helenes-winds-its-like-a-war-zone/SJLYLIX42JA6LNJYV6GNMHK4ZI/) | 2026-10-27 | medium |
| After Matthew 2016, Chatham changed plans: "General population will no longer bus to Augusta" | n/a | [WTOC](https://www.wtoc.com/2021/10/07/five-years-later-lessons-learned-hurricane-matthew/) | 2026-10-27 | medium |

## 6. Data sources we could add

The event rule (challenge README, "Bringing your own data") bars data with an **unstated licence** and any **individual-level personal data**; only public domain, CC0 and US Government works are safe. **None of the Georgia state and county sources below clears that bar, so none may be loaded into BigQuery, the repo or the agent.** They may be cited as sources for facts stated in this document.

Sources that do clear the bar: the provided snapshot tables, CMS, HHS emPOWER, HRSA, NOAA/IBTrACS and OpenFEMA.

| Source | What it holds | Access | License / terms | Usable as data |
|---|---|---|---|---|
| DCH GaMap2Care (licensed facilities) | Assisted living communities and personal care homes: ID, name, address, county, licensed beds, status, lat/lon | [JSON feed](https://forms.dch.georgia.gov/HFRD/GetFacilitiesData.svc/GetData?FACTYPE=Assisted%20Living%20Community&maxbeds=1000); [page](https://forms.dch.georgia.gov/HFRD/GaMap2Care.html) | None stated. Records include administrator names, phone numbers and emails | **No** (no licence; personal data). Aggregate counts may be cited |
| GEMA hurricane evacuation zones | 27 zone polygons, 11 counties | [FeatureServer/11](https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/Georgia_Hurricane_Evacuation_Zones/FeatureServer/11) | None stated (empty `licenseInfo`) | **No** (no licence) |
| GEMA contraflow intersections | 32 points on I-16 | [FeatureServer/0](https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/Contraflow_Intersections/FeatureServer/0) | None stated | **No** (no licence) |
| HIFLD hurricane evacuation routes (archived) | 31,593 segments, 832 in GA | [FeatureServer/0](https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Hurricane_Evacuation_Routes_1/FeatureServer/0) | "Esri Master License Agreement"; access "U.S. Government"; archived, no longer updated | **No** (Esri MLA is not public domain or CC0) |
| Chatham SAGIS/CEMA: evacuation zones, routes, shelters, long-term care | 3 zones; 1,195 route segments; 180 long-term-care sites | [SAGIS CEMA services](https://pub.sagis.org/arcgis/rest/services/CEMA/) | No-warranty disclaimer (snippet only); no licence. The zone service is labelled "FOR TESTING PURPOSES ONY" | **No** (no licence) |
| GDOT traffic counts (Traffic Analysis and Data Application, TADA) | Count stations, AADT, exports | [TADA](https://gdottrafficdata.drakewell.com/publicmultinodemap.asp); [GDOT road and traffic data](https://www.dot.ga.gov/GDOT/Pages/RoadTrafficData.aspx) | "provided 'as is'"; no license | **No** (no licence) |
| GDOT GIS servers (EOC support layers) | Unknown | [egis.dot.ga.gov](https://egis.dot.ga.gov/arcgis/rest/services/EOC_SUPPORT_LAYERS/MapServer) | Unknown (timed out from this VM) | **No** (no licence found) |
| DPH OASIS | Vital stats, hospital discharge, ER, BRFSS | [OASIS](https://oasis.state.ga.us/What-Can-Oasis-Do-For-You.aspx) | Copyright DPH; asks for a citation; no reuse license | **No** (no licence) |
| Georgia GIO data hub | 247 statewide feature services | [data-hub.gio.georgia.gov](https://data-hub.gio.georgia.gov/) | 98 of the first 100 services have no license | **No** (no licence) |

**DCH roster counts** (output of `dch_roster_counts.py`, run 2026-10-27):

| Type | Facilities | Licensed beds | Beds unrecorded | Coastal-6 facilities | Coastal-6 beds |
|---|---|---|---|---|---|
| Assisted living community | 326 | 27,226 | 5 | 20 | 1,302 |
| Personal care home | 1,568 | 19,341 | 65 | 49 | 461 |

All rows in the feed are status Active. DCH's program page says it oversees "a total of 2,910 facilities ... approximately 55,000 residents" ([DCH](https://dch.georgia.gov/divisionsoffices/hfrd/facilities-provider-information/personal-care-homes)). That figure is larger than the feed and the scope difference is unexplained, so quote the feed counts as "listed in GaMap2Care". The script reads the feed at run time and prints only these aggregates; no facility records are stored.

## 7. Commerce, GA capacity rows

| Claim | Number | Source | Accessed | Confidence |
|---|---|---|---|---|
| Commerce city population, 2020 Census (6,544 in 2010) | 7,387 | [Georgia legislature census table](https://www.legis.ga.gov/api/document/docs/default-source/reapportionment-document-library/2020-census-count-by-city-name.pdf?sfvrsn=5519a15_2) | 2026-10-27 | high |
| Commerce High School enrollment 2024-25 | 557 | [NCES](https://nces.ed.gov/ccd/schoolsearch/school_detail.asp?Search=1&DistrictID=1301440&ID=130144000622), search summary | 2026-10-27 | unverified |
| Commerce High 270,135 and Commerce Primary 225,112 = share of reported GA evacuation capacity | 43.5% (495,247 / 1,138,056) | `capacity_checks.py` | 2026-10-27 | high |
| Both Commerce school rows are usage EVAC with post-impact capacity 0. Every other Commerce row is BOTH with post-impact ≈ half of evacuation capacity | n/a | `capacity_checks.py` | 2026-10-27 | high |
| Across Georgia, 797 of 837 BOTH shelters have post-impact capacity = half of evacuation capacity | 797 / 837 | `capacity_checks.py` | 2026-10-27 | high |
| That ratio matches 20 sq ft per evacuee (FEMA) vs 40 sq ft per post-impact resident (FEMA field guide) | 20 / 40 sq ft | [FEMA RTLT Evacuation Shelter, 9-508-1192](https://rtlt.preptoolkit.fema.gov/Public/Resource/ViewFile/9-508-1192?type=Pdf); [FEMA P-785](https://www.nationalmasscarestrategy.org/wp-content/uploads/2015/10/Shelter-Field-Guide-508_f3.pdf) | 2026-10-27 | high (20 sq ft quote extracted) / medium (40) |

**Hypothesis, not verified:** the Commerce values are a data-entry error, possibly square footage typed into a headcount field. At 20 sq ft per person, 270,135 people would need 5.4 million sq ft. No building square footage for either school was found to test this.
