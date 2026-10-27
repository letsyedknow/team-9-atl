# Tasks: Georgia Shelter Readiness Map

**Input**: Design documents from `/specs/001-georgia-shelter-map/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: This is not test-first. Tests are included only where the spec or constitution requires
them:
- SC-003: blank never renders as "no" (Constitution gate 1)
- SC-005b: no affected shelter appears in the receiving list
- FR-007: suspect capacities are handled correctly
- The payload matches the schema
- The SC-007 demo path, as an e2e smoke test

**Organization**: by user story (spec.md). US1 and US2 are P1, US3 is P2, US4 is P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on unfinished tasks)
- **[Story]**: US1–US4, for user-story phases only

## Path Conventions

- Frontend: `frontend/src/`, `frontend/tests/`
- Agent service: `agent/readiness_agent/`, `agent/server.py`, `agent/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeletons for both halves.

- [X] T001 Scaffold the Vite + React 18.3 + TypeScript 5 app in `frontend/`. Create `frontend/package.json` with:
  - dependencies `react`, `react-dom`, `d3-geo`, `topojson-client`, `@turf/turf`, `react-markdown`, `remark-gfm`
  - devDependencies `vite`, `@vitejs/plugin-react`, `typescript`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `msw`, `@playwright/test`, `us-atlas@3`, `@types/d3-geo`, `@types/topojson-client`
  - scripts `dev`, `build`, `test` (vitest run), `build:counties` (node scripts/build-ga-counties.mjs)
  - also `frontend/index.html`, `frontend/tsconfig.json`, `frontend/src/main.tsx`
- [X] T002 [P] Configure `frontend/vite.config.ts`:
  - React plugin
  - dev-server proxy for `/apps`, `/run`, `/run_sse` to `http://localhost:8000`
  - Vitest block with `environment: 'jsdom'` and setup file `frontend/tests/setup.ts`, which imports `@testing-library/jest-dom`
- [X] T003 [P] Create `agent/requirements.txt`:
  - `google-adk` pinned to an exact version; record it in `specs/001-georgia-shelter-map/research.md` R1
  - `google-cloud-bigquery`, `fastapi`, `uvicorn[standard]`, `pytest`, `jsonschema`
  - also create an empty `agent/readiness_agent/__init__.py` that does `from . import agent`, as the ADK app convention requires
- [X] T004 [P] Add lint config:
  - `frontend/eslint.config.js` (typescript-eslint recommended)
  - `agent/pyproject.toml` with a `[tool.ruff]` section (line-length 100) and a `[tool.pytest.ini_options]` section (testpaths = ["tests"])
- [X] T005 [P] Configure Playwright in `frontend/playwright.config.ts`: webServer `npm run dev`, baseURL `http://localhost:5173`, chromium only. Create an MSW handler skeleton in `frontend/tests/mocks/handlers.ts` for `POST /apps/readiness_agent/users/:u/sessions`, `POST /run` and `POST /run_sse`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Validated data, the map-data path through the agent, shared types and the app shell.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 Run notebook validation for Georgia (Constitution VI):
  1. Set `STATE = "GA"` in `notebooks/c4_01_load_explore.ipynb`, or run `scripts/load.sh`.
  2. Run the validation section and confirm there is no FAIL.
  3. Copy every WARN, with its row count and example rows, into a new section "## Validation run (GA)" at the end of `specs/001-georgia-shelter-map/research.md`. Expect the Commerce High School and Commerce Primary School capacities above 100,000.
- [X] T007 [P] Write `frontend/scripts/build-ga-counties.mjs`:
  1. Read `node_modules/us-atlas/counties-10m.json`.
  2. Keep geometries in `objects.counties` whose `id` starts with `"13"`, and drop the `states` and `nation` objects.
  3. Throw unless exactly 159 remain.
  4. Write `frontend/src/assets/ga-counties.topo.json`.
  5. Record the us-atlas version and its ISC / Census public-domain license in research.md R3.
  Run it and commit the asset.
- [X] T008 [P] Create `frontend/src/lib/types.ts` mirroring [data-model.md](data-model.md) exactly: `Flag`, `FlagCounts`, `SourcedValue`, `Shelter`, `County`, `MapData`, `HurricaneScenario`, `ReceivingEntry`, `ChatExchange`, `AnswerSegment`. Flags are string unions and never booleans.
- [X] T009 [P] Create `frontend/src/lib/flags.ts`:
  - `flagLabel(f)`: YES → "Yes", NO → "No", UNRECORDED → "Not recorded"
  - `flagClass(f)`: CSS class. UNRECORDED gets a distinct hatched neutral style, never the NO color
  - `countFlags(shelters, key): FlagCounts`
  - `sourceLabel(v: SourcedValue)`: always renders the dataset **and the table**, e.g. "FEMA NSS registry · shelters", "ACS survey estimate via CDC SVI · vulnerability_tracts · 412 of 415 tracts" (Constitution III)
  - `flagCountsLine(c: FlagCounts)`: always returns "{yes} yes · {no} no · {unrecorded} not recorded". There is no variant that shows only Yes (Constitution I)
  - `exclusionNote(excluded: {name}[])`: returns "" if empty, otherwise "Excludes {n} shelter(s) with suspect capacity: {names}" (Constitution VI)
  - add the matching styles to `frontend/src/styles/flags.css`
- [X] T010 [P] Write `frontend/tests/unit/flags.test.ts`, covering SC-003 at unit level:
  - UNRECORDED is labeled "Not recorded" and its class differs from NO
  - `countFlags` keeps unrecorded separate and never adds it to `no`
  - no helper returns a boolean for a Flag
  - `flagCountsLine` always includes all three counts, even when `no` and `unrecorded` are 0
  - `exclusionNote` names every excluded shelter and its count, and is empty only for an empty list
  - `sourceLabel` output contains the table name
- [X] T011 Implement `agent/readiness_agent/map_data.py` with `get_georgia_map_data(project: str, dataset: str = "evacuation_readiness") -> dict`, returning a dict that validates against `specs/001-georgia-shelter-map/contracts/map-data.schema.json`.
  - **Shelters query**: read `shelters` where `state = 'GA'`. Map BigQuery TRUE/FALSE/NULL to `"YES"`/`"NO"`/`"UNRECORDED"` in one helper `to_flag(v)`.
    - `is_medical`: `"UNRECORDED"` when `population_code` is NULL, otherwise YES or NO from `is_medical`.
    - `quality_flags`: `suspect_capacity` if `evacuation_capacity < 0 OR > 100000`; `location_disagrees` if `county_fips` is NULL or does not start with `"13"`.
    - `county_name`: `county_name`, falling back to `county_parish`.
  - **Tracts query**: read `vulnerability_tracts` where `geo_id LIKE '13%'`. Treat `-999` and negative values as NULL, then aggregate by `LEFT(geo_id,5)`:
    - `households_no_vehicle`: SUM, source "ACS 5-yr · vulnerability_tracts", kind "survey"
    - `share_65_plus`: `SUM(pop_65_plus)/SUM(total_pop)`, source "ACS 5-yr · vulnerability_tracts", kind "survey"
    - `share_disability`: population-weighted mean of `pct_disability` over tracts with values, source "ACS survey estimate via CDC SVI · vulnerability_tracts", coverage "N of M tracts"
  - **County records**: build one per county for all 159 FIPS, including counties with zero shelters.
    - `capacity_total` excludes suspect shelters, and `capacity_total_incl_suspect` includes them. Both have source "FEMA NSS registry · shelters", kind "registry".
    - `capacity_excluded` lists `{shelter_id, name}` for every suspect shelter in the county.
    - `wheelchair`, `generator`, `medical` and `in_surge` are all full `{yes, no, unrecorded}` counts.
  - **`notes`**: counted statewide statements, e.g. "{n} of {N} shelters have no wheelchair-access record", "{k} shelters have a suspect capacity and are excluded from totals", "Drive times are not included; distances are straight-line".
  - **Return**: `schema`, `state`, `generated_at` (UTC ISO). Cache the result in-process for 10 minutes.
