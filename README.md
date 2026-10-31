# Brazil 2026 presidential election — results pipeline & statistical forensics report

Two things live in this repo:

1. A data pipeline that builds an analysis-ready dataset of the official
   2026 Brazilian presidential election results (round 1: 2026-10-04,
   round 2: 2026-10-25) from TSE's open-data portal
   (https://dadosabertos.tse.jus.br), using only official TSE sources for
   the vote/turnout data.
2. A statistical forensics report built on top of that dataset —
   [`report/2026_election_forensics_report.html`](report/2026_election_forensics_report.html)
   — an interactive, bilingual (English/Portuguese), light/dark-aware page
   that tests whether round-2 landslide results are statistically unusual,
   via a Monte Carlo chance model, round-1↔round-2 consistency checks, an
   ecological vote-transfer estimate, digit-based forensic tests, and a
   data-integrity audit, each with its reasoning, caveats and limitations
   stated in plain language. Open the file directly in a browser — it's
   fully self-contained (no server, no build step, no external requests).

## What it produces

In `data/processed/` (CSV + Parquet each):

- `votes_candidate_munzona` — round × municipality × zone × candidate
- `turnout_munzona` — round × municipality × zone, electorate/turnout/abstention/blank/spoiled
- `results_municipality` — round × municipality, wide (one column per candidate + turnout)
- `results_state` — same, aggregated to round × state (abroad votes kept as `sg_uf='ZZ'`)
- `results_national` — same, aggregated to round only
- `DATA_DICTIONARY.md` — column-by-column description and transformation notes

## How the source files were found

Via TSE's CKAN API (no URLs were guessed):

```
curl "https://dadosabertos.tse.jus.br/api/3/action/package_search?q=resultados%202026"
curl "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026"
```

This located package `resultados-2026`, which lists
`votacao_candidato_munzona_2026.zip` and `detalhe_votacao_munzona_2026.zip`
among its resources. `votacao_secao_2026_*.zip` (polling-station level)
is also listed but was not downloaded, per the original brief, since it
wasn't confirmed as needed.

Each zip contains per-state files (state/district races only — no
presidential rows) plus a `_BR.csv` file that already contains, by
itself, the complete presidential race across every state + DF + abroad
votes, both rounds. See `DATA_DICTIONARY.md` for how this was verified.

## Setup

```bash
python3 -m venv .venv_eleicao
.venv_eleicao/bin/pip install -r requirements.txt
```

## Running the pipeline

```bash
cd scripts
../.venv_eleicao/bin/python3 run_all.py
```

This runs, in order:

1. `download.py` — re-queries the CKAN API for the current resource URLs,
   downloads the two zips plus the TSE-IBGE municipality crosswalk into
   `data/raw/`, and writes `data/raw/MANIFEST.csv` (url, download time,
   size, SHA-256 for each file).
2. `extract.py` — extracts the `_BR.csv` member of each zip into
   `data/raw/extracted/<dataset>/`. The raw zips are never modified.
3. `build_datasets.py` — reads the Latin-1/`;`-separated CSVs, cleans TSE
   null placeholders, filters to the presidential race (defensively
   asserted, not assumed), joins the IBGE municipality code, and writes
   the five processed tables.
4. `validate.py` — checks national round-2 totals against TSE's official
   announcement, abstention rates, internal reconciliation (candidate
   votes + blank + spoiled == turnout), and duplicate-municipality
   checks. Raises on any mismatch rather than silently passing.

Steps can also be run individually, e.g. `../.venv_eleicao/bin/python3 build_datasets.py`,
as long as the previous step's output already exists.

## Regenerating the forensics report

Once `data/processed/` exists (previous section), the report is built by
three more scripts, run from `scripts/` in order:

```bash
../.venv_eleicao/bin/python3 fraud_analysis.py     # statistical tests -> data/analysis/summary.json
../.venv_eleicao/bin/python3 export_chart_data.py  # packages chart data -> data/analysis/chart_data.json
../.venv_eleicao/bin/python3 render_report.py      # renders -> report/2026_election_forensics_report.html
```

- `fraud_analysis.py` runs every statistical test shown in the report
  (data-integrity reconciliation, the Monte Carlo landslide-chance model
  and its robustness variants, the round-1↔round-2 consistency check, the
  ecological vote-transfer regression, the turnout/swing correlation,
  last-digit tests, blank/null vote rates) and writes every number to
  `data/analysis/summary.json` — nothing in the report's text is
  hand-typed, it's all read from this file.
- `export_chart_data.py` packages the zone-level data the *interactive*
  charts need (hover tooltips, etc.) into `data/analysis/chart_data.json`,
  embedded directly in the final HTML.
- `render_report.py` renders the bilingual (EN/PT) HTML page, embedding
  `scripts/assets/report_charts.js` + `report_app.js` (a small
  dependency-free charting toolkit) and `chart_data.json` inline, so the
  output file is fully self-contained.
- `make_figures.py` is a separate, optional script that renders static
  matplotlib SVG versions of some charts into `data/analysis/figures/`;
  it's a non-interactive fallback and isn't used by the HTML report.

`data/analysis/` (summary.json, chart_data.json, the zone-level parquet,
Monte Carlo simulation draws, static figures) is regenerated output and
is gitignored, same as `data/raw/` and `data/processed/`.

## Notes

- `data/raw/*.zip` are the unmodified files as downloaded from
  `cdn.tse.jus.br`; `data/raw/MANIFEST.csv` records their provenance.
- One domestic municipality (Boa Esperança do Norte, MT — installed
  2025-01-01) was missing from the community TSE/IBGE crosswalk and was
  patched in manually in `scripts/crosswalk.py`; see `DATA_DICTIONARY.md`.
- Re-running `download.py` re-fetches the resource URLs from the CKAN API
  each time rather than hardcoding them, so it stays correct if TSE
  reorganizes the portal.

## License

This project's code is licensed under the [MIT License](LICENSE). The
underlying election data is public information published by TSE
(Tribunal Superior Eleitoral) and is not covered by this license.
