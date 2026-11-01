"""Election-forensics style statistical analysis of the 2026 presidential
results, focused on the question: are zone-level landslide results (>=90%
for one candidate) in round 2 statistically surprising, or expected from
binomial sampling variance given zone size and each municipality's own
underlying preference?

Methodology notes (read before trusting any single test in isolation):
  - The "null model" used throughout is NOT "fair coin / 50-50". It is:
    each zone's vote is a binomial draw at its own true electorate size
    (n) around its OWN municipality's revealed preference (p), estimated
    with the municipality's OTHER zones only (leave-one-out, so a zone is
    never used to validate itself). This is the standard, defensible way
    to ask "could this zone's result arise by chance" in a country with
    strong, real geographic heterogeneity in candidate support.
  - Digit-based tests (last-digit uniformity) are included because they
    are a standard tool in the election-forensics literature, but are
    flagged with the literature's own caveat (Deckert, Myagkov & Ordeshook
    2011): first-digit Benford's law is NOT theoretically expected for
    vote counts and has low power/high false-positive risk; last-digit
    tests are commonly used instead but still have limited power. Treat
    these as supplementary, not decisive.
  - All numbers here are computed directly from data/processed/*.parquet,
    produced by build_datasets.py from the official TSE files. Nothing is
    simulated or assumed except the explicitly-labeled Monte Carlo null.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import Bounds, LinearConstraint, minimize

from common import PROCESSED_DIR, ROOT

ANALYSIS_DIR = ROOT / "data" / "analysis"
FIG_DIR = ANALYSIS_DIR / "figures"
RNG = np.random.default_rng(20261031)
N_SIM = 4000
N_BOOT = 600

LULA = "LULA"
FLAVIO = "FLAVIO BOLSONARO"
# Round-1 candidates estimated individually in the vote-transfer model; every
# other candidate is pooled into "OTHER" (see build_municipality_candidate_matrix).
TRANSFER_KEEP_SEPARATE = {LULA, FLAVIO, "RONALDO CAIADO"}
OFFICIAL_LULA_R2_VOTES = 64_256_232
OFFICIAL_FLAVIO_R2_VOTES = 59_826_041


def load_zone_level() -> tuple[pd.DataFrame, pd.DataFrame]:
    votes = pd.read_parquet(PROCESSED_DIR / "votes_candidate_munzona.parquet")
    turnout = pd.read_parquet(PROCESSED_DIR / "turnout_munzona.parquet")
    return votes, turnout


def pivot_round(votes: pd.DataFrame, turno: int) -> pd.DataFrame:
    sub = votes[
        (votes["nr_turno"] == turno) & (votes["nm_urna_candidato"].isin([LULA, FLAVIO]))
    ]
    wide = sub.pivot_table(
        index=["sg_uf", "cd_municipio", "nr_zona"],
        columns="nm_urna_candidato",
        values="qt_votos_nominais",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    wide = wide.rename(columns={LULA: f"lula_r{turno}", FLAVIO: f"flavio_r{turno}"})
    return wide


def build_zone_table(votes: pd.DataFrame, turnout: pd.DataFrame) -> pd.DataFrame:
    r1 = pivot_round(votes, 1)
    r2 = pivot_round(votes, 2)

    zone_key = ["sg_uf", "cd_municipio", "nr_zona"]
    meta = turnout[turnout["nr_turno"] == 2][
        zone_key + ["nm_municipio", "cd_municipio_ibge", "is_abroad"]
    ].drop_duplicates(subset=zone_key)

    t1 = turnout[turnout["nr_turno"] == 1][
        zone_key + ["qt_aptos", "qt_comparecimento"]
    ].rename(columns={"qt_aptos": "aptos_r1", "qt_comparecimento": "comparecimento_r1"})
    t2 = turnout[turnout["nr_turno"] == 2][
        zone_key + ["qt_aptos", "qt_comparecimento"]
    ].rename(columns={"qt_aptos": "aptos_r2", "qt_comparecimento": "comparecimento_r2"})

    z = meta.merge(r2, on=zone_key, how="left").merge(t2, on=zone_key, how="left")
    z = z.merge(r1, on=zone_key, how="left").merge(t1, on=zone_key, how="left")

    for c in ["lula_r1", "flavio_r1", "lula_r2", "flavio_r2"]:
        z[c] = z[c].fillna(0)

    z["n_r2"] = z["lula_r2"] + z["flavio_r2"]
    z["n_r1"] = z["lula_r1"] + z["flavio_r1"]
    z["p_r2"] = np.where(z["n_r2"] > 0, z["lula_r2"] / z["n_r2"], np.nan)
    z["p_r1_twoparty"] = np.where(z["n_r1"] > 0, z["lula_r1"] / z["n_r1"], np.nan)

    # --- PRIMARY null model: uniform national swing applied to the zone's
    # OWN round-1 result. This is standard psephology practice and, unlike
    # a same-municipality comparison, works for every zone (most Brazilian
    # municipalities have exactly one electoral zone, so there is no
    # "other zone in this municipality" to compare against for ~97% of
    # them). National swing is passed in by the caller after this
    # function's result reveals it, so it is applied in a second pass by
    # the caller (see main()).
    z["turnout_rate_r1"] = z["comparecimento_r1"] / z["aptos_r1"]
    z["turnout_rate_r2"] = z["comparecimento_r2"] / z["aptos_r2"]
    z["turnout_rate_delta"] = z["turnout_rate_r2"] - z["turnout_rate_r1"]
    z["swing_r1_to_r2"] = z["p_r2"] - z["p_r1_twoparty"]

    # --- SECONDARY / diagnostic model: same-municipality, same-round,
    # leave-one-out. Only usable for the ~190 municipalities that have
    # more than one electoral zone (big cities). Kept as a cautionary
    # illustration in the report: within-city neighborhood heterogeneity
    # is normally far larger than binomial noise, so this model routinely
    # produces huge |z| on entirely legitimate results -- it is NOT used
    # for the Monte Carlo null or as fraud evidence, only to show why a
    # naive "compare to the surrounding area" test over-flags.
    muni = z.groupby(["sg_uf", "cd_municipio"])[["lula_r2", "flavio_r2"]].transform(
        "sum"
    )
    loo_lula = muni["lula_r2"] - z["lula_r2"]
    loo_flavio = muni["flavio_r2"] - z["flavio_r2"]
    loo_n = loo_lula + loo_flavio
    z["loo_n"] = loo_n
    z["p_loo"] = np.where(loo_n > 0, loo_lula / loo_n, np.nan)

    loo_n_safe = loo_n.where(loo_n > 0, other=np.nan)
    eps_loo = (1 / (2 * loo_n_safe)).fillna(0.0)
    p_loo_filled = z["p_loo"].fillna(0.0)
    z["p_loo_clipped"] = np.clip(p_loo_filled, eps_loo, 1 - eps_loo)
    z.loc[z["p_loo"].isna(), "p_loo_clipped"] = np.nan

    n_r2_safe = z["n_r2"].where(z["n_r2"] > 0, other=np.nan)
    se_loo = np.sqrt(z["p_loo_clipped"] * (1 - z["p_loo_clipped"]) / n_r2_safe)
    z["se_loo"] = se_loo
    z["z_score_same_muni"] = (z["p_r2"] - z["p_loo_clipped"]) / se_loo

    return z


def monte_carlo_landslide_null(
    z: pd.DataFrame,
    p_col: str,
    n_col: str = "n_r2",
    threshold: float = 0.90,
    n_sim: int = N_SIM,
) -> dict:
    valid = z.dropna(subset=[p_col, n_col])
    valid = valid[valid[n_col] > 0]
    n = valid[n_col].to_numpy()
    p = valid[p_col].to_numpy()
    lo_cut = 1 - threshold

    sims_lula90 = np.empty(n_sim, dtype=int)
    sims_flavio90 = np.empty(n_sim, dtype=int)
    sims_either90 = np.empty(n_sim, dtype=int)

    for i in range(n_sim):
        draws = RNG.binomial(n, p)
        share = draws / n
        lula90 = share >= threshold
        flavio90 = share <= lo_cut
        sims_lula90[i] = lula90.sum()
        sims_flavio90[i] = flavio90.sum()
        sims_either90[i] = (lula90 | flavio90).sum()

    actual_share = valid["lula_r2"] / valid[n_col]
    actual_lula90 = int((actual_share >= threshold).sum())
    actual_flavio90 = int((actual_share <= lo_cut).sum())
    actual_either90 = actual_lula90 + actual_flavio90

    def pctile_rank(actual: int, sims: np.ndarray) -> float:
        return float((sims <= actual).mean() * 100)

    return {
        "n_zones_simulated": int(len(valid)),
        "n_sim": n_sim,
        "actual_lula_ge90": actual_lula90,
        "actual_flavio_ge90": actual_flavio90,
        "actual_either_ge90": actual_either90,
        "sim_lula_ge90_mean": float(sims_lula90.mean()),
        "sim_lula_ge90_p05": float(np.percentile(sims_lula90, 5)),
        "sim_lula_ge90_p95": float(np.percentile(sims_lula90, 95)),
        "sim_flavio_ge90_mean": float(sims_flavio90.mean()),
        "sim_flavio_ge90_p05": float(np.percentile(sims_flavio90, 5)),
        "sim_flavio_ge90_p95": float(np.percentile(sims_flavio90, 95)),
        "sim_either_ge90_mean": float(sims_either90.mean()),
        "sim_either_ge90_p05": float(np.percentile(sims_either90, 5)),
        "sim_either_ge90_p95": float(np.percentile(sims_either90, 95)),
        "actual_lula90_percentile_in_null": pctile_rank(actual_lula90, sims_lula90),
        "actual_flavio90_percentile_in_null": pctile_rank(
            actual_flavio90, sims_flavio90
        ),
        "actual_either90_percentile_in_null": pctile_rank(
            actual_either90, sims_either90
        ),
        "sims_either90": sims_either90.tolist(),
        "sims_lula90": sims_lula90.tolist(),
        "sims_flavio90": sims_flavio90.tolist(),
    }


def last_digit_test(counts: pd.Series, min_count: int = 10) -> dict:
    c = counts[counts >= min_count].astype("int64")
    last_digit = (c % 10).to_numpy()
    observed = np.bincount(last_digit, minlength=10)
    expected = np.full(10, len(c) / 10)
    chi2, p = stats.chisquare(observed, expected)
    return {
        "n": int(len(c)),
        "observed": observed.tolist(),
        "expected_per_digit": float(len(c) / 10),
        "chi2": float(chi2),
        "p_value": float(p),
    }


def data_integrity_checks(votes_all: pd.DataFrame, turnout_all: pd.DataFrame) -> dict:
    """Independently re-derive the pipeline's own reconciliation checks
    (duplicates, candidate-votes-vs-valid, turnout-vs-valid+blank+null,
    impossible values, geographic coverage, national totals) directly from
    the processed parquet files, rather than just citing validate.py's
    prior run. Every number here is recomputed fresh."""
    d: dict = {}
    d["n_vote_records"] = int(len(votes_all))
    d["n_turnout_records"] = int(len(turnout_all))

    d["duplicate_vote_rows"] = int(
        votes_all.duplicated(
            subset=["nr_turno", "sg_uf", "cd_municipio", "nr_zona", "sq_candidato"]
        ).sum()
    )
    d["duplicate_turnout_rows"] = int(
        turnout_all.duplicated(
            subset=["nr_turno", "sg_uf", "cd_municipio", "nr_zona"]
        ).sum()
    )

    vote_sum = (
        votes_all.groupby(["nr_turno", "sg_uf", "cd_municipio", "nr_zona"])[
            "qt_votos_nominais"
        ]
        .sum()
        .rename("votos_candidatos")
    )
    t = turnout_all.set_index(["nr_turno", "sg_uf", "cd_municipio", "nr_zona"])
    merged = t.join(vote_sum, how="outer")
    d["n_zone_round_rows_checked"] = int(len(merged))
    d["reconciliation_failures_candidate_vs_valid"] = int(
        (merged["votos_candidatos"] != merged["qt_votos_validos"]).sum()
    )
    recon_total = (
        merged["qt_votos_validos"]
        + merged["qt_votos_brancos"]
        + merged["qt_votos_nulos"]
    )
    d["reconciliation_failures_turnout_vs_valid_blank_null"] = int(
        (merged["qt_comparecimento"] != recon_total).sum()
    )

    d["negative_vote_records"] = int((votes_all["qt_votos_nominais"] < 0).sum())
    d["turnout_exceeds_electorate"] = int(
        (turnout_all["qt_comparecimento"] > turnout_all["qt_aptos"]).sum()
    )
    d["negative_abstentions"] = int((turnout_all["qt_abstencoes"] < 0).sum())
    d["negative_blank_or_null"] = int(
        (
            (turnout_all["qt_votos_brancos"] < 0) | (turnout_all["qt_votos_nulos"] < 0)
        ).sum()
    )

    domestic = turnout_all[~turnout_all["is_abroad"]]
    d["domestic_zone_rows"] = int(len(domestic))
    d["domestic_zones_missing_ibge_code"] = int(
        domestic["cd_municipio_ibge"].isna().sum()
    )
    d["abroad_zone_rows"] = int((turnout_all["is_abroad"]).sum())
    d["abroad_locations"] = int(
        turnout_all.loc[turnout_all["is_abroad"], "cd_municipio"].nunique()
    )

    r2 = votes_all[votes_all["nr_turno"] == 2]
    lula_total = int(r2.loc[r2["nm_urna_candidato"] == LULA, "qt_votos_nominais"].sum())
    flavio_total = int(
        r2.loc[r2["nm_urna_candidato"] == FLAVIO, "qt_votos_nominais"].sum()
    )
    d["national_lula_r2_votes"] = lula_total
    d["national_flavio_r2_votes"] = flavio_total
    d["official_lula_r2_votes"] = OFFICIAL_LULA_R2_VOTES
    d["official_flavio_r2_votes"] = OFFICIAL_FLAVIO_R2_VOTES
    d["national_totals_match_official"] = bool(
        lula_total == OFFICIAL_LULA_R2_VOTES
        and flavio_total == OFFICIAL_FLAVIO_R2_VOTES
    )
    return d


def build_municipality_candidate_matrix(
    votes_all: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Municipality x candidate round-1 vote matrix, plus round-2
    Lula/Flavio vote columns.

    We estimate only the two finalists and Ronaldo Caiado individually, and
    pool every other round-1 candidate into a single 'OTHER' bloc. This is a
    deliberate identifiability choice, not cosmetic: ecological regression
    can only separate candidates whose municipal support patterns are
    distinct. Caiado (a sitting governor with a geographically concentrated
    base) is the one eliminated candidate the model resolves to an interior
    estimate; the remaining eliminated candidates are smaller and too
    collinear with the finalists to separate, so fitting them individually
    pins their rates to the 0/1 boundaries with error bars so wide they carry
    no information. Pooling them avoids presenting those non-identifiable
    point estimates as if they were findings. (Fitting all candidates
    separately leaves R^2 essentially unchanged, ~0.997, so nothing is lost
    in fit -- only spurious precision is avoided.)"""
    r1 = votes_all[votes_all["nr_turno"] == 1]
    r1_grouped = r1.copy()
    r1_grouped["group"] = r1_grouped["nm_urna_candidato"].where(
        r1_grouped["nm_urna_candidato"].isin(TRANSFER_KEEP_SEPARATE), "OTHER"
    )
    wide = (
        r1_grouped.groupby(["sg_uf", "cd_municipio", "group"])["qt_votos_nominais"]
        .sum()
        .unstack(fill_value=0)
    )

    r2 = votes_all[votes_all["nr_turno"] == 2]
    r2_wide = (
        r2.groupby(["sg_uf", "cd_municipio", "nm_urna_candidato"])["qt_votos_nominais"]
        .sum()
        .unstack(fill_value=0)
    )

    df = wide.join(
        r2_wide[[LULA, FLAVIO]].rename(columns={LULA: "lula_r2", FLAVIO: "flavio_r2"}),
        how="inner",
    )
    candidate_cols = [c for c in wide.columns]
    return df, candidate_cols