- [X] T012 [P] Write `agent/tests/test_map_data.py` using injected fake row lists. Refactor T011 so the row-to-payload transform is a pure function `build_payload(shelter_rows, tract_rows, county_fips_list)`. Assert:
  - NULL becomes `UNRECORDED`, never `NO`
  - a 270,135 capacity is flagged `suspect_capacity`, excluded from `capacity_total`, included in `capacity_total_incl_suspect`, and listed by name in `capacity_excluded`
  - every `SourcedValue.source` contains its table name (`shelters` or `vulnerability_tracts`)
  - `-999` tracts are excluded and coverage is reported
  - a zero-shelter county is present with `shelter_count = 0`
  - the payload validates with `jsonschema` against `specs/001-georgia-shelter-map/contracts/map-data.schema.json`
- [X] T013 Implement `agent/readiness_agent/callbacks.py`:
  - `load_map_data_callback(callback_context) -> types.Content | None`
  - When the latest user message text is exactly `LOAD_MAP_DATA v1`, call `get_georgia_map_data(os.environ["GOOGLE_CLOUD_PROJECT"])` and return `types.Content(role="model", parts=[types.Part(text=json.dumps(payload))])`. This skips the LLM.
  - Otherwise return None.
  - On a BigQuery error, return Content with a JSON `{"schema":"map-data/v1","error":"<message>"}` so the frontend shows its failed state.
- [X] T014 Implement `agent/readiness_agent/agent.py`:
  - `root_agent = Agent(name="readiness_agent", model="gemini-3.6-flash", instruction=..., before_agent_callback=load_map_data_callback, tools=[])`
  - The instruction must say: treat any message part beginning `CONTEXT v1` as context (selected county, shelter, scenario), not a question; always distinguish recorded yes, recorded no and not recorded; include `shelter_id` / `county_fips` in tool results.
  - Add a header comment saying the readiness-agent feature owns the tools, the Maps grounding and the full instruction (plan dependencies D1, D2).
- [X] T015 [P] Write `agent/tests/test_callbacks.py`:
  - the exact command returns Content whose text parses as JSON with `schema == "map-data/v1"`, with `get_georgia_map_data` monkeypatched
  - `"load map data"` and any other text return None
  - a BigQuery exception returns the error JSON
- [X] T016 Implement `agent/server.py`:
  - `app = get_fast_api_app(agents_dir=<dir of agent/>, web=False, session_service_uri=None)` (in-memory sessions)
  - mount `StaticFiles(directory="../frontend/dist" or env FRONTEND_DIST, html=True)` at `/` **after** the ADK routes, so `/apps`, `/run` and `/run_sse` still resolve
  - expose `uvicorn` startup on `PORT` (default 8080)
- [X] T017 Implement `frontend/src/lib/agentClient.ts`:
  - `const APP = "readiness_agent"`; a per-tab `userId = crypto.randomUUID()`
  - `createSession(): Promise<string>`
  - `loadMapData(signal): Promise<MapData>`:
    - create a dedicated session and POST `/run` with `LOAD_MAP_DATA v1`
    - take the last event whose author is `readiness_agent`, then `JSON.parse(content.parts[0].text)`
    - reject on: status other than 200, JSON parse failure, `schema !== "map-data/v1"`, an `error` field, or a 20 s timeout (AbortController)
- [X] T018 Implement the store in `frontend/src/state/store.tsx`: `useReducer` plus React context.
  - **State**: `mapData: {status: "loading" | "ready" | "failed", data?, error?}`, `hoverFips`, `selectedFips`, `selectedShelterId`, `highlight: {shelterIds: Set<string>, countyFips: Set<string>}`, `scenario: HurricaneScenario | null`, `chat: ChatExchange[]`
  - **Selectors**: `countyByFips` and `shelterById` maps, built once when the data loads
- [X] T019 Build the app shell in `frontend/src/App.tsx` and `frontend/src/styles/app.css`:
  - three-column desktop layout: map (flex 1), side panel (360 px), chat (400 px)
  - on mount, call `loadMapData` and dispatch the result
  - a banner for the loading state, and for the failed state with a Retry button (FR-008b)
  - county outlines render regardless of data status
- [X] T020 [P] Create the test fixture `frontend/tests/mocks/mapData.fixture.json`, valid per the schema, with 4 counties and 8 shelters, including:
  - Jackson (13157) with "Commerce High School", capacity 270,135, `suspect_capacity`
  - a county with zero shelters
  - shelters with UNRECORDED, NO and YES wheelchair flags
  - one `location_disagrees` shelter
  - two `in_surge_slosh_area = YES` shelters in Glynn (13127) and Chatham (13051)
  Wire it into the `/run` handler in `frontend/tests/mocks/handlers.ts`.

**Checkpoint**:
- `curl` per [quickstart.md](quickstart.md) §1 returns about 1,792 shelters and 159 counties.
- The frontend shell shows outlines, then a ready state.

---

## Phase 3: User Story 1 - Explore Georgia's shelters by county (Priority: P1) 🎯 MVP

**Goal**: A hoverable Georgia county map with shelters plotted, a county summary showing
Yes / No / Not recorded counts and people figures, and shelter details.

**Independent Test**: Open the app with the chat and simulation unused. Hover over Cobb and
Chatham, and check the figures against BigQuery. Jackson shows the Commerce flag and two totals.

- [X] T021 [P] [US1] Implement `frontend/src/components/map/CountyLayer.tsx`:
  - SVG with `geoMercator().fitSize([w,h], gaFeatureCollection)` from `ga-counties.topo.json` via `topojson-client.feature`
  - one `<path>` per county
  - `onPointerEnter` / `onPointerLeave` dispatch hover, and only the hovered county gets the `.county--hover` class
  - `tabIndex=0` with `onFocus` / `onBlur` mirroring hover
  - classes for `highlight.countyFips` and `selectedFips`
  - export the `projection` through context for the other layers
- [X] T022 [P] [US1] Implement `frontend/src/components/map/ShelterLayer.tsx`:
  - one `<circle>` per shelter at `projection([lon, lat])`
  - fill by usage (EVAC / POST / not recorded)
  - a ring stroke when `in_surge_slosh_area === "YES"`
  - a small warning glyph for any `quality_flags`
  - `.shelter--highlight` from the store
  - click dispatches `selectedShelterId`
  - render nothing until `mapData.status === "ready"`
- [X] T023 [US1] Implement `frontend/src/components/summary/CountySummary.tsx` for the hovered county, falling back to the selected one (FR-003, FR-003a, FR-007):
  - name and shelter count; "No shelters on file" when 0
  - `capacity_total`, with `exclusionNote(capacity_excluded)` directly beside it and the "incl. suspect" total when `capacity_excluded` is non-empty
  - a `flagCountsLine` row for each of wheelchair, generator, medical and surge zone
  - the three people figures, each with `sourceLabel()`
  - an `aria-live="polite"` wrapper
  - every number shows its registry or survey kind badge
- [X] T024 [P] [US1] Implement `frontend/src/components/summary/ShelterDetails.tsx` (FR-004, FR-005, User Story 1 acceptance scenario 4):
  - name, address, capacity and post-impact capacity, usage, and the four flags via `flagLabel`
  - quality-flag explanations: "Capacity looks implausible; FEMA's value shown unedited" and "Coordinates disagree with recorded state/county"
  - the label "Registry record (FEMA National Shelter System)"
