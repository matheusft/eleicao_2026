# Data dictionary — Brazil 2026 presidential election results

Source: Tribunal Superior Eleitoral (TSE) open-data portal
(https://dadosabertos.tse.jus.br), package `resultados-2026`, resources
"Votação nominal por município e zona" and "Detalhe da apuração por
município e zona" (URLs and checksums in `data/raw/MANIFEST.csv`).

Both source zips contain one file per state plus one `_BR.csv` file. The
per-state files only carry state/district races (Governador, Senador,
Deputado Federal, Deputado Estadual) — zero `Presidente` rows. The
`_BR.csv` file in each zip already contains **only** the `Presidente`
race, for all 26 states + DF + votes cast abroad (`SG_UF = 'ZZ'`), both
rounds. So this pipeline reads only the `_BR.csv` member of each zip —
there is no BR/per-state duplication to reconcile for the presidential
race, and nothing is dropped by skipping the per-state files (they hold
no presidential data).

Encoding: TSE CSVs are `;`-separated, Latin-1, quoted. Placeholder values
`#NULO#`, `#NE#`, `-1`, `-3` are treated as missing (`<NA>`) wherever they
appear in a string or numeric code column.

Municipality codes: TSE's own `CD_MUNICIPIO` is kept in every table. The
IBGE 7-digit equivalent (`cd_municipio_ibge`) is added via a join against
the community-maintained crosswalk at
https://github.com/betafcc/Municipios-Brasileiros-TSE (TSE publishes no
official combined TSE/IBGE crosswalk file). One domestic municipality in
that crosswalk did not match: **Boa Esperança do Norte, MT** (TSE code
73709), because it was only officially installed 2025-01-01 (split from
Brasnorte) and postdates the crosswalk. It was patched in manually in
`scripts/crosswalk.py`, sourced from IBGE's own municipality page
(IBGE code 5101837). No other domestic municipality is unmatched.
Rows with `SG_UF = 'ZZ'` (votes cast abroad, at 186 distinct consular
voting locations) have no IBGE municipality and are flagged via
`is_abroad = true` with `cd_municipio_ibge` left null, rather than
dropped.

All five tables below are in `data/processed/`, as both `.csv` and
`.parquet`.

## votes_candidate_munzona
One row per round × municipality (or abroad voting location) × zone ×
candidate. Source: `votacao_candidato_munzona_2026_BR.csv`.

| column | type | description |
|---|---|---|
| ano_eleicao | Int64 | Election year (2026) |
| nr_turno | Int64 | Round: 1 (2026-10-04) or 2 (2026-10-25) |
| dt_eleicao | date | Date of this round |
| sg_uf | string | State code, or `ZZ` for votes cast abroad |
| cd_municipio | Int64 | TSE municipality/location code |
| nm_municipio | string | Municipality (or foreign city) name, as published by TSE |
| nr_zona | Int64 | Electoral zone number |
| sq_candidato | Int64 | TSE candidate sequence number (unique per candidacy) |
| nr_candidato | Int64 | Ballot number (e.g. 13, 22) |
| nm_candidato | string | Candidate's full legal name |
| nm_urna_candidato | string | Candidate's ballot ("urna") name |
| nr_partido | Int64 | Party number |
| sg_partido | string | Party acronym |
| nm_partido | string | Party full name |
| nr_federacao | Int64 | Party federation number (null if not in a federation) |
| sg_federacao | string | Federation acronym (null if not in a federation) |
| nm_federacao | string | Federation full name (null if not in a federation) |
| voto_em_transito | bool | Whether these are "voto em trânsito" votes (`ST_VOTO_EM_TRANSITO`) |
| qt_votos_nominais | Int64 | Valid votes for this candidate in this round/mun/zone |
| cd_sit_tot_turno | Int64 | Candidacy outcome code for this round (elected/not elected/runoff) |
| ds_sit_tot_turno | string | Candidacy outcome description |
| is_abroad | bool | True when `sg_uf == 'ZZ'` |
| cd_municipio_ibge | Int64 | IBGE municipality code (null for abroad rows) |