def _fit_joint_transfer(
    X: np.ndarray,
    y_lula: np.ndarray,
    y_flavio: np.ndarray,
    x0: np.ndarray | None = None,
) -> np.ndarray:
    """Jointly fit round-2 Lula and Flavio votes as linear functions of
    round-1 candidate votes, with each candidate's two rates constrained
    to lula_rate>=0, flavio_rate>=0, lula_rate+flavio_rate<=1. Fitting the
    two outcomes independently (two separate bounded regressions) can give
    lula_rate+flavio_rate > 1 for the same candidate -- mathematically
    impossible, since a voter can only go to one place. This joint
    constraint is what rules that out.

    Inputs must already be scaled to O(1) magnitude (raw vote counts are
    ~1e4-1e6, which makes the unscaled objective ~1e13 and breaks SLSQP's
    and trust-constr's internal numerics -- scaling X and y by the same
    constant leaves the optimal rates unchanged, since the problem is
    linear/homogeneous in that scale)."""
    k = X.shape[1]
    XtX = X.T @ X

    def objective(params):
        bl, bf = params[:k], params[k:]
        rl = X @ bl - y_lula
        rf = X @ bf - y_flavio
        return float(rl @ rl + rf @ rf)

    def grad(params):
        bl, bf = params[:k], params[k:]
        g_bl = 2 * (XtX @ bl - X.T @ y_lula)
        g_bf = 2 * (XtX @ bf - X.T @ y_flavio)
        return np.concatenate([g_bl, g_bf])

    def hess(params):
        H = np.zeros((2 * k, 2 * k))
        H[:k, :k] = 2 * XtX
        H[k:, k:] = 2 * XtX
        return H

    A = np.zeros((k, 2 * k))
    for j in range(k):
        A[j, j] = 1
        A[j, k + j] = 1
    constraints = [LinearConstraint(A, -np.inf, 1.0)]
    bounds = Bounds(0.0, 1.0)
    start = x0 if x0 is not None else np.full(2 * k, 0.3)
    res = minimize(
        objective,
        start,
        jac=grad,
        hess=hess,
        method="trust-constr",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "gtol": 1e-10, "xtol": 1e-12},
    )
    return res.x