- [X] T025 [P] [US1] Implement `frontend/src/components/map/Legend.tsx` (FR-009), explaining:
  - the county hover and highlight colors
  - shelter fill by usage, the surge ring and the warning glyph
  - Yes / No / Not recorded styles
  - the registry / survey / live / simulation badges
- [X] T026 [US1] Wire up US1 in `frontend/src/App.tsx`:
  - `CountyLayer` and `ShelterLayer` inside one `<svg>`
  - side panel: `ShelterDetails` when a shelter is selected, otherwise `CountySummary`
  - `Legend` under the map
  - clicking a county sets `selectedFips`
  - hover updates do no network work (FR-008a)
- [X] T027 [P] [US1] Write `frontend/tests/component/CountySummary.test.tsx` with the fixture:
  - Jackson shows the total excluding Commerce plus the incl.-suspect line
  - unrecorded wheelchair count shown separately and not added to No (SC-003)
  - the zero-shelter county shows "No shelters on file"
  - the disability figure shows "ACS survey estimate via CDC SVI"

**Checkpoint**: US1 works on its own. This is the MVP demo of "what's on file for my county and how
much is blank".

---

## Phase 4: User Story 2 - Ask the agent about a county or shelter (Priority: P1)

**Goal**: A chat panel that streams agent answers, labels live vs registry content, renders Google
Maps sources under supported text, and highlights referenced shelters and counties on the map.

**Independent Test**: Ask the Cobb County example and two accessibility questions (agent from the
readiness feature, or the MSW mock). Check that:
- the unrecorded counts are stated
- the sources sit directly under the live segments
- the referenced items highlight

- [X] T028 [P] [US2] Implement `frontend/src/lib/grounding.ts`:
  - `segmentAnswer(text, groundingMetadata?)`: returns `AnswerSegment[]`. Split `text` at each `groundingSupports[].segment` (with `startIndex ?? 0` and `endIndex`) into `kind: "live"` segments carrying `sources = groundingChunkIndices.map(i => chunks[i].maps)` as `{title, uri, placeId}`. The rest is `kind: "registry"`.
  - `collectReferences(obj)`: walks any JSON recursively and collects the string values of keys `shelter_id` and `county_fips`.
- [X] T029 [P] [US2] Write `frontend/tests/unit/grounding.test.ts`:
  - a null `startIndex` is treated as 0
  - two supports produce live / registry / live ordering
  - sources map to the right segment
  - `collectReferences` finds nested IDs in arrays
- [X] T030 [US2] Add `streamChat({question, context, onEvent, signal})` to `frontend/src/lib/agentClient.ts`:
  - create the chat session lazily, once per tab
  - POST `/run_sse` with `streaming: true` and two parts: the question text, and `"CONTEXT v1 " + JSON.stringify(context)` (contracts §3)
  - read `response.body` with `getReader()` and `TextDecoder`, split on blank lines, and parse each `data:` line as an Event
  - raise on `errorCode`, HTTP errors, or a 90 s timeout
- [X] T031 [US2] Implement `frontend/src/components/chat/ChatPanel.tsx`:
  - text input with Send (Enter submits)
  - history list of `ChatExchange`
  - status chips for pending, streaming and failed, with Retry re-sending the same question and context
  - builds context from the store: `county_fips = selectedFips ?? hoverFips`, `shelter_id`, `scenario` (null until US3)
  - on each event: append partial text, collect `functionResponse` references into the exchange, keep the final `groundingMetadata`
  - the map stays interactive during streaming
- [X] T032 [US2] Implement `frontend/src/components/chat/AnswerView.tsx` and `frontend/src/components/chat/SourceList.tsx`:
  - render `segmentAnswer()` output
  - live segments get a "Live check · just now" badge and a distinct style
  - registry segments get no badge
  - `SourceList` sits **immediately after** each live segment: a `<span translate="no">Google Maps</span>` label, then each source title as a link to `uri` (`target=_blank rel=noopener`)
  - referenced shelters and counties render as chips under the answer, and clicking one selects it on the map
- [X] T033 [US2] On exchange completion in `frontend/src/state/store.tsx`, dispatch `highlight` with the exchange's `referenced_shelter_ids` and `referenced_county_fips`, and clear it on the next question. Keep `placeId`s only in memory: a `liveChecks: Map<shelter_id, {placeIds, checked_at}>` holds no titles, URIs or text beyond the render (FR-022).
- [X] T034 [P] [US2] Write `frontend/tests/component/AnswerView.test.tsx`:
  - sources render as the next sibling after the live segment
  - the element containing "Google Maps" has `translate="no"`
  - registry text has no live badge
  - a failed exchange shows Retry

**Checkpoint**: US1 and US2 both work. The chat answers county questions and highlights the map.

---

## Phase 5: User Story 3 - Draw a simulated hurricane and see which shelters it puts at risk (Priority: P2)

**Goal**: The user draws a track and picks Category 1–5. The app shows the illustrative impact band,
affected counties and shelters, and the ranked receiving list (within the cutoff, capacity first)
with an adjustable cutoff. The scenario is sent to the agent with each chat message.

**Independent Test**: Draw a Category 3 track across Glynn and inland. Check that the affected
summary and receiving list update when the category, cutoff or track changes, and that no receiving
shelter lies inside the band.

- [X] T035 [P] [US3] Implement `frontend/src/lib/simulation.ts` with pure functions (research R5, R6):
  - `HALF_WIDTH_KM = {1:30, 2:45, 3:60, 4:80, 5:100}`
  - `thinTrack(lonlats, minKm=5)` returns a `LineString`, or a `Point` if there is one point or the track is under 1 km
  - `computeBand(track, category)` returns `turf.buffer(track, km, {units:"kilometers"})`
  - `affected(band, shelters, countyFeatures)` returns `{countyFips[], shelterIds[]}`, counting only GA counties and shelters
  - `countyCentroids(countyFeatures)` returns `Map<fips, [lon,lat]>`, memoized
  - `receivingList(shelters, affectedSet, affectedCountyFips, centroids, cutoffKm)`:
    1. exclude affected shelters
    2. compute distance to the nearest affected-county centroid
    3. keep `d <= cutoffKm`
    4. sort by capacity desc (suspect capacity treated as 0), then by `d` asc
    5. attach a `reason`, e.g. "Largest recorded capacity within 80 km; wheelchair access not recorded"
  - `listFlagCounts(shelters, key): FlagCounts`, used for the affected set and the receiving list
  - `capacitySummary(shelters)`: returns `{total, totalInclSuspect, excluded: {shelter_id, name}[]}` for any set of shelters
- [X] T036 [P] [US3] Write `frontend/tests/unit/simulation.test.ts`:
  - SC-005b: no affected shelter is ever in `receivingList`, across categories 1–5 and several tracks
  - sort order is capacity desc, ties by distance
  - the suspect Commerce shelter never ranks first
  - the cutoff filter works at 25, 80 and 200
  - a click produces a Point band
  - an empty-result case returns `[]`
  - a band crossing into Florida counts only GA
  - Cat 5 band width is greater than Cat 1
- [X] T037 [US3] Implement `frontend/src/components/map/TrackDrawer.tsx`:
  - a "Draw hurricane track" toggle
  - while on, pointer down / move / up on the SVG collects `projection.invert` points and shows a live polyline
  - on pointer-up, dispatch `scenario.track = thinTrack(points)` and recompute
  - render the band polygon (semi-transparent) and the track with a storm glyph at the end
  - the track can be redrawn by toggling again
  - a "Reset" button clears the scenario (FR-020)
