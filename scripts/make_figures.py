"""Generate the SVG exhibits for the election-forensics report from
data/analysis/summary.json, zone_table.parquet and monte_carlo_sims.npz.

Charts are rendered on their own light "exhibit" surface (not transparent)
so they stay legible regardless of the surrounding page's light/dark theme
-- the same treatment a printed exhibit or scanned chart gets when placed
on a dark page, applied consistently across every figure here.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from common import PROCESSED_DIR, ROOT

ANALYSIS_DIR = ROOT / "data" / "analysis"
FIG_DIR = ANALYSIS_DIR / "figures"

COLOR_FLAVIO = "#2a78d6"
COLOR_LULA = "#e34948"
COLOR_ACCENT = "#4a3aa7"
COLOR_MUTED = "#9a978e"
COLOR_TEXT = "#2b2a27"
SURFACE = "#fcfcfb"

plt.rcParams.update(
    {
        "svg.fonttype": "path",
        "font.family": "DejaVu Sans",
        "text.color": COLOR_TEXT,
        "axes.edgecolor": COLOR_MUTED,
        "axes.labelcolor": COLOR_TEXT,
        "xtick.color": COLOR_TEXT,
        "ytick.color": COLOR_TEXT,
        "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 12,
    }
)


def _style_axes(ax, grid_axis="y"):
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(COLOR_MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=COLOR_TEXT, length=0)
    ax.grid(axis=grid_axis, color=COLOR_MUTED, alpha=0.25, linewidth=0.7)
    ax.set_axisbelow(True)


import os

PNG_PREVIEW = os.environ.get("FIGS_PNG_PREVIEW")


def save(fig, name: str) -> None:
    fig.savefig(
        FIG_DIR / f"{name}.svg",
        format="svg",
        bbox_inches="tight",
        transparent=False,
        dpi=200,
    )
    if PNG_PREVIEW:
        fig.savefig(
            f"{PNG_PREVIEW}/{name}.png", format="png", dpi=150, bbox_inches="tight"
        )
    plt.close(fig)


def fig_national_results(summary: dict, votes: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))

    r1 = (
        votes[votes["nr_turno"] == 1]
        .groupby("nm_urna_candidato")["qt_votos_nominais"]
        .sum()
    )
    r1_pct = 100 * r1 / r1.sum()
    r1_pct = r1_pct.sort_values(ascending=True)
    colors1 = [
        (
            COLOR_LULA
            if c == "LULA"
            else COLOR_FLAVIO if c == "FLAVIO BOLSONARO" else COLOR_MUTED
        )
        for c in r1_pct.index
    ]
    ax = axes[0]
    bars = ax.barh(r1_pct.index, r1_pct.values, color=colors1, height=0.65)
    for b, v in zip(bars, r1_pct.values):
        ax.text(
            v + 0.8,
            b.get_y() + b.get_height() / 2,
            f"{v:.1f}%",
            va="center",
            fontsize=9,
            color=COLOR_TEXT,
        )
    ax.set_xlim(0, max(r1_pct.values) * 1.22)
    ax.set_title(
        "Round 1 (Oct 4) — % of valid votes", fontsize=11, loc="left", color=COLOR_TEXT
    )
    _style_axes(ax, grid_axis="x")
    ax.set_yticklabels([lbl.title() for lbl in r1_pct.index], fontsize=9)

    r2 = (
        votes[votes["nr_turno"] == 2]
        .groupby("nm_urna_candidato")["qt_votos_nominais"]
        .sum()
    )
    r2_pct = 100 * r2 / r2.sum()
    ax = axes[1]
    order = ["FLAVIO BOLSONARO", "LULA"]
    vals = [r2_pct[o] for o in order]
    cols = [COLOR_FLAVIO, COLOR_LULA]
    bars = ax.barh(
        ["Flávio\nBolsonaro (PL)", "Lula (PT)"], vals, color=cols, height=0.55
    )
    for b, v in zip(bars, vals):
        ax.text(
            v + 0.8,
            b.get_y() + b.get_height() / 2,
            f"{v:.2f}%",
            va="center",
            fontsize=10,
            color=COLOR_TEXT,
            fontweight="bold",
        )
    ax.set_xlim(0, 100)
    ax.set_title(
        "Round 2 (Oct 25) — official result", fontsize=11, loc="left", color=COLOR_TEXT
    )
    _style_axes(ax, grid_axis="x")

    fig.tight_layout()
    save(fig, "national_results")


def fig_zone_histogram(z2: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    shares = (100 * z2["p_r2"]).to_numpy()
    bins = np.arange(0, 101, 2)
    ax.hist(
        shares,
        bins=bins,
        color=COLOR_MUTED,
        alpha=0.9,
        edgecolor=SURFACE,
        linewidth=0.3,
    )
    ax.axvline(90, color=COLOR_LULA, linestyle="--", linewidth=1.3)
    ax.axvline(10, color=COLOR_FLAVIO, linestyle="--", linewidth=1.3)
    n_lula90 = int((shares >= 90).sum())
    n_flavio90 = int((shares <= 10).sum())
    ax.text(
        90.5,
        ax.get_ylim()[1] * 0.92,
        f"{n_lula90} zones\n≥90% Lula",
        color=COLOR_LULA,
        fontsize=9,
        ha="left",
    )
    ax.text(
        9.5,
        ax.get_ylim()[1] * 0.92,
        f"{n_flavio90} zones\n≤90% Flávio",
        color=COLOR_FLAVIO,
        fontsize=9,
        ha="right",
    )
    ax.set_xlabel("Lula's share of the two-candidate vote in the zone (%)")
    ax.set_ylabel("Number of electoral zones")
    ax.set_title(
        f"Distribution of round-2 results across all {len(z2):,} electoral zones",
        fontsize=11,
        loc="left",
    )
    _style_axes(ax)
    fig.tight_layout()
    save(fig, "zone_histogram")


def fig_funnel(z2: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    landslide = (z2["p_r2"] >= 0.90) | (z2["p_r2"] <= 0.10)
    normal = z2[~landslide]
    extreme = z2[landslide]
    ax.scatter(
        normal["n_r2"],
        100 * normal["p_r2"],
        s=7,
        color=COLOR_MUTED,
        alpha=0.35,
        linewidths=0,
        label="All other zones",
        rasterized=True,
    )
    ax.scatter(
        extreme["n_r2"],
        100 * extreme["p_r2"],
        s=22,
        color=COLOR_ACCENT,
        alpha=0.9,
        linewidths=0,
        label="≥90% for one candidate",
        rasterized=True,
    )
    ax.set_xscale("log")
    ax.axhline(90, color=COLOR_MUTED, linestyle=":", linewidth=1)
    ax.axhline(10, color=COLOR_MUTED, linestyle=":", linewidth=1)
    ax.axhline(51.79, color=COLOR_TEXT, linestyle="-", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Zone size (two-candidate valid votes, log scale)")
    ax.set_ylabel("Lula's share of the two-candidate vote (%)")
    ax.set_title(
        "Landslide zones span the normal range of zone sizes", fontsize=11, loc="left"
    )
    ax.set_ylim(-2, 102)
    _style_axes(ax)
    ax.legend(frameon=False, loc="center left", fontsize=9, bbox_to_anchor=(1.01, 0.5))
    fig.tight_layout()
    save(fig, "funnel")


def fig_r1_vs_r2(z2: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    sub = z2.dropna(subset=["p_r1_twoparty"])
    landslide = (sub["p_r2"] >= 0.90) | (sub["p_r2"] <= 0.10)
    ax.scatter(
        100 * sub.loc[~landslide, "p_r1_twoparty"],
        100 * sub.loc[~landslide, "p_r2"],
        s=6,
        color=COLOR_MUTED,
        alpha=0.3,
        linewidths=0,
        rasterized=True,
    )
    ax.scatter(
        100 * sub.loc[landslide, "p_r1_twoparty"],
        100 * sub.loc[landslide, "p_r2"],
        s=22,
        color=COLOR_ACCENT,
        alpha=0.9,
        linewidths=0,
        label="≥90% in round 2",
        rasterized=True,
    )
    ax.plot(
        [0, 100], [0, 100], color=COLOR_TEXT, linewidth=0.8, alpha=0.5, linestyle="--"
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Lula's 2-candidate share in round 1 (%)")
    ax.set_ylabel("Lula's share in round 2 (%)")
    ax.set_title(
        "Round-2 landslide zones sit on the round-1 diagonal", fontsize=11, loc="left"
    )
    _style_axes(ax)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.tight_layout()
    save(fig, "r1_vs_r2")


def fig_monte_carlo(summary: dict, sims: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))

    def panel(ax, sims_arr, actual, label, color):
        bins = np.arange(sims_arr.min(), sims_arr.max() + 2) - 0.5
        ax.hist(
            sims_arr,
            bins=bins,
            color=COLOR_MUTED,
            alpha=0.85,
            edgecolor=SURFACE,
            linewidth=0.3,
        )
        ax.axvline(actual, color=color, linewidth=2)
        ax.text(
            actual,
            ax.get_ylim()[1] * 0.95,
            f"  actual = {actual}",
            color=color,
            fontsize=9,
            va="top",
            ha="left" if actual < sims_arr.mean() else "right",
        )
        ax.set_title(label, fontsize=10.5, loc="left")
        ax.set_xlabel("Simulated count of zones (per trial)")
        _style_axes(ax)

    panel(
        axes[0],
        np.array(sims["sims_lula90"]),
        summary["monte_carlo"]["actual_lula_ge90"],
        "Zones with Lula ≥90% (chance model vs. actual)",
        COLOR_LULA,
    )
    panel(
        axes[1],
        np.array(sims["sims_flavio90"]),
        summary["monte_carlo"]["actual_flavio_ge90"],
        "Zones with Flávio ≥90% (chance model vs. actual)",
        COLOR_FLAVIO,
    )
    axes[0].set_ylabel(f"Simulated trials (of {summary['monte_carlo']['n_sim']:,})")
    fig.tight_layout()
    save(fig, "monte_carlo")


def fig_swing(z2: pd.DataFrame, corr: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))

    ax = axes[0]
    swing_pts = 100 * z2["swing_r1_to_r2"].dropna()
    ax.hist(
        swing_pts,
        bins=60,
        color=COLOR_ACCENT,
        alpha=0.85,
        edgecolor=SURFACE,
        linewidth=0.2,
    )
    ax.axvline(swing_pts.mean(), color=COLOR_TEXT, linewidth=1, linestyle="--")
    ax.set_xlabel("Zone swing to Lula, round 1 → 2 (pts)")
    ax.set_ylabel("Number of zones")
    ax.set_title(
        "Zone-level swing is centered near the\nnational average, with normal spread",
        fontsize=10.5,
        loc="left",
    )
    _style_axes(ax)

    ax = axes[1]
    sub = z2.dropna(subset=["turnout_rate_delta", "swing_r1_to_r2"])
    sub = sub.sample(min(4000, len(sub)), random_state=1)
    ax.scatter(
        100 * sub["turnout_rate_delta"],
        100 * sub["swing_r1_to_r2"],
        s=5,
        color=COLOR_MUTED,
        alpha=0.25,
        linewidths=0,
        rasterized=True,
    )
    xs = np.linspace(
        sub["turnout_rate_delta"].min(), sub["turnout_rate_delta"].max(), 50
    )
    slope, intercept = np.polyfit(sub["turnout_rate_delta"], sub["swing_r1_to_r2"], 1)
    ax.plot(100 * xs, 100 * (slope * xs + intercept), color=COLOR_ACCENT, linewidth=2)
    ax.set_xlabel("Turnout-rate change, round 1 → 2 (pts)")
    ax.set_ylabel("Swing to Lula (pts)")
    ax.set_title(
        f"r = {corr['pearson_r']:.3f}  (n = {corr['n']:,}, p = {corr['p_value']:.1e})",
        fontsize=10.5,
        loc="left",
    )
    _style_axes(ax)

    fig.tight_layout()
    save(fig, "swing")


def fig_digit_test(summary: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0))
    for ax, key, color, title in [
        (
            axes[0],
            "last_digit_test_lula_r2",
            COLOR_LULA,
            "Last digit of Lula's zone vote counts",
        ),
        (
            axes[1],
            "last_digit_test_flavio_r2",
            COLOR_FLAVIO,
            "Last digit of Flávio's zone vote counts",
        ),
    ]:
        d = summary[key]
        digits = np.arange(10)
        ax.bar(digits, d["observed"], color=color, alpha=0.85, width=0.65)
        ax.axhline(
            d["expected_per_digit"], color=COLOR_TEXT, linestyle="--", linewidth=1
        )
        ax.set_xticks(digits)
        ax.set_xlabel("Last digit of vote count")
        ax.set_title(
            f"{title}\nχ²={d['chi2']:.2f}, p={d['p_value']:.2f} (n={d['n']:,})",
            fontsize=10,
            loc="left",
        )
        _style_axes(ax)
    axes[0].set_ylabel("Zones")
    fig.tight_layout()
    save(fig, "digit_test")


def fig_state_swing(summary: dict) -> None:
    df = pd.DataFrame(summary["state_table"])
    df = df[df["sg_uf"] != "ZZ"].sort_values("p_r2")
    fig, ax = plt.subplots(figsize=(7, 9))
    y = np.arange(len(df))
    ax.scatter(
        100 * df["p_r1_twoparty"],
        y,
        color=COLOR_MUTED,
        s=35,
        zorder=3,
        label="Round 1 (2-cand. share)",
    )
    ax.scatter(100 * df["p_r2"], y, color=COLOR_ACCENT, s=35, zorder=3, label="Round 2")
    for yi, (x1, x2) in enumerate(zip(100 * df["p_r1_twoparty"], 100 * df["p_r2"])):
        ax.plot([x1, x2], [yi, yi], color=COLOR_MUTED, linewidth=1, alpha=0.6, zorder=2)
    ax.axvline(50, color=COLOR_TEXT, linewidth=0.8, alpha=0.4, linestyle=":")
    ax.set_yticks(y)
    ax.set_yticklabels(df["sg_uf"])
    ax.set_xlabel("Lula's share (%)")
    ax.set_title("State-level swing, round 1 → round 2", fontsize=11, loc="left")
    _style_axes(ax, grid_axis="x")
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.tight_layout()
    save(fig, "state_swing")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    summary = json.loads((ANALYSIS_DIR / "summary.json").read_text(encoding="utf-8"))
    z2 = pd.read_parquet(ANALYSIS_DIR / "zone_table.parquet")
    z2 = z2[z2["n_r2"] > 0]
    votes = pd.read_parquet(PROCESSED_DIR / "votes_candidate_munzona.parquet")
    sims = np.load(ANALYSIS_DIR / "monte_carlo_sims.npz")

    fig_national_results(summary, votes)
    fig_zone_histogram(z2)
    fig_funnel(z2)
    fig_r1_vs_r2(z2)
    fig_monte_carlo(summary, sims)
    fig_swing(z2, summary["swing_turnout_correlation"])
    fig_digit_test(summary)
    fig_state_swing(summary)

    print("Figures written to", FIG_DIR)


if __name__ == "__main__":
    main()