All rows had `NM_TIPO_DESTINACAO_VOTOS == 'Válido'` in the source (no
blank/null-vote rows mixed into the candidate file — those live only in
the turnout file), so that column was dropped as constant.

## turnout_munzona
One row per round × municipality (or abroad voting location) × zone.
Source: `detalhe_votacao_munzona_2026_BR.csv`.

| column | type | description |
|---|---|---|
| ano_eleicao | Int64 | Election year |
| nr_turno | Int64 | Round |
| dt_eleicao | date | Date of this round |
| sg_uf | string | State code, or `ZZ` |
| cd_municipio | Int64 | TSE municipality/location code |
| nm_municipio | string | Municipality (or foreign city) name |
| nr_zona | Int64 | Electoral zone number |
| qt_aptos | Int64 | Registered electorate (`QT_APTOS`) |
| qt_comparecimento | Int64 | Voters who showed up (`QT_COMPARECIMENTO`) |
| qt_abstencoes | Int64 | Abstentions (`QT_ABSTENCOES`) |
| qt_votos_validos | Int64 | Valid votes for the presidential race (`QT_TOTAL_VOTOS_VALIDOS`) |
| qt_votos_brancos | Int64 | Blank votes (`QT_VOTOS_BRANCOS`) |
| qt_votos_nulos | Int64 | Spoiled/null votes (`QT_TOTAL_VOTOS_NULOS`) |
| is_abroad | bool | True when `sg_uf == 'ZZ'` |
| cd_municipio_ibge | Int64 | IBGE municipality code (null for abroad rows) |

Reconciliation enforced at build time (see `scripts/validate.py`):
`qt_comparecimento == qt_votos_validos + qt_votos_brancos + qt_votos_nulos`
and the sum of `qt_votos_nominais` in `votes_candidate_munzona` equals
`qt_votos_validos` here, for every (round, uf, municipio, zona).

## results_municipality
One row per round × municipality (or abroad location), wide format:
turnout figures plus one `votos_<candidate_slug>` and one
`pct_votos_validos_<candidate_slug>` column per candidate who ran in
either round (candidates absent from a given round show 0 votes / 0%
there). `<candidate_slug>` is the candidate's ballot name
(`nm_urna_candidato`), lowercased with accents stripped and
non-alphanumeric characters collapsed to `_`. Built by summing
`votes_candidate_munzona` and `turnout_munzona` across zones within each
municipality.

Candidate columns present (round 1 had 12 candidates; round 2 had only
Lula and Flávio Bolsonaro, so every other candidate's round-2 column is 0):
`votos_lula`, `votos_flavio_bolsonaro`, `votos_ronaldo_caiado`,
`votos_zema`, `votos_escritor_augusto_cury`, `votos_clariana_barao`,
`votos_veterinario_wilson_grassi`, `votos_renan_santos`,
`votos_rui_costa_pimenta`, `votos_edmilson_costa`, `votos_hertz_dias`,
`votos_samara` (plus the matching `pct_votos_validos_*` columns).

`pct_votos_validos_*` = candidate's votes ÷ `qt_votos_validos`, rounded to
6 decimals.

## results_state
Same shape as `results_municipality`, aggregated to round × `sg_uf`.
`ZZ` (abroad) is kept as its own row — it is not a Brazilian state, but
is retained rather than dropped, consistent with keeping abroad votes
flagged throughout the pipeline.

## results_national
Same shape, aggregated to round only (one row per round).

## Validation summary
See `scripts/validate.py` for the automated checks and
`README.md` for how to re-run them. As of this build: round-2 national
totals matched TSE's official announcement exactly (Lula 64,256,232 /
51.79%; Flávio Bolsonaro 59,826,041 / 48.21%); abstention matched
official figures (round 1 ≈21.08%, round 2 ≈19.22%); no reconciliation
mismatches; no duplicate municipality rows.