- [X] T038 [P] [US3] Implement `frontend/src/components/scenario/CategoryPicker.tsx` (segmented control 1–5, default 3) and `frontend/src/components/scenario/ReachSlider.tsx` (range 25–200, step 5, default 80, value shown as "Within reach: 80 km (straight-line)"). Both dispatch recompute.
- [X] T039 [US3] Add a scenario reducer case in `frontend/src/state/store.tsx`. On track, category or cutoff change, compute `band`, `affected_*`, `receiving` with `simulation.ts`, synchronously after the drag ends, not on pointer move.
- [X] T040 [US3] Implement `frontend/src/components/scenario/AffectedSummary.tsx` (FR-018, FR-019):
  - a header badge: "Illustrative scenario — not a forecast"
  - affected county names
  - shelter count, and recorded capacity from `capacitySummary` with `exclusionNote` beside it
  - `flagCountsLine` for wheelchair, generator and surge zone
  - the shelters recorded as YES for surge zone listed by name
- [X] T041 [US3] Implement `frontend/src/components/scenario/ReceivingList.tsx` (FR-018a–d):
  - table with columns: rank, name and county, capacity, distance "(straight-line)", wheelchair, generator, surge flag, reason
  - a header line: "{n} shelters within {cutoff} km outside the affected area · wheelchair access: " + `flagCountsLine(listFlagCounts(list, "wheelchair_accessible"))`
  - if the list shows any capacity total, it uses `capacitySummary` and `exclusionNote`. Suspect rows keep their warning glyph and the reason "Capacity looks implausible; ranked as 0"
  - empty state: "No shelters within {cutoff} km outside the affected area — try raising the reach cutoff"
  - clicking a row selects the shelter
- [X] T042 [US3] Style affected vs receiving in `frontend/src/components/map/ShelterLayer.tsx` and `CountyLayer.tsx`:
  - affected shelters red-outlined; surge plus affected gets a strong marker
  - receiving shelters green-outlined
  - affected counties tinted
  - side panel shows `AffectedSummary` and `ReceivingList` when a scenario is active (wire in `frontend/src/App.tsx`)
- [X] T043 [US3] In `frontend/src/components/chat/ChatPanel.tsx`, include `scenario` in the `CONTEXT v1` payload (contracts §3) as `{track, category, cutoff_km, affected_county_fips, affected_shelter_ids, receiving_top: first 20 shelter_ids}`.
- [X] T044 [P] [US3] Write `frontend/tests/component/ReceivingList.test.tsx` with the fixture plus a synthetic scenario:
  - the header shows the cutoff and all three wheelchair counts (yes · no · not recorded)
  - a suspect shelter row shows its glyph and reason
  - "Not recorded" is shown, not "No"
  - the empty state text appears for an empty list

**Checkpoint**: US1–US3 work. The core demo path (SC-007) can be run with the mocked agent.

---

## Phase 6: User Story 4 - Readiness gaps and "what we could not tell you" (Priority: P3)

**Goal**: Show the agent's ranked "verify before the season" lists clearly, and always show a counted
"What we could not tell you".

**Independent Test**: Ask "What should I verify before September in Chatham County?" Check that you
get a ranked list with reasons, that the shelters highlight, and that the counted "could not tell
you" section is visible.

- [X] T045 [US4] In `frontend/src/components/chat/AnswerView.tsx`, render each segment's text with `react-markdown` and `remark-gfm`, so ranked lists and tables display. Document in a code comment that the live/registry split is applied per segment, so a markdown table split across segments renders as separate blocks. This is an accepted limitation.
- [X] T046 [US4] Implement `frontend/src/components/summary/CouldNotTell.tsx`, a "What we could not tell you" panel, always visible at the bottom of the side panel, showing:
  - `mapData.notes` (statewide, counted)
  - for the hovered or selected county: "{u} of {n} shelters never assessed for wheelchair access", "{g} generator status not recorded"
  - when a scenario is active: the receiving list's unrecorded count and "Distances are straight-line; drive times not included"
- [X] T047 [US4] Add suggested-question chips to `frontend/src/components/chat/ChatPanel.tsx`, built from the selection:
  - "How many shelters are in {county} and what is their capacity?"
  - "Which shelters in {county} are in the surge zone?"
  - "What should I verify before September in {county}?"
  - when a scenario is active: "Which of these receiving shelters can actually take a wheelchair?"

**Checkpoint**: All four stories work on their own.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T048 Write the repo-root `Dockerfile` (moved from `agent/` so `gcloud run deploy --source .` finds it):
  - stage 1 `node:20` runs `npm ci && npm run build` in `frontend/`
  - stage 2 `python:3.12-slim` installs `agent/requirements.txt`, copies `agent/` and `frontend/dist`
  - sets `FRONTEND_DIST`, `CMD uvicorn server:app --host 0.0.0.0 --port $PORT`
  - add a root `.dockerignore` excluding `node_modules`, `.venv` and `notebooks`
- [ ] T049 Deploy per [quickstart.md](quickstart.md) §4: Cloud Run with `--iap --no-allow-unauthenticated --min-instances 1`, and allow-list the team plus invited judges. Then check:
  - an account that isn't allow-listed gets the IAP denial page, and Cloud Run logs show no request (FR-023)
  - adding an account works without a redeploy (FR-024)
  Record the service URL and checks in `specs/001-georgia-shelter-map/research.md`.
- [X] T050 [P] Write the Playwright smoke test `frontend/tests/e2e/smoke.spec.ts` with MSW, following SC-007:
  1. load the page and see county outlines, then shelters
  2. hover a fixture county and see the summary
  3. draw a track across Glynn and set Category 3
  4. the receiving list appears with "straight-line" and the 80 km cutoff
  5. send a chat question (mocked SSE with one grounded segment)
  6. "Google Maps" sources appear under the live segment, and a referenced shelter is highlighted
- [ ] T051 Measure performance against the deployed service, and record the results in `specs/001-georgia-shelter-map/research.md`:
  - SC-004: hover summary in under 0.5 s (DevTools performance)
  - SC-004a: map data within 20 s of a cold page load
  - SC-005: scenario update within 2 s
  - SC-005a: cutoff update within 1 s
- [ ] T052 Run the equity audit (Constitution V, quickstart §5 step 7):
  1. For a Category 3 Glynn scenario, export the receiving `shelter_id`s.
  2. In BigQuery, join each to the nearest `vulnerability_tracts` centroid by `ST_DISTANCE`.
  3. Compare `pct_no_vehicle`, `pct_age_65_plus` and `pct_disability` with the GA statewide distribution.
  4. Record the numbers, including "no difference", in `specs/001-georgia-shelter-map/research.md`.
- [ ] T053 Grounding and attribution check (Constitution II), with the readiness-agent owner:
  - confirm that at least one real answer shows grounding changing or annotating a result (dependency D1)
  - confirm tool results carry `shelter_id` (D2)
  - screenshot a compliant source rendering, with "Google Maps" unmodified, `translate="no"`, and sources immediately after the content
  Record the results in `specs/001-georgia-shelter-map/research.md`.
- [ ] T054 Re-run the Constitution Check in `specs/001-georgia-shelter-map/plan.md` against the built system. Update each gate's status with evidence (test names, research.md sections). Run the full quickstart §5 walk-through.
- [X] T055 [P] Update the Commands section of `CLAUDE.md` if any script names changed, and add `frontend/` and `agent/` run instructions to `agent/README.md` (keep the existing requirements text).

---

# Connecting the frontend to the readiness agent (added 2026-10-27)

**Context**: PRs #3–#6 merged the team's readiness agent into `agent/readiness_agent/`. It has:
- tools: `find_vulnerable_tracts`, `assess_shelter_accessibility`, `find_power_dependent_counties`, `build_readiness_brief`, the BigQuery MCP (`execute_sql_readonly`) and `google_maps_grounding`
- data in `<project>.evac_prod.*_clean` (see `agent/readiness_agent/evacuation_tools.py`)

The transport is already wired:
- the same-origin server is `agent/server.py`
- the Vite proxy sends the agent's `origin` header (`frontend/vite.config.ts`)

