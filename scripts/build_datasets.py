"""Step 3-4: read, clean, join and aggregate the presidential-race TSE data
into the analysis-ready tables in data/processed/.

Scope note: only the "<dataset>_BR.csv" member of each zip is used. As
documented in extract.py, that file already contains exactly and only the
"Presidente" race (CD_CARGO == 1), for every state + DF + ZZ (abroad),
both rounds -- the per-state files never contain presidential rows, so
there is no BR/per-state duplication to reconcile for this race.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

from common import EXTRACTED_DIR, PROCESSED_DIR, clean_string_nulls, to_nullable_int
from crosswalk import load_crosswalk

CANDIDATO_CSV = (
    EXTRACTED_DIR
    / "votacao_candidato_munzona_2026"
    / "votacao_candidato_munzona_2026_BR.csv"
)
DETALHE_CSV = (
    EXTRACTED_DIR
    / "detalhe_votacao_munzona_2026"
    / "detalhe_votacao_munzona_2026_BR.csv"
)

READ_KWARGS = dict(
    sep=";", encoding="latin1", quotechar='"', dtype=str, low_memory=False
)


def _parse_tse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%d/%m/%Y", errors="coerce").dt.date


def _assert_presidential_only(df: pd.DataFrame, cargo_col: str, label: str) -> None:
    cargos = set(df[cargo_col].str.strip('"').unique())
    if cargos not in ({"Presidente"}, {'"Presidente"'}):
        raise RuntimeError(
            f"{label}: expected only the Presidente race in the _BR.csv file, found {cargos}"
        )


def load_votes_candidate_munzona() -> pd.DataFrame:
    df = pd.read_csv(CANDIDATO_CSV, **READ_KWARGS)
    _assert_presidential_only(df, "DS_CARGO", "votacao_candidato_munzona_2026_BR")

    if not df["NR_TURNO"].isin(["1", "2"]).all():
        raise RuntimeError("Unexpected NR_TURNO values outside {1,2} in candidate file")
    if not (df["CD_CARGO"] == "1").all():
        raise RuntimeError("Unexpected CD_CARGO values outside {1} in candidate file")
    if not df["NM_TIPO_DESTINACAO_VOTOS"].eq("Válido").all():
        raise RuntimeError(
            "Candidate file contains non-'Válido' vote-destination rows; "
            "the pipeline assumes only valid nominal votes appear here."
        )

    out = pd.DataFrame()
    out["ano_eleicao"] = df["ANO_ELEICAO"].astype("Int64")
    out["nr_turno"] = df["NR_TURNO"].astype("Int64")
    out["dt_eleicao"] = _parse_tse_date(df["DT_ELEICAO"])
    out["sg_uf"] = df["SG_UF"]
    out["cd_municipio"] = to_nullable_int(df["CD_MUNICIPIO"])
    out["nm_municipio"] = df["NM_MUNICIPIO"]
    out["nr_zona"] = to_nullable_int(df["NR_ZONA"])
    out["sq_candidato"] = df["SQ_CANDIDATO"].astype("Int64")
    out["nr_candidato"] = to_nullable_int(df["NR_CANDIDATO"])
    out["nm_candidato"] = df["NM_CANDIDATO"]
    out["nm_urna_candidato"] = df["NM_URNA_CANDIDATO"]
    out["nr_partido"] = to_nullable_int(df["NR_PARTIDO"])
    out["sg_partido"] = df["SG_PARTIDO"]
    out["nm_partido"] = df["NM_PARTIDO"]
    out["nr_federacao"] = to_nullable_int(df["NR_FEDERACAO"])
    out["sg_federacao"] = clean_string_nulls(df["SG_FEDERACAO"])
    out["nm_federacao"] = clean_string_nulls(df["NM_FEDERACAO"])
    out["voto_em_transito"] = df["ST_VOTO_EM_TRANSITO"].map({"S": True, "N": False})
    out["qt_votos_nominais"] = to_nullable_int(df["QT_VOTOS_NOMINAIS"])
    out["cd_sit_tot_turno"] = to_nullable_int(df["CD_SIT_TOT_TURNO"])
    out["ds_sit_tot_turno"] = clean_string_nulls(df["DS_SIT_TOT_TURNO"])
    out["is_abroad"] = out["sg_uf"].eq("ZZ")

    dup_key = ["nr_turno", "sg_uf", "cd_municipio", "nr_zona", "sq_candidato"]
    n_dup = out.duplicated(subset=dup_key).sum()
    if n_dup:
        raise RuntimeError(
            f"votes_candidate_munzona: {n_dup} duplicate round/mun/zone/candidate rows"
        )

    return out


def load_turnout_munzona() -> pd.DataFrame:
    df = pd.read_csv(DETALHE_CSV, **READ_KWARGS)
    _assert_presidential_only(df, "DS_CARGO", "detalhe_votacao_munzona_2026_BR")

    if not df["NR_TURNO"].isin(["1", "2"]).all():
        raise RuntimeError("Unexpected NR_TURNO values outside {1,2} in turnout file")
    if not (df["CD_CARGO"] == "1").all():
        raise RuntimeError("Unexpected CD_CARGO values outside {1} in turnout file")

    out = pd.DataFrame()
    out["ano_eleicao"] = df["ANO_ELEICAO"].astype("Int64")
    out["nr_turno"] = df["NR_TURNO"].astype("Int64")
    out["dt_eleicao"] = _parse_tse_date(df["DT_ELEICAO"])
    out["sg_uf"] = df["SG_UF"]
    out["cd_municipio"] = to_nullable_int(df["CD_MUNICIPIO"])
    out["nm_municipio"] = df["NM_MUNICIPIO"]
    out["nr_zona"] = to_nullable_int(df["NR_ZONA"])
    out["qt_aptos"] = to_nullable_int(df["QT_APTOS"])
    out["qt_comparecimento"] = to_nullable_int(df["QT_COMPARECIMENTO"])
    out["qt_abstencoes"] = to_nullable_int(df["QT_ABSTENCOES"])
    out["qt_votos_validos"] = to_nullable_int(df["QT_TOTAL_VOTOS_VALIDOS"])
    out["qt_votos_brancos"] = to_nullable_int(df["QT_VOTOS_BRANCOS"])
    out["qt_votos_nulos"] = to_nullable_int(df["QT_TOTAL_VOTOS_NULOS"])
    out["is_abroad"] = out["sg_uf"].eq("ZZ")

    dup_key = ["nr_turno", "sg_uf", "cd_municipio", "nr_zona"]
    n_dup = out.duplicated(subset=dup_key).sum()
    if n_dup:
        raise RuntimeError(f"turnout_munzona: {n_dup} duplicate round/mun/zone rows")

    # Reconciliation check at source granularity: comparecimento = validos + brancos + nulos
    recon = out["qt_comparecimento"] - (
        out["qt_votos_validos"] + out["qt_votos_brancos"] + out["qt_votos_nulos"]
    )
    bad = out[recon != 0]
    if len(bad):
        raise RuntimeError(
            f"turnout_munzona: {len(bad)} zone rows where comparecimento != validos+brancos+nulos"
        )

    return out


def attach_ibge_code(df: pd.DataFrame, cw: pd.DataFrame, label: str) -> pd.DataFrame:
    merged = df.merge(
        cw, on=["cd_municipio", "sg_uf"], how="left", validate="many_to_one"
    )
    unmatched = merged[merged["cd_municipio_ibge"].isna() & ~merged["is_abroad"]]
    if len(unmatched):
        sample = (
            unmatched[["sg_uf", "cd_municipio", "nm_municipio"]]
            .drop_duplicates()
            .sort_values(["sg_uf", "cd_municipio"])
        )
        print(
            f"[{label}] WARNING: {len(sample)} domestic municipalities did not match the TSE-IBGE crosswalk:"
        )
        print(sample.to_string(index=False))
    merged = merged.drop(columns=["nm_municipio_crosswalk"])
    return merged


def build_results_municipality(
    votes: pd.DataFrame, turnout: pd.DataFrame
) -> pd.DataFrame:
    vote_mun = (
        votes.groupby(
            [
                "nr_turno",
                "sg_uf",
                "cd_municipio",
                "cd_municipio_ibge",
                "nm_municipio",
                "is_abroad",
                "nr_candidato",
                "nm_urna_candidato",
                "sg_partido",
            ],
            dropna=False,
        )["qt_votos_nominais"]
        .sum()
        .reset_index()
    )

    turnout_mun = (
        turnout.groupby(
            [
                "nr_turno",
                "sg_uf",
                "cd_municipio",
                "cd_municipio_ibge",
                "nm_municipio",
                "is_abroad",
            ],
            dropna=False,
        )[
            [
                "qt_aptos",
                "qt_comparecimento",
                "qt_abstencoes",
                "qt_votos_validos",
                "qt_votos_brancos",
                "qt_votos_nulos",
            ]
        ]
        .sum()
        .reset_index()
    )

    def _slug(name: str) -> str:
        ascii_name = (
            unicodedata.normalize("NFKD", name)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return ascii_name.lower()

    candidate_label = (
        vote_mun["nm_urna_candidato"]
        .map(_slug)
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    vote_mun = vote_mun.assign(col=("votos_" + candidate_label))

    wide_votes = vote_mun.pivot_table(
        index=[
            "nr_turno",
            "sg_uf",
            "cd_municipio",
            "cd_municipio_ibge",
            "nm_municipio",
            "is_abroad",
        ],
        columns="col",
        values="qt_votos_nominais",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    result = turnout_mun.merge(
        wide_votes,
        on=[
            "nr_turno",
            "sg_uf",
            "cd_municipio",
            "cd_municipio_ibge",
            "nm_municipio",
            "is_abroad",
        ],
        how="left",
    )

    vote_cols = [c for c in result.columns if c.startswith("votos_")]
    for c in vote_cols:
        share_col = c.replace("votos_", "pct_votos_validos_")
        result[share_col] = (result[c] / result["qt_votos_validos"]).round(6)

    dup = result.duplicated(subset=["nr_turno", "sg_uf", "cd_municipio"]).sum()
    if dup:
        raise RuntimeError(
            f"results_municipality: {dup} duplicate round/municipality rows"
        )

    return result


def _aggregate_level(municipality: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    vote_cols = [c for c in municipality.columns if c.startswith("votos_")]
    turnout_cols = [
        "qt_aptos",
        "qt_comparecimento",
        "qt_abstencoes",
        "qt_votos_validos",
        "qt_votos_brancos",
        "qt_votos_nulos",
    ]
    agg = (
        municipality.groupby(group_cols, dropna=False)[turnout_cols + vote_cols]
        .sum()
        .reset_index()
    )
    for c in vote_cols:
        share_col = c.replace("votos_", "pct_votos_validos_")
        agg[share_col] = (agg[c] / agg["qt_votos_validos"]).round(6)
    return agg


def build_results_state(results_municipality: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_level(results_municipality, ["nr_turno", "sg_uf"])


def build_results_national(results_municipality: pd.DataFrame) -> pd.DataFrame:
    return _aggregate_level(results_municipality, ["nr_turno"])


def _write(df: pd.DataFrame, name: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = PROCESSED_DIR / f"{name}.csv"
    parquet_path = PROCESSED_DIR / f"{name}.parquet"
    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)
    print(f"Wrote {name}: {len(df):,} rows -> {csv_path.name}, {parquet_path.name}")


def main() -> None:
    cw = load_crosswalk()

    votes = load_votes_candidate_munzona()
    turnout = load_turnout_munzona()

    votes = attach_ibge_code(votes, cw, "votes_candidate_munzona")
    turnout = attach_ibge_code(turnout, cw, "turnout_munzona")

    _write(votes, "votes_candidate_munzona")
    _write(turnout, "turnout_munzona")

    results_municipality = build_results_municipality(votes, turnout)
    _write(results_municipality, "results_municipality")

    results_state = build_results_state(results_municipality)
    _write(results_state, "results_state")

    results_national = build_results_national(results_municipality)
    _write(results_national, "results_national")

    print("\nDone.")


if __name__ == "__main__":
    main()
