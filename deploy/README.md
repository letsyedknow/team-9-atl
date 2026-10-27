# Deploying the agent

The ADK agent in `agent/` runs on Cloud Run as `evac-readiness-agent` (project `qwiklabs-gcp-04-edc952746633`, region `us-east1`).

- Live URL: https://evac-readiness-agent-hcodkdjhka-ue.a.run.app (the shelter map at `/`; ADK REST at `/apps`, `/run` and `/run_sse`, app `readiness_agent`)
- Every push to `main` that touches `agent/`, `frontend/`, `deploy/`, `Dockerfile` or the workflow redeploys through `.github/workflows/deploy-agent.yml`. It can also be run by hand from the Actions tab.

## How it fits together

| Piece | What it does |
|---|---|
| `Dockerfile` | Builds `frontend/` with Node, then a Python 3.12 image runs `agent/server.py` (uvicorn), which serves the ADK API and the built frontend |
| `deploy/config.sh` | Project, region, service and account names, shared by both scripts |
| `deploy/setup_gcp.sh` | One-time, idempotent: Artifact Registry repo `team9`, runtime account `evac-agent-run` (BigQuery read, Vertex AI), deployer account `github-deployer`, Workload Identity Federation for GitHub Actions on `main`, public access on the service |
| `deploy/deploy.sh [tag]` | Build for linux/amd64, push to Artifact Registry, deploy to Cloud Run |

GitHub Actions authenticates with Workload Identity Federation; there is no service-account key. Only pushes to `main` of `zm2231/team-9-atl` can assume the deployer. Repository variables `GCP_WIF_PROVIDER` and `GCP_DEPLOY_SA` hold the two identifiers that `setup_gcp.sh` prints.

## Deploy by hand

```
gcloud auth login && gcloud config set project qwiklabs-gcp-04-edc952746633
deploy/deploy.sh
```

Needs Docker and an account that can push to Artifact Registry and deploy to Cloud Run.

## Run locally

```
See `agent/README.md`.
```

Runtime settings (both `.env` and Cloud Run): `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_LOCATION=global` (Gemini 3 models are served from `global`), `MODEL_NAME=gemini-3-flash-preview`, `EVAC_DATASET=evac_prod`.

## Data

The agent reads `evac_prod`, a copy of the team's data that changes only when someone runs `deploy/refresh_evac_prod.sh`. The script copies snapshots of `evacuation_readiness` (`*_clean`, `*_flow_staging`) and all of `hurricane_history` into it; rerun it after either source changes. Tables are copied one at a time, so run it when nobody is mid-demo. Other inputs and model outputs are loaded into `evac_prod` directly, and the refresh script leaves them alone.