What remains is making the agent's output match what the frontend reads ([contracts/agent-interface.md](contracts/agent-interface.md) §3).

**Gaps found** (each is fixed by a task below):
1. Tool results carry no `shelter_id`, and the county tool uses `fips_code`, so answers cannot highlight the map (dependency D2).
2. Tools filter by county name only, but the frontend's `CONTEXT v1` sends `county_fips`. No tool can look up the `shelter_id`s in `receiving_top` or `shelter_id`.
3. Tool flags are raw booleans, so `NULL` reaches the model unlabeled. `assess_shelter_accessibility` sorts by raw capacity, so the Commerce rows (270,135 and 225,112) rank first (Constitution I, VI).
4. ADK's `/run_sse` reports a mid-stream failure as `data: {"error": "...", "error_details": {...}}` (verified in `google/adk/cli/api_server.py`, ADK 2.13). `streamChat` only checks `errorCode` and `errorMessage`, so a failed turn shows as done.
5. Source labels still name `shelters` and `vulnerability_tracts`, but the tables are now `*_clean` (Constitution III).
6. There is no way for the agent to report a live-check result (renamed or closed), so analysis finding H2 is unbuilt.

**Credentials**: T061, T062, T069 and T072 need Application Default Credentials for the team's GCP project (`gcloud auth application-default login`). Everything else runs offline against fakes.

## Phase 8: Integration Foundation (Blocking Prerequisites)

**Purpose**: Shared fixes that every story's real-agent path depends on.

- [X] T056 Handle ADK's SSE error event in `frontend/src/lib/agentClient.ts`:
  - add `error?: string` and `error_details?: { error_type?: string; error_message?: string }` to `AgentEvent`
  - in `streamChat`, throw `new Error(e.error)` when `e.error` is present, before any `errorCode`/`errorMessage` check
  - add `frontend/tests/unit/agentClient.test.ts`:
    - `parseSseChunk` parses `data: {"error":"ValueError: boom","error_details":{}}`
    - `streamChat` rejects with `"ValueError: boom"` when `fetch` is stubbed (`vi.stubGlobal`) to return a `ReadableStream` with one text event and then that error event
- [X] T057 [P] In `agent/readiness_agent/map_data.py`, rename `_shelter(row)` to the public `shelter_record(row)` and keep `_shelter = shelter_record` for compatibility. It stays the single place a shelter row becomes `{shelter_id, name, address, county_fips, county_name, lat, lon, evacuation_capacity, post_impact_capacity, usage, the four flags via to_flag, quality_flags}`. Also export the constants `SUSPECT_LOW` and `SUSPECT_HIGH`.
- [X] T058 [P] Update source labels in `agent/readiness_agent/map_data.py` to the real tables:
  - `SRC_SHELTERS = "FEMA NSS registry · shelters_clean"`
  - `SRC_ACS = "ACS 5-yr · vulnerability_tracts_clean"`
  - `SRC_SVI = "ACS survey estimate via CDC SVI · vulnerability_tracts_clean"`
  - in `agent/tests/test_map_data.py::test_every_source_names_its_table`, assert `"· shelters_clean"` or `"· vulnerability_tracts_clean"`
- [X] T059 Move the frontend fixture generator into `agent/scripts/make_frontend_fixture.py`:
  - copy the generator used in Phase 2 T020: 12 shelters (J1–J3, G1–G2, C1–C2, B1, M1, W1, Y1, X1), 8 counties, and tracts including a `-999` row
  - it calls `build_payload`, validates against `specs/001-georgia-shelter-map/contracts/map-data.schema.json`, and writes `frontend/tests/mocks/mapData.fixture.json`
  - run it so the fixture picks up the T058 labels, then run `cd frontend && npx vitest run` and update any assertion that hard-codes `· vulnerability_tracts`
- [X] T060 [P] Write `agent/scripts/capture_sse.py` (stdlib `urllib` only):
  - args: `--base http://localhost:8000 --question "..." --context '{"county_fips":...}' --out frontend/tests/mocks/recorded/<name>.sse`
  - creates a session at `/apps/readiness_agent/users/capture/sessions`, then POSTs `/run_sse` with the two-part message from contracts §3 (question, then `CONTEXT v1 <json>`) and writes the raw response body to `--out`
  - add a header comment saying captured files must not contain personal data and that Maps content inside them is test-only, never shipped (FR-022)

**Checkpoint**: `cd agent && .venv/bin/python -m pytest` and `cd frontend && npx vitest run` both pass.

---

## Phase 9: User Story 1 - Map loads from the real agent (Priority: P1)

**Goal**: The session-start `LOAD_MAP_DATA v1` call returns real Georgia data from `evac_prod`.

**Independent Test**:
1. With ADC set, run `cd agent && GOOGLE_CLOUD_PROJECT=<team project> EVAC_DATASET=evac_prod .venv/bin/uvicorn server:app --port 8000`.
2. In another shell, run `cd frontend && npm run dev`, then open http://localhost:5173.
3. Outlines render at once. Markers and summaries appear within 20 s (SC-004a).

- [ ] T061 [US1] **Schema check first (gates T063, T066):** run `bq show --schema --format=prettyjson <project>:evac_prod.shelters_clean` and the same for `vulnerability_tracts_clean`, and record both column lists in research.md under "## Agent integration (evac_prod)". Every name in `SHELTER_COLUMNS` and the tract columns must exist; fix any mismatch with an alias in `agent/readiness_agent/map_data.py`. Then run the quickstart §1 `curl` smoke test against the local server. The expected shelter count comes from `bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM \`<project>.evac_prod.shelters_clean\` WHERE state="GA" AND latitude IS NOT NULL AND longitude IS NOT NULL'`.
  - Confirm `schema == "map-data/v1"`, 159 counties, and a `shelters` length equal to that count.
  - If BigQuery reports a missing column (`county_fips`, `county_name`, `county_parish`, `usage`, `population_code`, `is_medical` in `shelters_clean`; `total_pop`, `pop_65_plus`, `pct_disability`, `households_no_vehicle` in `vulnerability_tracts_clean`), alias the real column in `SHELTERS_SQL` / `TRACTS_SQL` in `agent/readiness_agent/map_data.py`.
  - Record the column mapping and the load time under "## Agent integration (evac_prod)" in `specs/001-georgia-shelter-map/research.md`.
- [ ] T062 [US1] Write `agent/scripts/check_county_totals.py` (SC-002, analysis M1):
  - call `get_georgia_map_data(project, "evac_prod")`
  - run `SELECT county_fips, COUNT(*) n, SUM(IF(evacuation_capacity BETWEEN 0 AND 100000, evacuation_capacity, 0)) cap, COUNTIF(wheelchair_accessible IS NULL) wc_unrec FROM \`<project>.evac_prod.shelters_clean\` WHERE state='GA' GROUP BY 1`
  - print every county whose `shelter_count`, `capacity_total.value` or `wheelchair.unrecorded` differs, and exit non-zero if any do
  - run it and record the result in research.md

**Checkpoint**: The map shows real Georgia shelters through the agent.

---

## Phase 10: User Story 2 - Chat with the real agent (Priority: P1)

**Goal**: Agent answers use the screen's context, return `shelter_id`/`county_fips` so the map highlights, keep Yes / No / Not recorded, and carry grounding metadata the UI renders.

**Independent Test**: With the local server and `npm run dev`, select Cobb County and ask the three US2 questions from spec.md. Check that:
- the counts state "not recorded"
- referenced shelters highlight
- grounded sentences show Google Maps sources directly beneath

