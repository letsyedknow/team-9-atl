#!/usr/bin/env bash
# Copy read-only snapshots of the source datasets into evac_prod, the dataset the deployed agent reads.
# Only the tables listed here are overwritten; tables other pipelines load into evac_prod are left alone.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

PROD="${PROJECT_ID}:evac_prod"

bq --location US show "${PROD}" >/dev/null 2>&1 ||
  bq --location US mk --dataset --description "Team 9 data the deployed agent reads: snapshots of evacuation_readiness (*_clean, *_flow_staging) and hurricane_history, refreshed by deploy/refresh_evac_prod.sh, plus external inputs and model outputs loaded directly." "${PROD}" >/dev/null

tables() {
  bq query --quiet --use_legacy_sql=false --format=csv \
    "SELECT table_name FROM \`${PROJECT_ID}.$1.INFORMATION_SCHEMA.TABLES\` WHERE table_type = 'BASE TABLE' AND REGEXP_CONTAINS(table_name, r'$2') ORDER BY 1" |
    tail -n +2
}

copy() {
  local src="$1" pattern="$2" list
  list="$(tables "${src}" "${pattern}")"
  if [[ -z "${list}" ]]; then
    echo "no tables matched in ${src}" >&2
    exit 1
  fi
  for t in ${list}; do
    bq cp --force --quiet "${PROJECT_ID}:${src}.${t}" "${PROD}.${t}" >/dev/null
    echo "${src}.${t} -> evac_prod.${t}"
  done
}

copy evacuation_readiness '_(clean|flow_staging)$'
copy hurricane_history '.'
