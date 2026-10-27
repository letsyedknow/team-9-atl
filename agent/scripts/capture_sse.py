"""Capture one real /run_sse chat turn to a file, for replay in frontend tests (tasks T060, T069).

    .venv/bin/python scripts/capture_sse.py --question "How many shelters are in Cobb County?" \\
        --context '{"county_fips": "13067", "shelter_id": null, "scenario": null}' \\
        --out ../frontend/tests/mocks/recorded/us2-1.sse

Captured files must never contain personal data. Any Google Maps content inside them is for local
test replay only and is never shipped to users (FR-022).
"""

import argparse
import json
import urllib.request
from pathlib import Path

APP = "readiness_agent"


def post(url: str, body: dict | None = None) -> bytes:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as res:
        return res.read()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--question", required=True)
    p.add_argument("--context", default='{"county_fips": null, "shelter_id": null, "scenario": null}')
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()

    context = json.loads(a.context)
    session = json.loads(post(f"{a.base}/apps/{APP}/users/capture/sessions"))["id"]
    body = post(f"{a.base}/run_sse", {
        "app_name": APP,
        "user_id": "capture",
        "session_id": session,
        "streaming": True,
        "new_message": {"role": "user", "parts": [
            {"text": a.question},
            {"text": "CONTEXT v1 " + json.dumps(context)},
        ]},
    })
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(body)
    events = body.count(b"\ndata:") + body.startswith(b"data:")
    print(f"Wrote {len(body)} bytes ({events} events) to {a.out}")


if __name__ == "__main__":
    main()