- [ ] T063 [US2] Rework `assess_shelter_accessibility` in `agent/readiness_agent/evacuation_tools.py`: *(Code and offline tests done 2026-10-27; awaiting T061 schema check.)*
  - add the parameter `county_fips: str | None = None` (filter `county_fips = @county_fips`), and default `state` to `"GA"`
  - select the shelter columns from one shared constant rather than an inline list. In `agent/readiness_agent/map_data.py`, define `SHELTER_COLUMNS = ("shelter_id", "shelter_name", "address_1", "city", "zip", "county_fips", "county_name", "county_parish", "latitude", "longitude", "evacuation_capacity", "post_impact_capacity", "usage", "wheelchair_accessible", "generator_onsite", "is_medical", "population_code", "in_surge_slosh_area")`. Build `SHELTERS_SQL` from it, import it here, and drop the `geo` GEOGRAPHY column. One list then serves the map load and both shelter tools, and T061 verifies it against the real table.
  - `shelter_record` already reads every column except `shelter_id`, `latitude` and `longitude` with `.get`. Keep it that way, so a column aliased to `NULL` degrades to "Not recorded" rather than raising.
  - order by `wheelchair_accessible IS NULL DESC, IF(evacuation_capacity < 0 OR evacuation_capacity > 100000, 0, evacuation_capacity) DESC, shelter_name`, so suspect capacities never rank first (Constitution VI)
  - return `{"shelters": [shelter_record(r) for r in rows], "wheelchair": {yes, no, unrecorded}, "source": SOURCES["shelters"]}`, counting via `to_flag`
  - define a `SOURCES` dict at the top of the module, one entry per table, each naming the dataset **and** the table (Constitution III):
    - `"shelters": "FEMA NSS registry · shelters_clean"`
    - `"tracts": "ACS 5-yr and CDC SVI · vulnerability_tracts_clean"`
    - `"power": "HHS emPOWER · power_dependent_counties_clean"`
    Every tool result carries the matching `source`.
  - update the docstring to say flags are YES / NO / UNRECORDED and UNRECORDED means nobody assessed it
- [X] T064 [P] [US2] Rework `find_power_dependent_counties` in `agent/readiness_agent/evacuation_tools.py`:
  - select `fips_code AS county_fips`
  - add the parameter `county_fips: str | None = None` (filter `fips_code = @county_fips`)
  - return `{"counties": rows, "source": SOURCES["power"]}` instead of a bare list
  - state in the docstring that emPOWER is county-level and must never be attributed to a tract or block (Constitution III)
- [X] T065 [P] [US2] Rework `find_vulnerable_tracts` in `agent/readiness_agent/evacuation_tools.py`:
  - add the parameter `county_fips: str | None = None` (filter `v.county_fips = @county_fips`)
  - drop the `geo` column
  - note in the docstring that `pct_disability` is an ACS survey estimate via CDC SVI and that `-999` means missing
  - map `-999` to `None` in Python before returning
  - return `{"tracts": rows, "source": SOURCES["tracts"]}` instead of a bare list
- [ ] T066 [US2] Add the tool `get_shelters(shelter_ids: list[str]) -> dict` to `agent/readiness_agent/evacuation_tools.py`: *(Code and offline tests done 2026-10-27; awaiting T061 schema check.)*
  - raise `ValueError` if more than 25 IDs are passed
  - query with `bigquery.ArrayQueryParameter("ids", "STRING", shelter_ids)` and `WHERE shelter_id IN UNNEST(@ids)`, selecting `SHELTER_COLUMNS` (the same shared list as T063)
  - return `{"shelters": [shelter_record(r) ...], "source": SOURCES["shelters"]}` in the order of `shelter_ids`
  - register it in `tools=[...]` in `agent/readiness_agent/agent.py`
- [X] T067 [US2] Extend `INSTRUCTION` in `agent/readiness_agent/agent.py` with these rules:
  - when `CONTEXT v1` has `county_fips`, pass it as `county_fips` to the readiness tools rather than guessing a county name
  - when it has `shelter_id`, call `get_shelters([shelter_id])`
  - to judge whether a specific shelter is accessible or still exists, ground that one building with Google Maps using its name and address, never as an area question
  - report counts as "N yes · N no · N not recorded"
  - name the source table for every figure you give, using the tool result's `source` field (e.g. "1,950 spaces (FEMA NSS registry · shelters_clean)"), and say whether it is a registry record, a survey estimate, simulated or a live check (Constitution III)
  - never include a shelter flagged `suspect_capacity` in a capacity total without saying so
- [X] T068 [P] [US2] Write `agent/tests/test_evacuation_tools.py`. Monkeypatch `evacuation_tools._run_query` to capture `(sql, params)` and return fake rows (no BigQuery). Assert:
  - `assess_shelter_accessibility(county_fips="13157")` passes a `county_fips` parameter and returns `shelter_id` and `county_fips` on every shelter
  - a `None` wheelchair value becomes `"UNRECORDED"` and the counts include it
  - a 270,135 capacity carries `suspect_capacity`
  - `find_power_dependent_counties` rows have a `county_fips` key
  - `get_shelters` rejects 26 IDs and preserves input order
  - `find_vulnerable_tracts` maps `-999` to `None`
  - every tool result has a `source` containing its table name (`shelters_clean`, `vulnerability_tracts_clean` or `power_dependent_counties_clean`)
- [ ] T069 [US2] Run real-agent chat verification, with ADC set:
  - with the local server and `npm run dev`, ask the three US2 questions for Cobb (13067) and Chatham (13051)
  - capture each with `agent/scripts/capture_sse.py` into `frontend/tests/mocks/recorded/us2-<n>.sse`
  - confirm: (a) answer text appears once, not duplicated by partial and final events; (b) `functionResponse` payloads contain `shelter_id`; (c) at least one final event has `groundingMetadata.groundingChunks[].maps`
  - if (a) fails, fix the text-folding rule in `frontend/src/components/chat/ChatPanel.tsx`
  - record the observed event sequence in research.md R8
- [X] T070 [P] [US2] Extract the per-event logic from `ChatPanel.run` into a pure `foldEvent(acc, event)` in `frontend/src/lib/chatFold.ts`. It accumulates text (partial adds a delta, a non-partial event replaces the text), references via `collectReferences`, and the latest `groundingMetadata`. `ChatPanel` must use it. Add `frontend/tests/unit/chatFold.test.ts`, which replays `tests/mocks/handlers.ts` `chatEvents` plus every `tests/mocks/recorded/*.sse` file (if present, via `parseSseChunk`) and asserts the final text is not duplicated and references are collected.

**Checkpoint**: US2's independent test passes against the real agent.

---

## Phase 11: User Story 3 - The scenario reaches the agent (Priority: P2)

**Goal**: Questions about a drawn hurricane use the screen's affected set and receiving list, not a re-ranking.

**Independent Test**: Draw a Category 3 track across Glynn, then ask "Which of these receiving shelters can actually take a wheelchair?". The answer should:
- call `get_shelters` with the screen's `receiving_top`
- ground shelters one building at a time
- separate recorded yes, recorded no and not assessed

- [X] T071 [US3] Add scenario rules to `INSTRUCTION` in `agent/readiness_agent/agent.py`:
  - `CONTEXT v1.scenario` holds `affected_county_fips`, `affected_shelter_ids` and `receiving_top`, already ranked by the screen's documented rule (within the reach cutoff, capacity first)
  - for questions about receiving or affected shelters, call `get_shelters` with those IDs (at most 25) and keep the screen's order. Don't re-rank.
  - say that the scenario is illustrative and that distances are straight-line
- [ ] T072 [US3] Verify end to end with ADC: draw the Glynn Category 3 track in `npm run dev`, ask the receiving-shelter wheelchair question, and capture it to `frontend/tests/mocks/recorded/us3-receiving.sse` with `agent/scripts/capture_sse.py`. Confirm the answer's referenced shelters are a subset of `receiving_top`, and record the result in research.md.

**Checkpoint**: Scenario questions are answered from the screen's own lists.

---