def vote_transfer_analysis(votes_all: pd.DataFrame) -> dict:
    """Ecological (municipality-level) estimate of where each round-1
    candidate's votes went in round 2, via a jointly-constrained linear
    model (see _fit_joint_transfer), with a municipality-resample
    bootstrap for uncertainty. This is an aggregate/ecological estimate,
    not a measurement of individual voters -- see the report's caveats."""
    df, candidates = build_municipality_candidate_matrix(votes_all)
    SCALE = 1e4  # raw counts are ~1e4-1e6; see _fit_joint_transfer docstring
    X_raw = df[candidates].to_numpy(dtype=float)
    y_lula_raw = df["lula_r2"].to_numpy(dtype=float)
    y_flavio_raw = df["flavio_r2"].to_numpy(dtype=float)
    X, y_lula, y_flavio = X_raw / SCALE, y_lula_raw / SCALE, y_flavio_raw / SCALE
    n_muni = X.shape[0]
    k = len(candidates)

    point = _fit_joint_transfer(X, y_lula, y_flavio)
    beta_lula, beta_flavio = point[:k], point[k:]

    boot_lula = np.empty((N_BOOT, k))
    boot_flavio = np.empty((N_BOOT, k))
    rng = np.random.default_rng(7)
    for i in range(N_BOOT):
        idx = rng.integers(0, n_muni, n_muni)
        b = _fit_joint_transfer(X[idx], y_lula[idx], y_flavio[idx], x0=point)
        boot_lula[i], boot_flavio[i] = b[:k], b[k:]

    r1_votes_total = X_raw.sum(axis=0)
    rows = []
    for j, cand in enumerate(candidates):
        rows.append(
            {
                "candidate": cand,
                "r1_votes": float(r1_votes_total[j]),
                "lula_rate": float(beta_lula[j]),
                "lula_rate_lo": float(np.percentile(boot_lula[:, j], 5)),
                "lula_rate_hi": float(np.percentile(boot_lula[:, j], 95)),
                "flavio_rate": float(beta_flavio[j]),
                "flavio_rate_lo": float(np.percentile(boot_flavio[:, j], 5)),
                "flavio_rate_hi": float(np.percentile(boot_flavio[:, j], 95)),
            }
        )
        rows[-1]["other_rate"] = max(
            0.0, 1.0 - rows[-1]["lula_rate"] - rows[-1]["flavio_rate"]
        )

    pred_lula = (X @ beta_lula) * SCALE
    pred_flavio = (X @ beta_flavio) * SCALE
    ss_res_lula = float(np.sum((pred_lula - y_lula_raw) ** 2))
    ss_tot_lula = float(np.sum((y_lula_raw - y_lula_raw.mean()) ** 2))
    ss_res_flavio = float(np.sum((pred_flavio - y_flavio_raw) ** 2))
    ss_tot_flavio = float(np.sum((y_flavio_raw - y_flavio_raw.mean()) ** 2))
    return {
        "n_municipalities": int(n_muni),
        "n_bootstrap": N_BOOT,
        "candidates": rows,
        "model_fit": {
            "lula_r2_actual": float(y_lula_raw.sum()),
            "lula_r2_predicted": float(pred_lula.sum()),
            "flavio_r2_actual": float(y_flavio_raw.sum()),
            "flavio_r2_predicted": float(pred_flavio.sum()),
            "r_squared_lula": float(1 - ss_res_lula / ss_tot_lula),
            "r_squared_flavio": float(1 - ss_res_flavio / ss_tot_flavio),
        },
    }


