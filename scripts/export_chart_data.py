"""Package the already-computed analysis outputs (zone_table.parquet,
summary.json, monte_carlo_sims.npz, votes_candidate_munzona.parquet) into a
single compact JSON file the report's inline JS charting code consumes.

Zone-level rows are packed as plain arrays (not objects) to keep the file
small with ~6,250 rows; COLUMNS documents the order.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import PROCESSED_DIR, ROOT

ANALYSIS_DIR = ROOT / "data" / "analysis"
OUT_PATH = ANALYSIS_DIR / "chart_data.json"

COLUMNS = ["uf", "mun", "zona", "abroad", "n", "p2", "p1", "dturn", "swing"]


def round_or_none(x, nd=6):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def main() -> None:
    z = pd.read_parquet(ANALYSIS_DIR / "zone_table.parquet")
    z = z[z["n_r2"] > 0].copy()
    summary = json.loads((ANALYSIS_DIR / "summary.json").read_text(encoding="utf-8"))
    sims = np.load(ANALYSIS_DIR / "monte_carlo_sims.npz")
    votes = pd.read_parquet(PROCESSED_DIR / "votes_candidate_munzona.parquet")

    zones = []
    for r in z.itertuples(index=False):
        zones.append(
            [
                r.sg_uf,
                r.nm_municipio.title(),
                int(r.nr_zona),
                bool(r.is_abroad),
                int(r.n_r2),
                round_or_none(r.p_r2),
                round_or_none(r.p_r1_twoparty),
                round_or_none(r.turnout_rate_delta),
                round_or_none(r.swing_r1_to_r2),
            ]
        )

    def candidate_pcts(turno: int):
        sub = (
            votes[votes["nr_turno"] == turno]
            .groupby("nm_urna_candidato")["qt_votos_nominais"]
            .sum()
        )
        pct = (100 * sub / sub.sum()).round(3)
        # Each entry: [name, share-of-valid-votes (%), absolute vote count].
        # The vote count lets the chart show both the share and the raw
        # number of votes behind it in the tooltip.
        return [
            [name.title(), float(pct[name]), int(sub[name])]
            for name in pct.sort_values(ascending=False).index
        ]

    data = {
        "columns": COLUMNS,
        "zones": zones,
        "national": {"round1": candidate_pcts(1), "round2": candidate_pcts(2)},
        "monte_carlo": {
            "sims_lula90": sims["sims_lula90"].tolist(),
            "sims_flavio90": sims["sims_flavio90"].tolist(),
            "actual_lula90": summary["monte_carlo"]["actual_lula_ge90"],
            "actual_flavio90": summary["monte_carlo"]["actual_flavio_ge90"],
            "n_sim": summary["monte_carlo"]["n_sim"],
        },
        "digit_lula": summary["last_digit_test_lula_r2"],
        "digit_flavio": summary["last_digit_test_flavio_r2"],
        "state_table": [
            [
                row["sg_uf"],
                round_or_none(row["p_r1_twoparty"]),
                round_or_none(row["p_r2"]),
                round_or_none(row.get("abstention_r1")),
                round_or_none(row.get("abstention_r2")),
            ]
            for row in summary["state_table"]
            if row["sg_uf"] != "ZZ"
        ],
        "vote_transfer": summary["vote_transfer"],
        "blank_null": {
            "round1": summary["blank_null"]["round1"],
            "round2": summary["blank_null"]["round2"],
            "state": summary["blank_null"]["state_invalid_rate"],
        },
        "robustness": summary["robustness"],
        "data_integrity": summary["data_integrity"],
    }

    OUT_PATH.write_text(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes), {len(zones):,} zones")


if __name__ == "__main__":
    main()