## Phase 12: User Story 4 - Readiness brief and live-check discrepancies (Priority: P3)

**Goal**: The brief is counted and FIPS-aware. A shelter Google Maps reports as renamed or closed is marked on the map (analysis H2).

**Independent Test**:
- Ask "What should I verify before September in Chatham County?" and get a ranked list with reasons and a counted "What we could not tell you".
- After the agent grounds a shelter Maps reports as renamed, a discrepancy marker appears on that shelter.

- [X] T073 [US4] Add the tool `record_live_check(shelter_id: str, status: str, place_id: str | None = None) -> dict` to `agent/readiness_agent/evacuation_tools.py`:
  - `status` must be one of `exists`, `renamed`, `closed`, `unknown`; raise `ValueError` otherwise
  - return `{"live_check": {"shelter_id", "status", "place_id", "checked_at": UTC ISO}}`
  - store nothing (FR-022)
  - register it in `agent/readiness_agent/agent.py`, and add to `INSTRUCTION`: after grounding a specific shelter, call `record_live_check` with what Maps showed, and say so in the answer
- [X] T074 [US4] Rework `build_readiness_brief` in `agent/readiness_agent/evacuation_tools.py`:
  - accept `county_fips: str | None = None` alongside `county`, passing it to the three tools
  - adapt to the new dict results from T063–T065: `vulnerable_tracts` takes `["tracts"]`, `shelters_to_verify` takes `["shelters"]`, `medical_dependency` takes `["counties"]`. Add `"sources"`, mapping each section to its `source` string
  - add `"could_not_tell"` with:
    - `wheelchair_unrecorded`: count among `shelters_to_verify`
    - `generator_unrecorded`: count among `shelters_to_verify`
    - `notes`: "Distances are straight-line", "emPOWER is county-level", "Shelter open status during a storm is not known"
  - instruct the agent (in `INSTRUCTION`) to end every brief with a counted "What we could not tell you" section
- [X] T075 [US4] Document `live_check` in `specs/001-georgia-shelter-map/contracts/agent-interface.md` §3. A `functionResponse.response.live_check` holds `{shelter_id, status, place_id, checked_at}`, and the frontend keeps only `status`, `place_id` and the time. In `specs/001-georgia-shelter-map/data-model.md`, change LiveCheck to say it is populated from `record_live_check` tool results.
- [X] T076 [US4] Add `collectLiveChecks(obj): { shelter_id: string; status: "exists" | "renamed" | "closed" | "unknown"; place_id?: string }[]` to `frontend/src/lib/grounding.ts`, walking `functionResponse` payloads for `live_check` objects. Then wire it up:
  - in `frontend/src/state/store.tsx`, extend `liveChecks` entries to `{ status, placeIds, checked_at }` and change the `liveCheck` action to carry `status`
  - in `frontend/src/components/chat/ChatPanel.tsx` (or `chatFold.ts` from T070), dispatch `liveCheck` for each one
- [X] T077 [US4] Show discrepancies:
  - `frontend/src/components/map/ShelterLayer.tsx`: draw a `?` glyph (class `shelter-discrepancy`) beside shelters whose live check is `renamed` or `closed`. The shelter stays on the map, because the registry record is not edited (FR-008).
  - `frontend/src/components/summary/ShelterDetails.tsx`: add the line "Live check: renamed / closed per <span translate="no">Google Maps</span> at HH:MM — registry record shown unedited"
  - add a legend entry in `frontend/src/components/map/Legend.tsx` and the style in `frontend/src/styles/app.css`
- [X] T078 [P] [US4] Write the tests:
  - `frontend/tests/unit/grounding.test.ts`: `collectLiveChecks` finds nested `live_check` objects and ignores invalid statuses
  - `frontend/tests/component/ShelterDetails.test.tsx`: renders the discrepancy line for a `renamed` live check, using `StoreProvider` with an `initial` state
  - `agent/tests/test_evacuation_tools.py`: `record_live_check` rejects `"gone"`, and `build_readiness_brief` returns `could_not_tell` counts

**Checkpoint**: All four stories work against the real agent.

---

## Phase 13: Polish (integration)

- [X] T079 [P] Make the mock agent in `frontend/tests/mocks/handlers.ts` mirror the real one:
  - the `functionResponse` uses `name: "get_shelters"` with `{shelters: [shelter_record-shaped M1, W1]}`
  - add a second `functionResponse` for `record_live_check` (`M1`, `exists`)
  - keep the existing grounded answer
  - re-run `npx playwright test`
- [X] T080 [P] Update the docs for the real dataset and dev loop:
  - `specs/001-georgia-shelter-map/quickstart.md` §1–2: the env vars `GOOGLE_CLOUD_PROJECT`, `EVAC_DATASET=evac_prod`, `MODEL_NAME`; ADC login; `.venv/bin/uvicorn server:app --port 8000` together with `npm run dev`
  - `plan.md` Technical Context Storage: `evac_prod.*_clean`
  - `contracts/agent-interface.md`: list the tool names whose results the frontend reads
- [X] T081 Run the full verification and fix any failures:
  - `cd agent && .venv/bin/python -m pytest`
  - `cd frontend && npx tsc -b && npx eslint . && npx vitest run && npm run build && npx playwright test`
  - then do T053 (grounding check), which these phases unblock

---

# Collapsible details panel (added 2026-10-27)

**Context**: The middle column (`SidePanel` in `frontend/src/App.tsx`) currently shows at all times. It holds:
- `CountySummary` or `ShelterDetails`
- `AffectedSummary` and `ReceivingList` when a hurricane is drawn
- `CouldNotTell`

The user wants a cleaner screen. **Decision**: keep the panel and its content, but collapse it to a thin rail that is **hidden by default** and opens with one click. Content is unchanged, so FR-003, FR-003a, FR-004, FR-005, FR-007, FR-018 (a–d), FR-019 and Constitution VII stay met when the panel is open. Hovering, selecting a county, selecting a shelter or drawing a track does **not** open it automatically.

## Phase 14: User Story 1 - Details panel collapsed by default (Priority: P1)

**Goal**: The map and chat take the full width. The details panel is a narrow rail until the user opens it.

**Independent Test**: Open the app (mock or real agent) and check:
- only the map and chat are visible, plus a narrow "Details" rail
- hovering a county or drawing a track does not open the panel
- clicking the rail opens it and shows the county summary or hurricane lists, and "Hide" collapses it again

- [X] T082 [US1] Add panel state in `frontend/src/state/store.tsx`:
  - add `detailsOpen: boolean` to `State`, defaulting to `false` in `initialState`
  - add the action `{ type: "setDetailsOpen"; open: boolean }` and its reducer case
  - no other action may change `detailsOpen`; hover, select and setTrack must not open it
- [X] T083 [US1] Move the `SidePanel` function out of `frontend/src/App.tsx` into a new `frontend/src/components/summary/DetailsPanel.tsx`.
  - **Closed** (`state.detailsOpen === false`): render a `<button className="details-rail">` with `aria-expanded="false"`, `aria-controls="details-panel"` and accessible name "Show details". Its visible label is the vertical text "Details ▸". When `state.selectedShelterId`, `state.selectedFips` or an active scenario (`useScenario()`) exists, add a small dot inside it (`<span className="details-rail__dot" aria-hidden="true" />`) and append " (new details available)" to the accessible name.
  - **Open**: render `<aside id="details-panel" className="side" aria-label="Details">`. It starts with a header row containing a "◂ Hide" button (`aria-expanded="true"`, `aria-controls="details-panel"`) that dispatches `setDetailsOpen(false)`, followed by the existing content unchanged: `ShelterDetails` or `CountySummary`, then `AffectedSummary` and `ReceivingList` when a scenario exists, then `CouldNotTell`.
  - In `App.tsx`, replace `<SidePanel />` with `<DetailsPanel />` and remove the now-unused imports.
