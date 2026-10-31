"""Step 5: validate the processed outputs against official TSE figures and
internal consistency rules. Prints a report; raises on hard failures that
would indicate the data is wrong (as opposed to expected modeling choices).
"""

from __future__ import annotations

import pandas as pd

from common import PROCESSED_DIR

OFFICIAL_ROUND2 = {
    "LULA": 64_256_232,
    "FLAVIO BOLSONARO": 59_826_041,
}
OFFICIAL_ROUND2_PCT = {
    "LULA": 51.79,
    "FLAVIO BOLSONARO": 48.21,
}
OFFICIAL_ABSTENTION_PCT = {1: 21.08, 2: 19.2}


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")


def main() -> None:
    votes = load("votes_candidate_munzona")
    turnout = load("turnout_munzona")
    results_national = load("results_national")

    report = []

    # 1. National round-2 candidate totals and shares vs. the official announcement.
    r2 = votes[votes["nr_turno"] == 2]
    totals = r2.groupby("nm_urna_candidato")["qt_votos_nominais"].sum()
    valid_total = totals.sum()
    for name, official_votes in OFFICIAL_ROUND2.items():
        got = int(totals.get(name, 0))
        pct = 100 * got / valid_total
        ok_votes = got == official_votes
        ok_pct = abs(pct - OFFICIAL_ROUND2_PCT[name]) < 0.01
        report.append(
            f"[{'OK' if ok_votes else 'MISMATCH'}] {name} round-2 votes: got {got:,}, official {official_votes:,}"
        )
        report.append(
            f"[{'OK' if ok_pct else 'MISMATCH'}] {name} round-2 share: got {pct:.2f}%, official {OFFICIAL_ROUND2_PCT[name]}%"
        )

    # 2. Abstention rate per round vs. official figures.
    for turno, official_pct in OFFICIAL_ABSTENTION_PCT.items():
        sub = turnout[turnout["nr_turno"] == turno]
        got_pct = 100 * sub["qt_abstencoes"].sum() / sub["qt_aptos"].sum()
        ok = abs(got_pct - official_pct) < 0.05
        report.append(
            f"[{'OK' if ok else 'MISMATCH'}] round {turno} abstention: got {got_pct:.2f}%, official ~{official_pct}%"
        )

    # 3. Reconciliation: candidate votes + blank + spoiled == turnout's valid+blank+spoiled basis,
    #    at the municipality x zone x round grain.
    vote_sum = (
        votes.groupby(["nr_turno", "sg_uf", "cd_municipio", "nr_zona"])[
            "qt_votos_nominais"
        ]
        .sum()
        .rename("qt_votos_candidatos")
    )
    t = turnout.set_index(["nr_turno", "sg_uf", "cd_municipio", "nr_zona"])
    merged = t.join(vote_sum, how="outer")
    bad_valid = merged[merged["qt_votos_candidatos"] != merged["qt_votos_validos"]]
    report.append(
        f"[{'OK' if len(bad_valid) == 0 else 'MISMATCH'}] "
        f"candidate-vote sum == turnout valid-vote total at every round/mun/zone "
        f"({len(bad_valid)} mismatching rows out of {len(merged)})"
    )

    bad_total = merged[
        merged["qt_comparecimento"]
        != (
            merged["qt_votos_validos"]
            + merged["qt_votos_brancos"]
            + merged["qt_votos_nulos"]
        )
    ]
    report.append(
        f"[{'OK' if len(bad_total) == 0 else 'MISMATCH'}] "
        f"comparecimento == validos+brancos+nulos at every round/mun/zone "
        f"({len(bad_total)} mismatching rows out of {len(merged)})"
    )

    # 4. No municipality appears twice within a round at the results_municipality grain.
    results_municipality = load("results_municipality")
    dup = results_municipality.duplicated(
        subset=["nr_turno", "sg_uf", "cd_municipio"]
    ).sum()
    report.append(
        f"[{'OK' if dup == 0 else 'MISMATCH'}] no duplicate (round, uf, municipio) rows ({dup} found)"
    )

    # 5. Row counts sanity.
    report.append(f"[INFO] votes_candidate_munzona rows: {len(votes):,}")
    report.append(f"[INFO] turnout_munzona rows: {len(turnout):,}")
    report.append(f"[INFO] results_municipality rows: {len(results_municipality):,}")
    report.append(f"[INFO] results_national rows: {len(results_national)}")

    print("\n".join(report))

    if any(r.startswith("[MISMATCH]") for r in report):
        raise SystemExit("Validation found mismatches -- see report above.")


if __name__ == "__main__":
    main()
