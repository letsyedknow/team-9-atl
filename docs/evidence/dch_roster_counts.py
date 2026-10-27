import json
import urllib.parse
import urllib.request
from collections import Counter

URL = "https://forms.dch.georgia.gov/HFRD/GetFacilitiesData.svc/GetData?FACTYPE={}&maxbeds=1000"
COASTAL = {"CHATHAM", "BRYAN", "LIBERTY", "MCINTOSH", "GLYNN", "CAMDEN"}
TYPES = ("Assisted Living Community", "Personal Care Home")


def fetch(factype: str) -> list[dict]:
    with urllib.request.urlopen(URL.format(urllib.parse.quote(factype)), timeout=120) as resp:
        return json.loads(json.load(resp)["GetFacilityDetailsResult"])


def beds(rows: list[dict]) -> int:
    return int(sum(r.get("LICENSED BEDS #") or 0 for r in rows))


for factype in TYPES:
    rows = fetch(factype)
    status = Counter(r.get("OPERSTDESC") for r in rows)
    coastal = [r for r in rows if (r.get("COUNTY") or "").strip().upper() in COASTAL]
    no_beds = sum(1 for r in rows if not r.get("LICENSED BEDS #"))
    print(f"{factype}: facilities={len(rows)} licensed_beds={beds(rows)} "
          f"beds_unrecorded={no_beds} status={dict(status)} "
          f"coastal6_facilities={len(coastal)} coastal6_beds={beds(coastal)}")