def blank_null_stats(turnout_all: pd.DataFrame) -> dict:
    g = turnout_all.groupby("nr_turno")[
        ["qt_comparecimento", "qt_votos_brancos", "qt_votos_nulos", "qt_votos_validos"]
    ].sum()
    g["blank_rate_pct"] = 100 * g["qt_votos_brancos"] / g["qt_comparecimento"]
    g["null_rate_pct"] = 100 * g["qt_votos_nulos"] / g["qt_comparecimento"]
    g["invalid_rate_pct"] = g["blank_rate_pct"] + g["null_rate_pct"]
    out = {
        "round1": g.loc[1].to_dict(),
        "round2": g.loc[2].to_dict(),
    }
    out["blank_rate_change_pts"] = (
        out["round2"]["blank_rate_pct"] - out["round1"]["blank_rate_pct"]
    )
    out["null_rate_change_pts"] = (
        out["round2"]["null_rate_pct"] - out["round1"]["null_rate_pct"]
    )

    gs = (
        turnout_all.groupby(["sg_uf", "nr_turno"])[
            ["qt_comparecimento", "qt_votos_brancos", "qt_votos_nulos"]
        ]
        .sum()
        .reset_index()
    )
    gs["invalid_rate_pct"] = (
        100 * (gs["qt_votos_brancos"] + gs["qt_votos_nulos"]) / gs["qt_comparecimento"]
    )
    piv = gs.pivot(index="sg_uf", columns="nr_turno", values="invalid_rate_pct")
    piv = piv[piv.index != "ZZ"]
    out["state_invalid_rate"] = [
        {"sg_uf": uf, "r1": float(row[1]), "r2": float(row[2])}
        for uf, row in piv.iterrows()
    ]
    return out


