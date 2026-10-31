"""TSE <-> IBGE municipality code crosswalk.

Source: community-maintained table at
https://github.com/betafcc/Municipios-Brasileiros-TSE
(codigo_tse, uf, nome_municipio, capital, codigo_ibge).

TSE does not publish an official combined TSE/IBGE code crosswalk file on
dadosabertos.tse.jus.br, so this widely-used community table is used
instead. Coverage and any non-matches are reported at build time rather
than silently dropped.
"""

from __future__ import annotations

import pandas as pd

from common import RAW_DIR

CROSSWALK_PATH = RAW_DIR / "municipios_tse_ibge_crosswalk.csv"

# The betafcc crosswalk predates Brazil's newest municipality and is missing
# it. Confirmed manually against IBGE's own municipality page
# (ibge.gov.br/cidades-e-estados/mt/boa-esperanca-do-norte.html): installed
# 2025-01-01, split from Brasnorte (MT), IBGE code 5101837. TSE's municipal
# code for it (73709) was read directly off the 2026 results files.
MANUAL_OVERRIDES = [
    {
        "codigo_tse": "73709",
        "uf": "MT",
        "nome_municipio": "BOA ESPERANÇA DO NORTE",
        "capital": "0",
        "codigo_ibge": "5101837",
    },
]


def load_crosswalk() -> pd.DataFrame:
    df = pd.read_csv(CROSSWALK_PATH, dtype=str)
    overrides = pd.DataFrame(MANUAL_OVERRIDES)
    df = pd.concat([df, overrides], ignore_index=True)
    df = df.rename(
        columns={
            "codigo_tse": "cd_municipio",
            "uf": "sg_uf",
            "nome_municipio": "nm_municipio_crosswalk",
            "codigo_ibge": "cd_municipio_ibge",
        }
    )
    # Both codes are purely numeric in both sources; join as integers so
    # zero-padding conventions can't cause silent join misses.
    df["cd_municipio"] = df["cd_municipio"].astype("Int64")
    df["cd_municipio_ibge"] = df["cd_municipio_ibge"].astype("Int64")
    return df[["cd_municipio", "sg_uf", "nm_municipio_crosswalk", "cd_municipio_ibge"]]