- [X] T084 [P] [US1] Update the layout in `frontend/src/styles/app.css`:
  - change `.layout` `grid-template-columns` to `minmax(420px, 1fr) auto 400px`, so the middle column is only as wide as the rail or panel
  - give `.side` `width: 360px`
  - add `.details-rail`: `width: 32px`, full height, `writing-mode: vertical-rl`, border-left `var(--border)`, background `var(--panel)`, color `var(--muted)`, no other border, cursor pointer, hover background `var(--county)`, and a visible `:focus-visible` outline
  - add `.details-rail__dot`: an 8px circle in `var(--live)`
  - add a `.side__header` flex row with space-between
- [X] T085 [P] [US1] Write `frontend/tests/component/DetailsPanel.test.tsx`. Render `DetailsPanel` inside `StoreProvider` and `ScenarioProvider` with `initial={{ mapData: { status: "ready", data: fixture } }}` (fixture `tests/mocks/mapData.fixture.json`). Assert:
  - (a) by default the button "Show details" has `aria-expanded="false"`, and `screen.queryByTestId("county-summary")` and `queryByTestId("could-not-tell")` are null
  - (b) clicking it shows `could-not-tell` and the hint text, and the "◂ Hide" button has `aria-expanded="true"`
  - (c) with `initial.selectedFips = "13157"` the rail shows the dot and its accessible name contains "new details available", but the panel stays closed
  - (d) clicking "◂ Hide" collapses it again
- [X] T086 [US1] Update the e2e demo path in `frontend/tests/e2e/smoke.spec.ts`:
  - right after the shelters appear, assert `getByRole("button", { name: /Show details/ })` is visible and `getByTestId("county-summary")` is not
  - then click it before the county-summary, affected-summary and receiving-list assertions
  - after drawing the track, also assert the panel is still open (it was opened manually) and was not closed by drawing

**Checkpoint**: The default screen is map plus chat. All existing tests pass with the panel opened explicitly.

---

## Phase 15: Polish (collapsible panel)

- [X] T087 [P] Amend `specs/001-georgia-shelter-map/spec.md` for the decision:
  - add to `## Clarifications` → `### Session 2026-10-27`: "- Q: Should the summary pane always be visible? → A: No. It collapses to a rail, hidden by default, and opens with one click; hovering, selecting or drawing does not open it."
  - FR-003: change "On hover or selection, the system MUST show a county summary" to "On hover or selection, the system MUST update a county summary, shown in the details panel (collapsed by default, one click to open)"
  - FR-018: append "Shown in the details panel."
  - User Story 1 acceptance scenario 1: "…and its summary appears within a moment" becomes "…and, with the details panel open, its summary appears within a moment"
  - SC-004: append "(with the details panel open)"
  - in `specs/001-georgia-shelter-map/quickstart.md` §5, add "Open the Details panel" as the first step after the app loads
- [X] T088 Run the full verification:
  - `cd frontend && npx tsc -b && npx eslint . && npx vitest run && npm run build && npx playwright test`
  - capture two 1440×900 screenshots (closed and open, after drawing a Glynn Category 3 track) to the session scratchpad and check the map widens when the panel is closed and nothing overlaps when it opens

---

## Dependencies & Execution Order

### Collapsible panel (phases 14–15)

- T082 runs before T083. T084 and T085 can run alongside T083 (different files). T086 runs after T083.
- T087 is documentation and can run anytime. T088 runs last.

### Integration phases (8–13)

- **Phase 8** blocks all integration phases. T056, T057, T058 and T060 can run in parallel. T059 runs after T058.
- **Phase 9 (US1)** needs only Phase 8 and ADC. It can run alongside Phase 10.
- **Phase 10 (US2)**: T063 and T066 can be written and unit-tested offline. They stay unchecked until T061's schema check confirms `SHELTER_COLUMNS` against `evac_prod.shelters_clean`; offline fakes cannot catch a missing column. T063–T066 run before T067. T068 runs alongside T063–T066. T069 needs T060, T063–T067 and ADC. T070 can start before T069 using mock events.
- **Phase 11 (US3)** needs T066 and T067.
- **Phase 12 (US4)**: T073 runs before T076 and T077. T075 is documentation and can run anytime.
- **Phase 13** runs last. T081 gates any commit.
- **Parallel example**:
  - agent lane: `T063 → T066 → T067`, with `T064`, `T065`, `T068` alongside
  - frontend lane: `T056`, then `T070`, then `T076 → T077`, with `T078` alongside

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all stories.** T006 (validation) gates use of real data. T011–T016 can proceed against fixtures meanwhile.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after Foundational. It can run in parallel with US1, but highlighting (T033) needs the US1 layers (T021, T022) to show anything.
- **US3 (Phase 5)**: after Foundational and US1's map layers (T021, T022). T043 needs US2's ChatPanel (T031).
- **US4 (Phase 6)**: after US2 (T032). T046 needs US1's side panel.
- **Polish (Phase 7)**: after the desired stories are done. T049, T051 and T053 need a deployed service; T053 also needs the readiness agent.

### Within Each Story

Types and helpers come before components, components before wiring, and wiring before checkpoint
validation. Test tasks marked [P] can be written alongside their target.

### Parallel Opportunities

- Setup: T002–T005 together after T001.
- Foundational: T007, T008, T009, T010, T012, T015 and T020 in parallel. T011 → T013 → T014 → T016 in sequence on the agent side. T017 → T018 → T019 on the frontend side.
- US1: T021, T022, T024, T025 and T027 in parallel. Then T023, then T026.
- US2: T028 and T029 in parallel with T030. Then T031 → T032 → T033. T034 can run in parallel with T033.
- US3: T035, T036 and T038 in parallel. Then T037 and T039 → T040 and T041 → T042 → T043. T044 in parallel.

---

## Parallel Example: User Story 1

```bash
Task: "T021 [US1] CountyLayer in frontend/src/components/map/CountyLayer.tsx"
Task: "T022 [US1] ShelterLayer in frontend/src/components/map/ShelterLayer.tsx"
Task: "T024 [US1] ShelterDetails in frontend/src/components/summary/ShelterDetails.tsx"
Task: "T025 [US1] Legend in frontend/src/components/map/Legend.tsx"
Task: "T027 [US1] CountySummary test in frontend/tests/component/CountySummary.test.tsx"
```

## Parallel Example: User Story 3

```bash
Task: "T035 [US3] simulation.ts pure functions"
Task: "T036 [US3] simulation unit tests"
Task: "T038 [US3] CategoryPicker + ReachSlider"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup, then Phase 2 Foundational. Validate GA data and get the map-data path working through the agent.
2. Phase 3 US1. **Stop and validate**: hover Cobb, Chatham and Jackson and compare with BigQuery.
3. This is already a demo of "what's on file and how much is blank".

### Incremental Delivery

1. Add US2 (chat). It is useful even before the readiness agent is finished, because it can be tested against the MSW mock.
2. Add US3 (simulation and receiving list). This is the headline demo.
3. Add US4 (gaps presentation and "could not tell you").
4. Polish: deploy behind IAP, measure, run the equity audit and the grounding check.

### Team Split (README lanes)

- **Front end lane**: T001–T002, T007–T010, T017–T019, and then US1, US3 and US4.
- **Agent lane**: T003, T011–T016, T048, plus the readiness-agent feature (D1, D2).
- **Data lane**: T006, T052.
- **Story lane**: the T053 evidence, the T054 walk-through, and the demo script.

---

## Notes

- [P] tasks touch different files and have no dependency on unfinished tasks.
- Never convert a Flag to a boolean, and never drop or edit a registry row (Constitution I, VI).
- Commit after each task or logical group, and stop at any checkpoint to validate the story on its own.