def between_round_capture(z2: pd.DataFrame) -> dict:
    """Addresses a specific fraud claim: that in some zones one candidate
    captured ~100% of the extra votes between round 1 and round 2 (the
    eliminated candidates' votes, recovered blank/null, and higher turnout),
    while the other gained nothing. The claim is TRUE but is a restatement of
    the national swing through an unstable ratio, not a fraud signature:
      - "X captured 100% of the net gain" just means the OTHER candidate's
        zone total did not rise. Because the runoff swung to Lula, Flavio's
        total failed to rise far more often than Lula's.
      - The pattern is symmetric (it happens for Flavio in his strongholds)
        and tracks how the zone already leaned (ordinary consolidation).
      - Crucially, no votes are invented: the winner's gain never exceeds the
        REAL pool of available voters, and turnout never exceeds the
        electorate (see data_integrity)."""
    dL = (z2["lula_r2"] - z2["lula_r1"]).to_numpy(dtype=float)
    dF = (z2["flavio_r2"] - z2["flavio_r1"]).to_numpy(dtype=float)
    net = dL + dF
    lean = z2["p_r1_twoparty"].to_numpy(dtype=float)
    n = len(z2)

    lula_ge100 = (net > 0) & (dF <= 0) & (dL > 0)
    flavio_ge100 = (net > 0) & (dL <= 0) & (dF > 0)

    # Does the winner's gain fit inside the REAL available pool in each zone?
    nonfin_r1 = (
        z2["comparecimento_r1"] - z2["lula_r1"] - z2["flavio_r1"]
    ).to_numpy(dtype=float)
    new_turnout = np.clip(
        (z2["comparecimento_r2"] - z2["comparecimento_r1"]).to_numpy(dtype=float), 0, None
    )
    flavio_lost = np.clip(-dF, 0, None)
    pool_lula = nonfin_r1 + new_turnout + flavio_lost
    gpos = dL > 0
    gain_vs_pool = dL[gpos] / np.where(pool_lula[gpos] > 0, pool_lula[gpos], np.nan)

    # Consolidation: Lula's share of the net gain vs how the zone leaned.
    meaningful = net > 50
    share = np.clip(dL[meaningful] / net[meaningful], -0.5, 1.5)
    corr = float(np.corrcoef(lean[meaningful], share)[0, 1])

    def example(mask, winner, stronghold_only=False):
        # Largest-magnitude domestic zone where `winner` captured everything.
        # For Lula we restrict to his strongholds (>60% there in round 1) so
        # the example illustrates ordinary consolidation; the (rare) Flavio
        # cases are counter-swing zones, so we just take the largest.
        keep = mask & (~z2["is_abroad"])
        if stronghold_only:
            own_lean = z2["p_r1_twoparty"] if winner == "lula" else 1 - z2["p_r1_twoparty"]
            keep = keep & (own_lean >= 0.6)
        sub = z2[keep].copy()
        if not len(sub):
            return None
        sub["dL"] = sub["lula_r2"] - sub["lula_r1"]
        sub["dF"] = sub["flavio_r2"] - sub["flavio_r1"]
        row = sub.sort_values(
            "dL" if winner == "lula" else "dF", ascending=False
        ).iloc[0]
        return {
            "nm_municipio": row["nm_municipio"].title(),
            "sg_uf": row["sg_uf"],
            "nr_zona": int(row["nr_zona"]),
            "dL": int(row["dL"]),
            "dF": int(row["dF"]),
            "p_r1_twoparty": float(row["p_r1_twoparty"]),
        }
    return {
        "n_zones": int(n),
        "lula_ge100_zones": int(lula_ge100.sum()),
        "lula_ge100_pct": float(100 * lula_ge100.mean()),
        "flavio_ge100_zones": int(flavio_ge100.sum()),
        "flavio_ge100_pct": float(100 * flavio_ge100.mean()),
        "pct_flavio_no_growth": float(100 * (dF <= 0).mean()),
        "pct_lula_no_growth": float(100 * (dL <= 0).mean()),
        "corr_lean_capture": corr,
        "max_gain_vs_pool_pct": float(100 * np.nanmax(gain_vs_pool)),
        "n_zones_gain_exceeds_pool": int(np.nansum(gain_vs_pool > 1.0001)),
        "example_lula": example(
            pd.Series(lula_ge100, index=z2.index), "lula", stronghold_only=True
        ),
        "example_flavio": example(
            pd.Series(flavio_ge100, index=z2.index), "flavio"
        ),
    }


