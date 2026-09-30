"""Publish the v1 school project to OSF and mint a DOI, without the web UI.

    $env:OSF_TOKEN = "your-token"
    python tools\\osf_publish.py            # shows what it will do, sends nothing
    python tools\\osf_publish.py --go       # actually does it

The token is read from the environment only. It is never written to disk or
printed. Create one at https://osf.io/settings/tokens/ with scope
osf.full_write.

Safe to re-run: the created project id is remembered in
submission/v1_release/osf_state.json, so a second run reuses the project and
only uploads files that are not there yet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "submission" / "v1_release"
STATE = RELEASE / "osf_state.json"
API = "https://api.osf.io/v2"
FILES = "https://files.osf.io/v1"

TITLE = (
    "Альтруистическое наказание в поведенческой экономике: сравнительный "
    "анализ поведения больших языковых моделей и человека в задаче "
    "punishment game"
)
DESCRIPTION = (
    "Индивидуальная выпускная работа, ОАНО «Школа «Летово», Москва, 2026. "
    "Супервайзер: Лоскутова З. В. Три языковые модели и 44 человека решали "
    "задачу costly punishment при четырёх уровнях стоимости наказания. "
    "Опрос людей был анонимным, персональных данных файлы не содержат."
)
UPLOADS = [
    "Vyatchanin_2026_v1_paper_ru.pdf",
    "Vyatchanin_2026_v1_data.xlsx",
    "Vyatchanin_2026_v1_prompts.pdf",
    "Vyatchanin_2026_v1_survey_form.pdf",
]


def call(method: str, url: str, token: str, body: bytes | None = None,
         content_type: str = "application/vnd.api+json") -> dict:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"\nOSF refused {method} {url}\nHTTP {err.code}: {detail}")
    return json.loads(raw) if raw else {}


def jsonapi(data: dict) -> bytes:
    return json.dumps({"data": data}).encode("utf-8")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", action="store_true", help="actually publish")
    args = parser.parse_args()

    missing = [f for f in UPLOADS if not (RELEASE / f).exists()]
    if missing:
        raise SystemExit(f"missing files in {RELEASE}: {missing}")

    print("\nWill publish to OSF:")
    print(f"  title:  {TITLE}")
    for f in UPLOADS:
        print(f"  file:   {f}  ({(RELEASE / f).stat().st_size // 1024} KB)")
    print("  then:   make the project public, mint a DOI")

    if not args.go:
        print("\nNothing sent. Add --go to do it for real.\n")
        return 0

    token = os.environ.get("OSF_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "\nOSF_TOKEN is not set in this PowerShell window.\n"
            'Run:  $env:OSF_TOKEN = "your-token"   then try again.'
        )

    me = call("GET", f"{API}/users/me/", token)
    print(f"\nSigned in to OSF as: {me['data']['attributes']['full_name']}")

    state = load_state()

    # 1. Project
    if "node_id" in state:
        node_id = state["node_id"]
        print(f"Reusing project {node_id}")
    else:
        node = call("POST", f"{API}/nodes/", token, jsonapi({
            "type": "nodes",
            "attributes": {
                "title": TITLE,
                "description": DESCRIPTION,
                "category": "project",
                "public": False,
            },
        }))
        node_id = node["data"]["id"]
        state["node_id"] = node_id
        save_state(state)
        print(f"Created project {node_id}")

    # 2. Files
    listing = call("GET", f"{API}/nodes/{node_id}/files/osfstorage/", token)
    present = {item["attributes"]["name"] for item in listing.get("data", [])}
    for name in UPLOADS:
        if name in present:
            print(f"  already uploaded: {name}")
            continue
        url = (
            f"{FILES}/resources/{node_id}/providers/osfstorage/"
            f"?kind=file&name={urllib.parse.quote(name)}"
        )
        call("PUT", url, token, (RELEASE / name).read_bytes(),
             content_type="application/octet-stream")
        print(f"  uploaded: {name}")

    # 3. Public
    call("PATCH", f"{API}/nodes/{node_id}/", token, jsonapi({
        "type": "nodes", "id": node_id, "attributes": {"public": True},
    }))
    print("Project is now public.")

    # 4. DOI
    ids = call("GET", f"{API}/nodes/{node_id}/identifiers/", token)
    doi = next(
        (i["attributes"]["value"] for i in ids.get("data", [])
         if i["attributes"]["category"] == "doi"),
        None,
    )
    if not doi:
        made = call("POST", f"{API}/nodes/{node_id}/identifiers/", token,
                    jsonapi({"type": "identifiers",
                             "attributes": {"category": "doi"}}))
        doi = made["data"]["attributes"]["value"]
    state["doi"] = doi
    save_state(state)

    print("\n=== DONE ===")
    print(f"Project: https://osf.io/{node_id}/")
    print(f"DOI:     {doi}")
    print(f"Link:    https://doi.org/{doi}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
