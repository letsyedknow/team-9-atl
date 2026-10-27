#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -f out/numbers.json
for s in capacity corridor getout medical equity; do
  echo "== $s"
  uv run --with duckdb==2.0.0,pandas python "$s.py"
done
