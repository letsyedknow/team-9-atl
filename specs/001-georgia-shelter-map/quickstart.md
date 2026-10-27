# Quickstart: Georgia Shelter Readiness Map

## 0. Prerequisites

- The challenge data is loaded for **GA**. In `notebooks/c4_01_load_explore.ipynb` (or
  `scripts/load.sh`), set `STATE = "GA"` and run everything.
- **Read the validation section**:
  - Any FAIL means stop.
  - Record every WARN in `research.md`. Expect the two Commerce capacities above 100,000.
- Node 20+, Python 3.12, and `gcloud` authenticated to the project.

## 1. Run the agent service locally

```bash
gcloud auth application-default login          # the agent's BigQuery, MCP and Gemini calls use ADC
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt            # includes requirements.txt plus test tools
export GOOGLE_CLOUD_PROJECT=<team project> GOOGLE_CLOUD_LOCATION=global GOOGLE_GENAI_USE_VERTEXAI=True
export EVAC_DATASET=evac_prod                  # tables shelters_clean, vulnerability_tracts_clean, …
export MODEL_NAME=gemini-3-flash-preview       # optional; the agent's default
uvicorn server:app --port 8000
```

Without credentials, run the frontend against the mocked agent instead:
`cd frontend && VITE_MOCK_AGENT=1 npm run dev`.

Smoke-test the map-data path. It needs no LLM and should return in a few seconds:

```bash
SID=$(curl -s -X POST localhost:8000/apps/readiness_agent/users/dev/sessions | jq -r .id)
curl -s -X POST localhost:8000/run -H 'content-type: application/json' -d "{
  \"app_name\":\"readiness_agent\",\"user_id\":\"dev\",\"session_id\":\"$SID\",
  \"new_message\":{\"role\":\"user\",\"parts\":[{\"text\":\"LOAD_MAP_DATA v1\"}]}}" \
| jq -r '.[-1].content.parts[0].text' | jq '{schema, shelters: (.shelters|length), counties: (.counties|length)}'
# expect: schema "map-data/v1", about 1792 shelters, 159 counties
```

## 2. Run the frontend

```bash
cd frontend
npm ci
npm run build:counties     # one-off: us-atlas → src/assets/ga-counties.topo.json (asserts 159)
npm run dev                # Vite proxies /apps, /run and /run_sse to :8000 (AGENT_URL overrides)
```

Capture a real chat turn for replay in tests (`frontend/tests/unit/chatFold.test.ts` picks up
every file in `frontend/tests/mocks/recorded/`):

```bash
cd agent && .venv/bin/python scripts/capture_sse.py \
  --question "How many shelters are in Cobb County and what is their capacity?" \
  --context '{"county_fips":"13067","shelter_id":null,"scenario":null}' \
  --out ../frontend/tests/mocks/recorded/us2-1.sse
```

## 3. Tests

```bash
cd agent && pytest
cd frontend && npm test            # Vitest: flags, simulation, grounding, components
cd frontend && npx playwright test # e2e smoke against the MSW-mocked agent
```

The tests must include:
- **SC-003**: an `UNRECORDED` wheelchair flag never renders as "No".
- **SC-005b**: no affected shelter appears in the receiving list.
- **FR-007**: Commerce capacities are excluded from `capacity_total` and still shown flagged.

## 4. Deploy (one Cloud Run service, IAP-gated)

```bash
gcloud run deploy readiness-map --source . --region us-central1 \
  --no-allow-unauthenticated --iap --min-instances 1 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=<project>,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=True

# Allow-list a person (no redeploy needed):
gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=readiness-map \
  --region us-central1 --member=user:<email> --role=roles/iap.httpsResourceAccessor
```

Check access: an account that isn't allow-listed gets the IAP denial page, and no request reaches
the service in Cloud Run logs (FR-023).

## 5. Manual acceptance walk-through (the demo path, SC-007)

1. Open the app. County outlines appear at once, and markers appear within 20 s.
2. Hover over Cobb, then Chatham. Each summary shows Yes / No / Not recorded counts and three people
   figures with their sources.
3. Hover over Jackson County. The Commerce shelters are flagged, and two totals are shown.
4. Draw a Category 3 track from offshore across Glynn County and inland. Check that:
   - the affected summary and the receiving list appear;
   - the cutoff reads 80 km;
   - the list is labeled straight-line and gives its unrecorded-accessibility count.
5. Move the cutoff to 150 km. The list updates within 1 s.
6. Ask: *"Which of these receiving shelters can actually take a wheelchair?"* Check that:
   - the answer separates recorded yes, recorded no and not assessed;
   - live-checked parts show Google Maps sources directly beneath them;
   - the referenced shelters highlight on the map.
7. **Equity audit (Constitution V)**:
   - For the step-4 scenario, export the receiving shelter IDs.
   - In BigQuery, join each shelter to its nearest tract in `vulnerability_tracts` and compare
     `pct_no_vehicle`, `pct_age_65_plus` and `pct_disability` with the state distribution.
   - Record the numbers, including "no difference", in `research.md`.
