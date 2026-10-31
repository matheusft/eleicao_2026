"""Step 1: download raw TSE zips (and record manifest) and the TSE-IBGE crosswalk.

TSE dataset discovered via the CKAN API on dadosabertos.tse.jus.br:
    package_search?q=resultados 2026  ->  package "resultados-2026"
    package_show?id=resultados-2026   ->  resource URLs below (taken verbatim
    from the API response, not guessed).
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import requests

from common import RAW_DIR, sha256_file

CKAN_PACKAGE_SHOW = (
    "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026"
)

# Resource names (as published in the CKAN package) we download.
WANTED_RESOURCE_NAMES = {
    "Votação nominal por município e zona": "votacao_candidato_munzona_2026.zip",
    "Detalhe da apuração por município e zona": "detalhe_votacao_munzona_2026.zip",
}

CROSSWALK_URL = (
    "https://raw.githubusercontent.com/betafcc/Municipios-Brasileiros-TSE/"
    "master/municipios_brasileiros_tse.csv"
)
CROSSWALK_FILENAME = "municipios_tse_ibge_crosswalk.csv"

MANIFEST_PATH = RAW_DIR / "MANIFEST.csv"
MANIFEST_FIELDS = ["filename", "url", "download_time_utc", "size_bytes", "sha256"]


def _resolve_resource_urls() -> dict[str, str]:
    resp = requests.get(CKAN_PACKAGE_SHOW, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"CKAN package_show failed: {data}")

    resources = data["result"]["resources"]
    found = {}
    for r in resources:
        name = r["name"]
        if name in WANTED_RESOURCE_NAMES:
            found[WANTED_RESOURCE_NAMES[name]] = r["url"]

    missing = set(WANTED_RESOURCE_NAMES.values()) - set(found)
    if missing:
        available = "\n".join(f"  - {r['name']}" for r in resources)
        raise RuntimeError(
            "Could not find the expected 2026 resources on the TSE portal.\n"
            f"Missing: {missing}\n"
            f"Resources actually listed under package 'resultados-2026':\n{available}"
        )
    return found


def _download_file(url: str, dest: Path) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return {
        "filename": dest.name,
        "url": url,
        "download_time_utc": started.isoformat(timespec="seconds"),
        "size_bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = []

    resource_urls = _resolve_resource_urls()
    for filename, url in resource_urls.items():
        dest = RAW_DIR / filename
        print(f"Downloading {filename} from {url} ...")
        row = _download_file(url, dest)
        manifest_rows.append(row)
        print(f"  -> {row['size_bytes']:,} bytes, sha256={row['sha256']}")

    crosswalk_dest = RAW_DIR / CROSSWALK_FILENAME
    print(f"Downloading TSE-IBGE crosswalk from {CROSSWALK_URL} ...")
    row = _download_file(CROSSWALK_URL, crosswalk_dest)
    manifest_rows.append(row)
    print(f"  -> {row['size_bytes']:,} bytes, sha256={row['sha256']}")

    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