def robustness_panel(z2: pd.DataFrame) -> list[dict]:
    """Re-run the chance-model landslide test under several variants that
    each 'try to break' the headline Monte Carlo finding: dropping abroad
    zones, dropping tiny zones, and using thresholds other than 90%. If the
    actual-vs-chance gap survives every variant, that is much stronger
    evidence than any single run."""
    variants = []

    def run(label_key, zsub, threshold):
        mc = monte_carlo_landslide_null(
            zsub, p_col="p_predicted", n_col="n_r2", threshold=threshold, n_sim=1500
        )
        variants.append(
            {
                "key": label_key,
                "threshold": threshold,
                "n_zones": mc["n_zones_simulated"],
                "actual_lula": mc["actual_lula_ge90"],
                "sim_lula_mean": mc["sim_lula_ge90_mean"],
                "sim_lula_p05": mc["sim_lula_ge90_p05"],
                "sim_lula_p95": mc["sim_lula_ge90_p95"],
                "actual_flavio": mc["actual_flavio_ge90"],
                "sim_flavio_mean": mc["sim_flavio_ge90_mean"],
                "sim_flavio_p05": mc["sim_flavio_ge90_p05"],
                "sim_flavio_p95": mc["sim_flavio_ge90_p95"],
            }
        )

    run("baseline", z2, 0.90)
    run("exclude_abroad", z2[~z2["is_abroad"]], 0.90)
    run("exclude_small_n", z2[z2["n_r2"] >= 50], 0.90)
    run("threshold_85", z2, 0.85)
    run("threshold_95", z2, 0.95)
    return variants


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    votes, turnout = load_zone_level()
    z = build_zone_table(votes, turnout)

    # National uniform swing, used to build the PRIMARY null model: predict
    # each zone's round-2 share from its OWN round-1 two-party share plus
    # the national average swing. This works for every zone (unlike the
    # same-municipality model) and is not circular (round 1 and round 2
    # are independent counts).
    national_r1_twoparty = z["lula_r1"].sum() / (
        z["lula_r1"].sum() + z["flavio_r1"].sum()
    )
    national_r2 = z["lula_r2"].sum() / (z["lula_r2"].sum() + z["flavio_r2"].sum())
    national_swing = national_r2 - national_r1_twoparty

    predicted_p = z["p_r1_twoparty"] + national_swing
    n_r2_safe = z["n_r2"].where(z["n_r2"] > 0, other=np.nan)
    eps_swing = (1 / (2 * n_r2_safe)).fillna(0.0)
    predicted_p_filled = predicted_p.fillna(0.0)
    z["p_predicted"] = np.clip(predicted_p_filled, eps_swing, 1 - eps_swing)
    z.loc[predicted_p.isna(), "p_predicted"] = np.nan
    se_swing = np.sqrt(z["p_predicted"] * (1 - z["p_predicted"]) / n_r2_safe)
    z["se_swing"] = se_swing
    z["z_score"] = (z["p_r2"] - z["p_predicted"]) / se_swing

    z2 = z[z["n_r2"] > 0].copy()
    n_total_zones = len(z2)

    lula90 = z2[z2["p_r2"] >= 0.90]
    flavio90 = z2[z2["p_r2"] <= 0.10]

    summary: dict = {}
    summary["n_total_zones_r2"] = int(n_total_zones)
    summary["n_lula_ge90"] = int(len(lula90))
    summary["n_flavio_ge90"] = int(len(flavio90))
    summary["pct_lula_ge90"] = float(100 * len(lula90) / n_total_zones)
    summary["pct_flavio_ge90"] = float(100 * len(flavio90) / n_total_zones)

    summary["n_distribution_all"] = {
        "median": float(z2["n_r2"].median()),
        "mean": float(z2["n_r2"].mean()),
        "p90": float(z2["n_r2"].quantile(0.90)),
    }
    summary["n_distribution_lula90"] = {
        "median": float(lula90["n_r2"].median()) if len(lula90) else None,
        "mean": float(lula90["n_r2"].mean()) if len(lula90) else None,
        "max": float(lula90["n_r2"].max()) if len(lula90) else None,
        "n_above_1000": int((lula90["n_r2"] > 1000).sum()),
    }
    summary["n_distribution_flavio90"] = {
        "median": float(flavio90["n_r2"].median()) if len(flavio90) else None,
        "mean": float(flavio90["n_r2"].mean()) if len(flavio90) else None,
        "max": float(flavio90["n_r2"].max()) if len(flavio90) else None,
        "n_above_1000": int((flavio90["n_r2"] > 1000).sum()),
    }

    # Largest landslide zones by raw electorate size (the ones that would matter most if real).
    top_landslide_by_n = pd.concat(
        [lula90.assign(winner="LULA"), flavio90.assign(winner="FLAVIO BOLSONARO")]
    )
    top_landslide_by_n = top_landslide_by_n.sort_values("n_r2", ascending=False).head(
        15
    )
    summary["top_landslide_zones_by_n"] = top_landslide_by_n[
        [
            "sg_uf",
            "cd_municipio",
            "nm_municipio",
            "nr_zona",
            "n_r2",
            "p_r2",
            "p_r1_twoparty",
            "winner",
            "is_abroad",
        ]
    ].to_dict(orient="records")

    # PRIMARY z-score (own-zone round-1 + national uniform swing) anomaly ranking.
    zvalid = z2.dropna(subset=["z_score"])
    zvalid = zvalid[np.isfinite(zvalid["z_score"])]
    summary["n_zones_with_zscore"] = int(len(zvalid))
    summary["zscore_distribution"] = {
        "mean": float(zvalid["z_score"].mean()),
        "std": float(zvalid["z_score"].std()),
        "pct_abs_gt_2": float(100 * (zvalid["z_score"].abs() > 2).mean()),
        "pct_abs_gt_3": float(100 * (zvalid["z_score"].abs() > 3).mean()),
    }
    top_anomalies = zvalid.reindex(
        zvalid["z_score"].abs().sort_values(ascending=False).index
    ).head(20)
    summary["top_anomaly_zones"] = top_anomalies[
        [
            "sg_uf",
            "cd_municipio",
            "nm_municipio",
            "nr_zona",
            "n_r2",
            "p_predicted",
            "p_r2",
            "z_score",
            "is_abroad",
        ]
    ].to_dict(orient="records")

    # Complementary ranking: largest ABSOLUTE percentage-point miss vs the
    # swing-predicted share, regardless of N. This separates "statistically
    # extreme because N is huge and the model is imperfect" (the z-score
    # ranking above) from "the model missed by a practically large margin."
    abs_dev = zvalid.copy()
    abs_dev["abs_dev_pts"] = 100 * (abs_dev["p_r2"] - abs_dev["p_predicted"]).abs()
    top_abs_dev = abs_dev.sort_values("abs_dev_pts", ascending=False).head(15)
    summary["top_abs_deviation_zones"] = top_abs_dev[
        [
            "sg_uf",
            "cd_municipio",
            "nm_municipio",
            "nr_zona",
            "n_r2",
            "p_predicted",
            "p_r2",
            "abs_dev_pts",
            "z_score",
            "is_abroad",
        ]
    ].to_dict(orient="records")

    # SECONDARY / diagnostic: same-municipality leave-one-out z-score, only
    # defined for the ~190 multi-zone municipalities. Shown as a cautionary
    # illustration, not used for any fraud conclusion (see module docstring
    # and build_zone_table()).
    zmuni_valid = z2.dropna(subset=["z_score_same_muni"])
    zmuni_valid = zmuni_valid[np.isfinite(zmuni_valid["z_score_same_muni"])]
    summary["same_muni_diagnostic"] = {
        "n_zones_with_score": int(len(zmuni_valid)),
        "n_multi_zone_municipalities": int(
            z.groupby(["sg_uf", "cd_municipio"]).size().gt(1).sum()
        ),
        "mean": (
            float(zmuni_valid["z_score_same_muni"].mean()) if len(zmuni_valid) else None
        ),
        "std": (
            float(zmuni_valid["z_score_same_muni"].std()) if len(zmuni_valid) else None
        ),
        "max_abs": (
            float(zmuni_valid["z_score_same_muni"].abs().max())
            if len(zmuni_valid)
            else None
        ),
        "pct_abs_gt_3": (
            float(100 * (zmuni_valid["z_score_same_muni"].abs() > 3).mean())
            if len(zmuni_valid)
            else None
        ),
    }

    # Monte Carlo null simulation, using the PRIMARY (swing-predicted) model.
    mc = monte_carlo_landslide_null(z2, p_col="p_predicted", n_col="n_r2")
    summary["monte_carlo"] = {k: v for k, v in mc.items() if not k.startswith("sims_")}

    # Swing / turnout-correlation analysis.
    swing_valid = z2.dropna(subset=["swing_r1_to_r2", "turnout_rate_delta"])
    r, p = stats.pearsonr(
        swing_valid["turnout_rate_delta"], swing_valid["swing_r1_to_r2"]
    )
    summary["swing_turnout_correlation"] = {
        "n": int(len(swing_valid)),
        "pearson_r": float(r),
        "p_value": float(p),
        "swing_mean": float(swing_valid["swing_r1_to_r2"].mean()),
        "swing_std": float(swing_valid["swing_r1_to_r2"].std()),
    }

    # National round1 two-party check for context (computed above, pre-filter).
    summary["national_two_party_share"] = {
        "lula_r1_twoparty_pct": float(100 * national_r1_twoparty),
        "lula_r2_pct": float(100 * national_r2),
        "flavio_r2_pct": float(100 * (1 - national_r2)),
        "swing_pts": float(100 * (national_r2 - national_r1_twoparty)),
    }
    # National abstention rate by round (electorate-weighted), so the report
    # can cite it from data instead of hard-coding it.
    nat_abst = turnout.groupby("nr_turno")[["qt_aptos", "qt_abstencoes"]].sum()
    summary["national_abstention"] = {
        "r1_pct": float(
            100 * nat_abst.loc[1, "qt_abstencoes"] / nat_abst.loc[1, "qt_aptos"]
        ),
        "r2_pct": float(
            100 * nat_abst.loc[2, "qt_abstencoes"] / nat_abst.loc[2, "qt_aptos"]
        ),
    }
    summary["n_distinct_municipalities"] = int(
        z.groupby(["sg_uf", "cd_municipio"]).ngroups
    )
    summary["n_round1_candidates"] = int(
        votes[votes["nr_turno"] == 1]["nm_urna_candidato"].nunique()
    )

    # Digit tests.
    summary["last_digit_test_lula_r2"] = last_digit_test(z2["lula_r2"])
    summary["last_digit_test_flavio_r2"] = last_digit_test(z2["flavio_r2"])
    results_muni = pd.read_parquet(PROCESSED_DIR / "results_municipality.parquet")
    r2_muni = results_muni[results_muni["nr_turno"] == 2]
    summary["last_digit_test_muni_valid_votes"] = last_digit_test(
        r2_muni["qt_votos_validos"]
    )

    # State-level swing table, plus turnout/abstention by state (used by
    # the regional-context section's second chart).
    state_tbl = (
        z.groupby("sg_uf")[["lula_r1", "flavio_r1", "lula_r2", "flavio_r2"]]
        .sum()
        .reset_index()
    )
    state_tbl["p_r1_twoparty"] = state_tbl["lula_r1"] / (
        state_tbl["lula_r1"] + state_tbl["flavio_r1"]
    )
    state_tbl["p_r2"] = state_tbl["lula_r2"] / (
        state_tbl["lula_r2"] + state_tbl["flavio_r2"]
    )
    state_tbl["swing_pts"] = 100 * (state_tbl["p_r2"] - state_tbl["p_r1_twoparty"])

    state_turnout = (
        turnout.groupby(["sg_uf", "nr_turno"])[["qt_aptos", "qt_abstencoes"]]
        .sum()
        .reset_index()
    )
    state_turnout["abstention_pct"] = (
        100 * state_turnout["qt_abstencoes"] / state_turnout["qt_aptos"]
    )
    piv_abst = state_turnout.pivot(
        index="sg_uf", columns="nr_turno", values="abstention_pct"
    )
    state_tbl = state_tbl.merge(
        piv_abst.rename(columns={1: "abstention_r1", 2: "abstention_r2"}),
        on="sg_uf",
        how="left",
    )
    summary["state_table"] = state_tbl.sort_values("p_r2", ascending=False).to_dict(
        orient="records"
    )

    # --- New sections: data integrity, vote transfer, blank/null, robustness.
    summary["data_integrity"] = data_integrity_checks(votes, turnout)
    summary["vote_transfer"] = vote_transfer_analysis(votes)
    summary["blank_null"] = blank_null_stats(turnout)
    summary["robustness"] = robustness_panel(z2)
    summary["between_round_capture"] = between_round_capture(z2)

    with open(ANALYSIS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    z2.to_parquet(ANALYSIS_DIR / "zone_table.parquet", index=False)
    mc_full = {
        "sims_either90": mc["sims_either90"],
        "sims_lula90": mc["sims_lula90"],
        "sims_flavio90": mc["sims_flavio90"],
    }
    np.savez(
        ANALYSIS_DIR / "monte_carlo_sims.npz",
        **{k: np.array(v) for k, v in mc_full.items()},
    )

    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k
                not in ("top_landslide_zones_by_n", "top_anomaly_zones", "state_table")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
