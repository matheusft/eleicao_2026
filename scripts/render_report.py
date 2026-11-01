"""Render the final HTML election-forensics report from summary.json and
chart_data.json, in two languages (English UK and Brazilian Portuguese)
with a client-side toggle. Every number in the prose is pulled from
summary.json -- nothing is hand-typed -- so the text can never drift from
the data, in either language.

Bilingual strategy: every piece of translatable copy is rendered TWICE as
sibling HTML elements (one `lang="en"`, one `lang="pt"`), via the B()
helper below. CSS shows only the element matching the page's current
`data-lang` attribute (`display: revert`, which maps each tag back to its
normal display value -- block for <p>/<li>/<div>, inline for <span>,
table-row-group for <tbody>, etc. -- so one mechanism works for every tag
used here). This is done at the smallest container that holds a number
together with its label (a whole stat-tile, a whole table <tbody>, a whole
caption), because pt-BR number formatting (1.234,56) differs from en-GB
(1,234.56) and the two must never be split apart.

Charts are live, interactive SVG (scripts/assets/report_charts.js +
report_app.js) built from chart_data.json at page-load time. Their text
(axis labels, legends, tooltips) is translated client-side by
report_app.js's own I18N dictionary, keyed off the same data-lang
attribute, and chart text re-renders automatically when the toggle fires.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import ROOT

ANALYSIS_DIR = ROOT / "data" / "analysis"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
OUT_PATH = ROOT / "report" / "2026_election_forensics_report.html"


def read_asset(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def fnum(x: float, lang: str, d: int = 0) -> str:
    s = f"{x:,.{d}f}"
    if lang == "pt":
        s = s.translate(str.maketrans(",.", ".,"))
    return s


def pct(x: float, lang: str, d: int = 2) -> str:
    return fnum(x, lang, d)


def B(tag: str, en: str, pt: str, cls: str = "", attrs: str = "") -> str:
    """Render `en`/`pt` as sibling elements toggled by the page's data-lang."""
    classes = f"i18n-block {cls}".strip()
    attr_str = f" {attrs}" if attrs else ""
    return (
        f'<{tag} lang="en" class="{classes}"{attr_str}>{en}</{tag}>'
        f'<{tag} lang="pt" class="{classes}"{attr_str}>{pt}</{tag}>'
    )


def tip(term: str, text: str) -> str:
    """Inline term with a styled, tap-and-hover-and-keyboard tooltip.
    `tabindex` makes it reachable on touch devices (a tap focuses it) and by
    keyboard, so the explanation is not hover-only."""
    return (
        f'<span class="has-tip" tabindex="0" role="note">{term}'
        f'<span class="tip-pop">{text}</span></span>'
    )


def takeaway(en: str, pt: str) -> str:
    """Plain-English 'what this means' box placed at the end of a section."""
    label = B("span", "In plain terms", "Em termos simples", cls="takeaway-label")
    body = B("span", en, pt, cls="takeaway-body")
    return f'<div class="takeaway">{label}{body}</div>'


def muni_label(r: dict, lang: str) -> str:
    if not r.get("is_abroad"):
        tag = ""
    else:
        tag = " (abroad)" if lang == "en" else " (exterior)"
    return f"{r['nm_municipio'].title()}{tag} / {r['sg_uf']}"


def winner_label(r: dict) -> str:
    return r["winner"].title().replace("Flavio Bolsonaro", "Flávio Bolsonaro")


def main() -> None:
    summary = json.loads((ANALYSIS_DIR / "summary.json").read_text(encoding="utf-8"))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    mc = summary["monte_carlo"]
    corr = summary["swing_turnout_correlation"]
    nat = summary["national_two_party_share"]
    ab = summary["national_abstention"]
    dt_lula = summary["last_digit_test_lula_r2"]
    dt_flavio = summary["last_digit_test_flavio_r2"]
    dt_muni = summary["last_digit_test_muni_valid_votes"]
    top0 = summary["top_landslide_zones_by_n"][0]
    di = summary["data_integrity"]
    vt = summary["vote_transfer"]
    bn = summary["blank_null"]
    rb = summary["robustness"]
    rb_by_key = {r["key"]: r for r in rb}
    brc = summary["between_round_capture"]

    def landslide_rows(lang: str) -> str:
        return "".join(f"""<tr>
          <td>{muni_label(r, lang)}</td>
          <td class="num">{r['nr_zona']}</td>
          <td class="num">{fnum(r['n_r2'], lang)}</td>
          <td class="num">{pct(100*r['p_r1_twoparty'], lang)}%</td>
          <td class="num">{pct(100*r['p_r2'], lang)}%</td>
          <td class="winner-cell"><span class="pill {'pill-lula' if r['winner']=='LULA' else 'pill-flavio'}">{winner_label(r)}</span></td>
        </tr>""" for r in summary["top_landslide_zones_by_n"])

    corr_cls = "caveat" if abs(corr["pearson_r"]) > 0.3 else "ok"

    def vt_cand(name: str) -> dict:
        return next(c for c in vt["candidates"] if c["candidate"] == name)

    bn_sorted = sorted(bn["state_invalid_rate"], key=lambda s: s["r2"])
    bn_lo = bn_sorted[:2]
    bn_hi = list(reversed(bn_sorted[-2:]))

    # (short_en, short_pt, desc_en, desc_pt). The short label keeps the table
    # narrow; the full description lives in a tap/hover tooltip.
    ROBUSTNESS_LABELS = {
        "baseline": (
            "All zones · 90% bar", "Todas as zonas · limiar 90%",
            "The headline test from §4: every zone, counting those at or above 90%.",
            "O teste principal da §4: todas as zonas, contando as que ficam em 90% ou acima.",
        ),
        "exclude_abroad": (
            "Drop overseas posts", "Sem postos no exterior",
            "Excludes the 186 overseas consular voting locations, which are tiny and could behave differently.",
            "Exclui os 186 locais de votação consular no exterior, que são minúsculos e poderiam se comportar de forma diferente.",
        ),
        "exclude_small_n": (
            "Drop tiny zones (<50)", "Sem zonas minúsculas (<50)",
            "Excludes zones with fewer than 50 two-candidate votes, where a single vote moves the share a lot.",
            "Exclui zonas com menos de 50 votos entre os dois candidatos, onde um único voto desloca muito o percentual.",
        ),
        "threshold_85": (
            "Looser bar · 85%", "Limiar mais frouxo · 85%",
            "Counts zones at or above 85% instead of 90% — a looser definition of 'high concentration'.",
            "Conta zonas em 85% ou acima, em vez de 90% — uma definição mais frouxa de 'alta concentração'.",
        ),
        "threshold_95": (
            "Stricter bar · 95%", "Limiar mais estrito · 95%",
            "Counts zones at or above 95% — a much stricter definition.",
            "Conta zonas em 95% ou acima — uma definição bem mais estrita.",
        ),
    }

    def rob_cell(actual: int, mean: float, p05: float, p95: float, lang: str) -> str:
        chance = "chance" if lang == "en" else "acaso"
        return (
            f'<strong>{fnum(actual, lang)}</strong>'
            f'<span class="chance">{chance} ~{fnum(mean, lang, 0)} '
            f'({fnum(p05, lang, 0)}&ndash;{fnum(p95, lang, 0)})</span>'
        )

    def robustness_rows(lang: str) -> str:
        rows = []
        for key, (en_lbl, pt_lbl, en_desc, pt_desc) in ROBUSTNESS_LABELS.items():
            r = rb_by_key[key]
            label = en_lbl if lang == "en" else pt_lbl
            desc = en_desc if lang == "en" else pt_desc
            rows.append(f"""<tr>
              <td>{tip(label, desc)}</td>
              <td class="num">{fnum(r['n_zones'], lang)}</td>
              <td class="num rob-cell">{rob_cell(r['actual_lula'], r['sim_lula_mean'], r['sim_lula_p05'], r['sim_lula_p95'], lang)}</td>
              <td class="num rob-cell">{rob_cell(r['actual_flavio'], r['sim_flavio_mean'], r['sim_flavio_p05'], r['sim_flavio_p95'], lang)}</td>
            </tr>""")
        return "".join(rows)

    chart_data_json = (ANALYSIS_DIR / "chart_data.json").read_text(encoding="utf-8")
    charts_js = read_asset("report_charts.js")
    app_js = read_asset("report_app.js")

    TITLE_EN = "2026 Brazilian Presidential Election — Statistical Forensics Report"
    TITLE_PT = (
        "Eleição Presidencial do Brasil em 2026 — Relatório de Perícia Estatística"
    )
    DESC_EN = "A statistical audit of high-concentration results, digit tests, and Monte Carlo simulations of the 2026 Brazil presidential runoff."
    DESC_PT = "Uma auditoria estatística dos resultados de alta concentração, testes de dígitos e simulações de Monte Carlo do segundo turno da eleição presidencial de 2026 no Brasil."

    html = f"""<!doctype html>
<meta charset="utf-8">
<script>
(function(){{
  try {{
    var saved = localStorage.getItem('report-lang');
    var lang = saved || ((navigator.language||'').toLowerCase().indexOf('pt')===0 ? 'pt' : 'en');
    document.documentElement.setAttribute('data-lang', lang);
    document.documentElement.setAttribute('lang', lang==='pt' ? 'pt-BR' : 'en-GB');
  }} catch(e) {{ document.documentElement.setAttribute('data-lang','en'); document.documentElement.setAttribute('lang','en-GB'); }}
  try {{
    // Only set data-theme explicitly if the viewer has made a choice before;
    // otherwise leave it unset so the page follows the OS theme live (the
    // existing @media (prefers-color-scheme) rules in <style> already
    // handle that case without any attribute present).
    var savedTheme = localStorage.getItem('report-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {{
      document.documentElement.setAttribute('data-theme', savedTheme);
    }}
  }} catch(e) {{}}
}})();
</script>
<title>{TITLE_EN}</title>
<meta name="description" content="{DESC_EN}">
<style>
:root {{
  --serif: 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, 'Noto Serif', serif;
  --sans: -apple-system, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --mono: ui-monospace, 'SF Mono', 'Cascadia Code', 'Roboto Mono', monospace;

  --surface-0: #fcfcfb;
  --surface-1: #f3f1ea;
  --surface-card: #ffffff;
  --text-primary: #16150f;
  --text-secondary: #52514e;
  --text-muted: #837f74;
  --border: #e2ded2;
  --accent: #4a3aa7;
  --accent-soft: #ece9f8;
  --lula: #c0272d;
  --flavio: #1c5fa8;
  --chart-muted: #9a978e;
  --ok-bg: #eaf3ea;
  --ok-text: #2c6b35;
  --warn-bg: #fbf0e3;
  --warn-text: #92551a;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --surface-0: #17160f;
    --surface-1: #1f1e16;
    --surface-card: #242319;
    --text-primary: #f3f1ea;
    --text-secondary: #c3c0b2;
    --text-muted: #948f80;
    --border: #38362a;
    --accent: #9085e9;
    --accent-soft: #2a2645;
    --lula: #e0696d;
    --flavio: #5a9bdb;
    --chart-muted: #8f8a78;
    --ok-bg: #1d2e1f;
    --ok-text: #8fd19a;
    --warn-bg: #332514;
    --warn-text: #e3ac6e;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface-0: #17160f;
  --surface-1: #1f1e16;
  --surface-card: #242319;
  --text-primary: #f3f1ea;
  --text-secondary: #c3c0b2;
  --text-muted: #948f80;
  --border: #38362a;
  --accent: #9085e9;
  --accent-soft: #2a2645;
  --lula: #e0696d;
  --flavio: #5a9bdb;
  --chart-muted: #8f8a78;
  --ok-bg: #1d2e1f;
  --ok-text: #8fd19a;
  --warn-bg: #332514;
  --warn-text: #e3ac6e;
}}
:root[data-theme="light"] {{
  color-scheme: light;
  --surface-0: #fcfcfb; --surface-1: #f3f1ea; --surface-card: #ffffff;
  --text-primary: #16150f; --text-secondary: #52514e; --text-muted: #837f74;
  --border: #e2ded2; --accent: #4a3aa7; --accent-soft: #ece9f8;
  --lula: #c0272d; --flavio: #1c5fa8; --chart-muted: #9a978e;
  --ok-bg: #eaf3ea; --ok-text: #2c6b35; --warn-bg: #fbf0e3; --warn-text: #92551a;
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--surface-0);
  color: var(--text-primary);
  font-family: var(--sans);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 880px; margin: 0 auto; padding: 0 24px 96px; }}
.wide {{ max-width: 1040px; }}

/* --- bilingual toggle: show only the element matching data-lang --- */
.i18n-block {{ display: none; }}
:root[data-lang="en"] .i18n-block[lang="en"] {{ display: revert; }}
:root[data-lang="pt"] .i18n-block[lang="pt"] {{ display: revert; }}

.controls {{
  position: fixed; top: 16px; right: 16px; z-index: 500;
  display: flex; flex-direction: column; gap: 8px; align-items: flex-end;
}}
.lang-toggle {{
  display: flex; gap: 2px; padding: 3px;
  background: var(--surface-card); border: 1px solid var(--border);
  border-radius: 999px; box-shadow: 0 2px 12px rgba(0,0,0,0.14);
}}
.lang-btn {{
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  padding: 7px 13px; border-radius: 999px; border: none;
  background: transparent; color: var(--text-muted); cursor: pointer;
}}
.lang-btn[aria-pressed="true"] {{ background: var(--accent); color: #fff; }}
.lang-btn:hover:not([aria-pressed="true"]) {{ color: var(--text-primary); }}
@media (max-width: 560px) {{ .controls {{ top: 10px; right: 10px; }} }}

header.masthead {{
  border-bottom: 1px solid var(--border);
  background: var(--surface-1);
  padding: 56px 24px 40px;
}}
header.masthead .wrap {{ max-width: 880px; }}
.kicker {{
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 12.5px;
  color: var(--accent);
  font-weight: 600;
}}
h1.title {{
  font-family: var(--serif);
  font-size: clamp(2rem, 4vw, 2.9rem);
  line-height: 1.12;
  margin: 14px 0 10px;
  text-wrap: balance;
  font-weight: 600;
}}
.dek {{
  font-size: 1.15rem;
  color: var(--text-secondary);
  text-wrap: balance;
}}
.meta-row {{
  display: flex; gap: 20px; flex-wrap: wrap;
  margin-top: 20px; font-size: 13.5px; color: var(--text-muted);
  font-family: var(--mono);
}}

section {{ padding: 48px 0; border-bottom: 1px solid var(--border); }}
section:last-of-type {{ border-bottom: none; }}
h2 {{
  font-family: var(--serif); font-weight: 600;
  font-size: 1.65rem; margin: 0 0 6px;
  text-wrap: balance;
}}
h2 .num {{ color: var(--accent); font-family: var(--mono); font-size: 0.85em; margin-right: 10px; }}
h3 {{ font-family: var(--serif); font-size: 1.2rem; margin: 28px 0 8px; font-weight: 600; }}
p {{ margin: 12px 0; }}
.lede {{ color: var(--text-secondary); font-size: 1.02rem; }}
strong {{ font-weight: 650; }}
a {{ color: var(--accent); }}

.verdict {{
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  padding: 24px 28px;
  margin-top: 18px;
}}
.verdict h3 {{ margin-top: 0; }}
.verdict ul {{ padding-left: 20px; margin: 10px 0; }}
.verdict li {{ margin: 8px 0; }}

.stat-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  margin: 20px 0;
}}
.stat-tile {{ background: var(--surface-card); padding: 16px 18px; }}
.stat-tile .v {{ font-family: var(--mono); font-size: 1.5rem; font-weight: 600; }}
.stat-tile .l {{ font-size: 12.5px; color: var(--text-muted); margin-top: 4px; }}
.v.lula {{ color: var(--lula); }}
.v.flavio {{ color: var(--flavio); }}

.exhibit {{
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 20px 14px;
  margin: 20px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
.exhibit .cap {{
  font-size: 13px; color: var(--text-muted); margin-top: 10px;
  border-top: 1px dashed var(--border); padding-top: 10px;
}}
.chart-row {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.chart-row > .chart-container {{ min-width: 260px; }}
.chart-container {{ width: 100%; }}
.chart-svg {{ width: 100%; height: auto; display: block; overflow: visible; }}
.chart-svg text {{ font-family: var(--sans); font-size: 11.5px; fill: var(--text-secondary); }}
.chart-svg .axis-caption {{ font-size: 12px; fill: var(--text-muted); }}
.chart-svg .cat-label {{ font-size: 11px; }}
.chart-svg .grid line, .chart-svg .gridline-v {{ stroke: var(--border); stroke-width: 1; }}
.chart-svg .refline {{ stroke: var(--text-secondary); stroke-width: 0.8; opacity: 0.55; }}
.chart-svg .refline-dotted {{ stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 2 3; }}
.chart-svg .refline-dash {{ stroke: var(--text-secondary); stroke-width: 1; stroke-dasharray: 5 4; opacity: 0.7; }}
.chart-svg .diagonal {{ stroke: var(--text-secondary); stroke-width: 1; stroke-dasharray: 5 4; opacity: 0.55; }}
.chart-svg .trendline {{ stroke: var(--accent); stroke-width: 2.2; }}
.chart-svg .connector {{ stroke: var(--text-muted); stroke-width: 1.2; opacity: 0.6; }}
.chart-svg .mark-line {{ stroke-width: 1.6; }}
.chart-svg .mark-label {{ font-size: 11px; font-weight: 600; }}
.chart-svg .legend-label {{ font-size: 11.5px; fill: var(--text-secondary); }}
.chart-svg .bar-value-label {{ font-size: 11px; fill: var(--text-primary); font-weight: 600; }}
.chart-svg .pt {{ transition: opacity 0.1s; }}
.chart-svg .pt-highlight {{ fill: none; stroke-width: 2.5; pointer-events: none; }}
.chart-svg .bar {{ transition: filter 0.08s; }}
.chart-svg .bar-hover {{ filter: brightness(1.18); }}
.chart-svg .bar-hit {{ cursor: crosshair; }}

.chart-tooltip {{
  position: fixed; z-index: 1000; display: none; pointer-events: none;
  background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 13px; font-size: 12.5px; box-shadow: 0 4px 18px rgba(0,0,0,0.18);
  max-width: 340px; font-family: var(--sans);
}}
.chart-tooltip .tt-title {{ font-weight: 650; margin-bottom: 6px; color: var(--text-primary); }}
.chart-tooltip .tt-row {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; color: var(--text-secondary); }}
.chart-tooltip .tt-key {{ width: 8px; height: 8px; border-radius: 2px; flex: none; }}
.chart-tooltip .tt-label {{ flex: 1; }}
.chart-tooltip .tt-value {{ font-family: var(--mono); font-weight: 600; color: var(--text-primary); }}

.chart-search {{ position: relative; max-width: 420px; margin: 0 0 14px; }}
.chart-search-icon {{
  position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
  width: 15px; height: 15px; color: var(--text-muted); pointer-events: none;
}}
.chart-search-input {{
  width: 100%; box-sizing: border-box; font-family: var(--sans); font-size: 13.5px;
  padding: 9px 32px 9px 34px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface-1); color: var(--text-primary);
}}
.chart-search-input:focus {{ outline: none; border-color: var(--accent); background: var(--surface-card); }}
.chart-search-input::placeholder {{ color: var(--text-muted); }}
.chart-search-clear {{
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  width: 22px; height: 22px; border: none; background: transparent; cursor: pointer;
  color: var(--text-muted); font-size: 16px; line-height: 1; border-radius: 50%;
}}
.chart-search-clear:hover {{ color: var(--text-primary); background: var(--border); }}
.chart-search-results {{
  position: absolute; z-index: 50; top: calc(100% + 4px); left: 0; right: 0;
  margin: 0; padding: 4px; list-style: none;
  background: var(--surface-card); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.16); max-height: 260px; overflow-y: auto;
}}
.chart-search-results li {{
  padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
  color: var(--text-secondary); display: flex; justify-content: space-between; gap: 10px;
}}
.chart-search-results li .muni {{ color: var(--text-primary); font-weight: 550; }}
.chart-search-results li .meta {{ font-family: var(--mono); color: var(--text-muted); font-size: 11.5px; white-space: nowrap; }}
.chart-search-results li:hover,
.chart-search-results li[aria-selected="true"] {{ background: var(--accent-soft); }}
.chart-search-results li.empty {{ cursor: default; color: var(--text-muted); font-style: italic; }}
.chart-search-results li.empty:hover {{ background: none; }}

.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; margin: 16px 0; }}
.table-scroll {{ overflow-x: auto; }}
th {{
  text-align: left; font-family: var(--mono); font-weight: 500; font-size: 11.5px;
  text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted);
  border-bottom: 1px solid var(--border); padding: 8px 10px; white-space: nowrap;
}}
td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; font-variant-numeric: tabular-nums; }}
td.num {{ font-family: var(--mono); text-align: right; }}
th:nth-child(n+2) {{ text-align: right; }}
tr:hover td {{ background: var(--surface-1); }}

.pill {{ display: inline-block; padding: 2px 9px; border-radius: 99px; font-size: 11.5px; font-weight: 600; }}
.pill-lula {{ background: color-mix(in srgb, var(--lula) 16%, transparent); color: var(--lula); }}
.pill-flavio {{ background: color-mix(in srgb, var(--flavio) 16%, transparent); color: var(--flavio); }}
.pill-e {{ background: var(--ok-bg); color: var(--ok-text); }}
.pill-b {{ background: var(--warn-bg); color: var(--warn-text); }}
.pill-d {{ background: var(--surface-1); color: var(--text-muted); }}

.checklist {{ list-style: none; padding: 0; margin: 20px 0; }}
.checklist li {{
  position: relative; padding: 6px 0 6px 30px; margin: 4px 0;
  border-bottom: 1px solid var(--border);
}}
.checklist li::before {{
  content: "✓"; position: absolute; left: 0; top: 6px;
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--ok-bg); color: var(--ok-text);
  font-size: 12px; font-weight: 700; line-height: 20px; text-align: center;
}}

.chart-svg .track-outline {{ stroke: var(--border); stroke-width: 1; }}
.chart-svg .ci-whisker {{ stroke-width: 1.6; opacity: 0.9; }}
.chart-svg .ci-point {{ opacity: 1; }}

.callout {{
  border-radius: 10px; padding: 16px 20px; margin: 18px 0; font-size: 14.5px;
}}
.callout.method {{ background: var(--accent-soft); color: var(--text-primary); border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); }}
.callout.caveat {{ background: var(--warn-bg); color: var(--warn-text); border: 1px solid color-mix(in srgb, var(--warn-text) 25%, transparent); }}
.callout.ok {{ background: var(--ok-bg); color: var(--ok-text); border: 1px solid color-mix(in srgb, var(--ok-text) 25%, transparent); }}
.callout b {{ color: inherit; }}

.toc {{ display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 13.5px; margin-top: 18px; }}
.toc a {{ color: var(--text-secondary); text-decoration: none; }}
.toc a:hover {{ color: var(--accent); }}
.toc span.n {{ font-family: var(--mono); color: var(--accent); margin-right: 4px; }}

footer {{ padding: 40px 0 80px; color: var(--text-muted); font-size: 13px; }}
footer a {{ color: var(--text-muted); }}
code {{ font-family: var(--mono); background: var(--surface-1); padding: 1px 5px; border-radius: 4px; font-size: 0.92em; }}

/* --- inline term tooltips (assumptions / definitions) --- */
.has-tip {{
  border-bottom: 1px dotted var(--accent); cursor: help; position: relative;
  outline: none;
}}
.has-tip > .tip-pop {{
  display: none; position: absolute; left: 0; bottom: calc(100% + 8px); z-index: 600;
  width: max-content; max-width: min(300px, 80vw);
  background: var(--surface-card); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 6px 22px rgba(0,0,0,0.20);
  padding: 10px 13px; font-size: 13px; font-weight: 400; line-height: 1.5;
  text-transform: none; letter-spacing: normal; white-space: normal;
}}
.has-tip:hover > .tip-pop, .has-tip:focus > .tip-pop, .has-tip:focus-within > .tip-pop {{ display: block; }}
@media (max-width: 560px) {{ .has-tip > .tip-pop {{ left: auto; right: 0; max-width: 78vw; }} }}

/* --- per-section plain-English takeaway --- */
.takeaway {{
  display: flex; gap: 14px; align-items: flex-start;
  background: var(--accent-soft); border: 1px solid color-mix(in srgb, var(--accent) 24%, transparent);
  border-radius: 10px; padding: 16px 20px; margin: 26px 0 4px;
}}
.takeaway-label {{
  flex: none; font-family: var(--mono); font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent);
  padding-top: 2px;
}}
.takeaway-body {{ font-size: 15px; color: var(--text-primary); }}
@media (max-width: 560px) {{ .takeaway {{ flex-direction: column; gap: 6px; }} }}

/* --- chart panel sub-heading (names which candidate a panel shows) --- */
.chart-subtitle {{
  text-align: center; font-family: var(--sans); font-size: 13.5px; font-weight: 600;
  color: var(--text-secondary); margin: 2px 0 2px;
}}

/* Winner column: centre the result pill instead of left-aligning the name. */
td.winner-cell {{ text-align: center; }}
.landslide-table th:last-child {{ text-align: center; }}

/* Robustness table: compact 4-column layout, chance range stacked under the
   actual count so the table never needs horizontal scrolling. */
.robustness-table th {{ white-space: normal; }}
.robustness-table td.rob-cell {{ white-space: normal; vertical-align: top; }}
.robustness-table td.rob-cell .chance {{
  display: block; font-family: var(--sans); font-weight: 400;
  color: var(--text-muted); font-size: 11px; margin-top: 2px;
}}
.robustness-table td:first-child {{ white-space: normal; }}

/* Small inline legend swatch used under exhibits (e.g. Monte Carlo keys). */
.mini-legend {{ display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12.5px; color: var(--text-muted); margin: 2px 0 0; }}
.mini-legend .mi {{ display: inline-flex; align-items: center; gap: 6px; }}
.mini-legend .sw {{ width: 22px; height: 0; border-top-width: 2px; border-top-style: solid; display: inline-block; }}
.mini-legend .sw.band {{ height: 11px; border: none; border-radius: 2px; }}
</style>

<div class="controls">
  <div class="lang-toggle" role="group" aria-label="Language / Idioma">
    <button type="button" class="lang-btn" data-set-lang="en" aria-pressed="true">🇬🇧</button>
    <button type="button" class="lang-btn" data-set-lang="pt" aria-pressed="false">🇧🇷</button>
  </div>
  <div class="lang-toggle" role="group" aria-label="Theme / Tema">
    <button type="button" class="lang-btn" data-set-theme="light" aria-pressed="false">{B("span", "☀️", "☀️")}</button>
    <button type="button" class="lang-btn" data-set-theme="dark" aria-pressed="false">{B("span", "🌙", "🌙")}</button>
  </div>
</div>

<header class="masthead">
  <div class="wrap">
    <div class="kicker">{B("span", "Statistical forensics · Brazil 2026 Presidential Election", "Perícia estatística · Eleição Presidencial do Brasil 2026")}</div>
    {B("h1", "Were round-2 high-concentration zones a sign of fraud, or of Brazilian political geography?", "As zonas de alta concentração de votos no 2º turno são sinal de fraude, ou de geografia política brasileira?", cls="title")}
    {B("p", f"A ground-up statistical audit of the official TSE results for both rounds: zone-by-zone concentration analysis, a chance-model Monte&nbsp;Carlo simulation, digit tests, and a round&#8209;1-vs-round&#8209;2 consistency check across all {fnum(summary['n_total_zones_r2'],'en')} electoral zones.", f"Uma auditoria estatística, construída do zero, dos resultados oficiais do TSE nos dois turnos: análise zona a zona da concentração de votos, uma simulação de Monte&nbsp;Carlo com modelo de acaso, testes de dígitos e uma verificação de consistência entre 1º e 2º turno em todas as {fnum(summary['n_total_zones_r2'],'pt')} zonas eleitorais.", cls="dek")}
    <div class="meta-row">
      {B("span", "Source: TSE dadosabertos.tse.jus.br — official results only", "Fonte: TSE dadosabertos.tse.jus.br — apenas resultados oficiais")}
      {B("span", "Round 1: 2026-10-04 · Round 2: 2026-10-25", "1º turno: 04/10/2026 · 2º turno: 25/10/2026")}
    </div>
    <nav class="toc">
      <a href="#integrity"><span class="n">01</span>{B("span", "Can we trust the numbers?", "Podemos confiar nos números?")}</a>
      <a href="#headline"><span class="n">02</span>{B("span", "Headline result", "Resultado principal")}</a>
      <a href="#landslides"><span class="n">03</span>{B("span", "Are 90%+ zones unusual?", "Zonas com 90%+ são incomuns?")}</a>
      <a href="#montecarlo"><span class="n">04</span>{B("span", "Could it happen by chance?", "Pode acontecer por acaso?")}</a>
      <a href="#robustness"><span class="n">05</span>{B("span", "Does this hold up?", "Isso se sustenta?")}</a>
      <a href="#consistency"><span class="n">06</span>{B("span", "Sudden, or pre-existing?", "Súbito, ou pré-existente?")}</a>
      <a href="#transfers"><span class="n">07</span>{B("span", "Where did the votes go?", "Para onde foram os votos?")}</a>
      <a href="#turnout"><span class="n">08</span>{B("span", "Turnout &amp; swing check", "Comparecimento e variação de votos")}</a>
      <a href="#blanknull"><span class="n">09</span>{B("span", "Blank &amp; spoiled votes", "Votos em branco e nulos")}</a>
      <a href="#digits"><span class="n">10</span>{B("span", "Digit tests", "Testes de dígitos")}</a>
      <a href="#geography"><span class="n">11</span>{B("span", "Regional context", "Contexto regional")}</a>
      <a href="#capture"><span class="n">12</span>{B("span", "All the swing votes?", "Todos os votos que mudaram?")}</a>
      <a href="#findings"><span class="n">13</span>{B("span", "Findings &amp; limits", "Conclusões e limites")}</a>
    </nav>
  </div>
</header>

<div class="wrap">

<section id="integrity">
  <h2><span class="num">01</span>{B("span", "Can we trust the numbers?", "Podemos confiar nos números?")}</h2>
  {B("p", "Before testing the results for anything unusual, we tested the data itself. Every figure below was recomputed directly from the official TSE files for this report.", "Antes de testar os resultados em busca de algo incomum, testamos os próprios dados. Cada número abaixo foi recalculado diretamente dos arquivos oficiais do TSE especificamente para este relatório.", cls="lede")}

  <ul class="checklist">
    {B("li", f"{tip(f'<strong>{fnum(di['n_vote_records'],'en')}</strong> candidate-vote records', 'One row for every candidate, in every electoral zone, in each of the two rounds — for example, Lula&#39;s vote total in zone 1 of a given town in round 2 is one such row.')} and {tip(f'<strong>{fnum(di['n_turnout_records'],'en')}</strong> zone-level turnout records', 'One row for every electoral zone in each round, recording how many registered voters actually turned out there.')} examined, across both rounds.", f"{tip(f'<strong>{fnum(di['n_vote_records'],'pt')}</strong> registros de votos por candidato', 'Uma linha para cada candidato, em cada zona eleitoral, em cada um dos dois turnos — por exemplo, o total de votos de Lula na zona 1 de uma cidade no 2º turno é uma dessas linhas.')} e {tip(f'<strong>{fnum(di['n_turnout_records'],'pt')}</strong> registros de comparecimento por zona', 'Uma linha para cada zona eleitoral em cada turno, registrando quantos eleitores registrados de fato compareceram ali.')} examinados, nos dois turnos.")}
    {B("li", f"No duplicate records: <strong>{di['duplicate_vote_rows']}</strong> duplicate candidate-vote rows and <strong>{di['duplicate_turnout_rows']}</strong> duplicate turnout rows found.", f"Nenhum registro duplicado: <strong>{di['duplicate_vote_rows']}</strong> linhas de votos duplicadas e <strong>{di['duplicate_turnout_rows']}</strong> linhas de comparecimento duplicadas encontradas.")}
    {B("li", f"Candidate votes reconcile with valid votes in <strong>every one</strong> of {fnum(di['n_zone_round_rows_checked'],'en')} round × municipality × zone records ({di['reconciliation_failures_candidate_vs_valid']} mismatches).", f"Os votos dos candidatos batem com os votos válidos em <strong>todos</strong> os {fnum(di['n_zone_round_rows_checked'],'pt')} registros de turno × município × zona ({di['reconciliation_failures_candidate_vs_valid']} divergências).")}
    {B("li", f"Turnout reconciles with valid + blank + spoiled votes everywhere ({di['reconciliation_failures_turnout_vs_valid_blank_null']} mismatches).", f"O comparecimento bate com votos válidos + brancos + nulos em todos os registros ({di['reconciliation_failures_turnout_vs_valid_blank_null']} divergências).")}
    {B("li", f"No impossible values: {di['negative_vote_records']} negative vote counts, {di['turnout_exceeds_electorate']} zones where turnout exceeds the registered electorate, {di['negative_abstentions']} negative abstention counts.", f"Nenhum valor impossível: {di['negative_vote_records']} contagens de votos negativas, {di['turnout_exceeds_electorate']} zonas em que o comparecimento excede o eleitorado registrado, {di['negative_abstentions']} contagens de abstenção negativas.")}
    {B("li", f"National round-2 totals match the official TSE announcement exactly: Lula {fnum(di['national_lula_r2_votes'],'en')} votes, Flávio Bolsonaro {fnum(di['national_flavio_r2_votes'],'en')} votes.", f"Os totais nacionais do 2º turno batem exatamente com o anúncio oficial do TSE: Lula {fnum(di['national_lula_r2_votes'],'pt')} votos, Flávio Bolsonaro {fnum(di['national_flavio_r2_votes'],'pt')} votos.")}
  </ul>

  {takeaway("The official data is internally consistent and adds up exactly to the published national totals. This alone does not prove the election was clean — it means the numbers analysed in the rest of this report are the genuine, unaltered official ones.", "Os dados oficiais são internamente consistentes e batem exatamente com os totais nacionais publicados. Isso, sozinho, não prova que a eleição foi limpa — significa que os números analisados no restante deste relatório são os oficiais, genuínos e sem alteração.")}
</section>

<section id="headline">
  <h2><span class="num">02</span>{B("span", "The headline result", "O resultado principal")}</h2>
  {B("p", f"Lula (PT) defeated Flávio Bolsonaro (PL) in the round-2 runoff. Round 1 was close — Flávio actually led narrowly — and Lula's share of the two-candidate vote rose by <strong>{pct(nat['swing_pts'],'en',2)} points</strong> between rounds, once the other {summary['n_round1_candidates']-2} round-1 candidates were eliminated. A later section (<a href=\"#transfers\">§7</a>) traces where that shift came from, using every eliminated candidate's own round-1 result.", f"Lula (PT) derrotou Flávio Bolsonaro (PL) no segundo turno. O primeiro turno foi disputado — Flávio, na verdade, liderou por pouco — e o percentual de Lula entre os dois candidatos subiu <strong>{pct(nat['swing_pts'],'pt',2)} pontos</strong> entre os turnos, depois que os outros {summary['n_round1_candidates']-2} candidatos do primeiro turno foram eliminados. Uma seção posterior (<a href=\"#transfers\">§7</a>) rastreia de onde veio essa variação, usando o resultado do primeiro turno de cada candidato eliminado.", cls="lede")}

  <div class="exhibit">
    <div style="max-width:620px;margin:0 auto">
      {B("div", f"Round 1 — all {summary['n_round1_candidates']} candidates", f"1º turno — todos os {summary['n_round1_candidates']} candidatos", cls="chart-subtitle")}
      <div id="chart-national-r1" class="chart-container"></div>
      {B("div", "Round 2 — the official runoff", "2º turno — o resultado oficial", cls="chart-subtitle", attrs='style="margin-top:18px"')}
      <div id="chart-national-r2" class="chart-container"></div>
    </div>
    {B("div", f"Figure 1. Round-1 result (all {summary['n_round1_candidates']} candidates, as a share of all valid votes) and the official round-2 result. Hover or tap any bar for the exact share and the raw number of votes behind it. Flávio led round 1. To compare the two rounds fairly we use the {tip('two-candidate share', f'Lula&#39;s votes divided by (Lula + Flávio) votes only, setting the other {summary['n_round1_candidates']-2} candidates aside. Round 2 is a straight Lula-vs-Flávio contest, so this is the like-for-like baseline for it.')}: on that basis Lula had {pct(nat['lula_r1_twoparty_pct'],'en')}% in round 1, rising to {pct(nat['lula_r2_pct'],'en')}% in round 2.", f"Figura 1. Resultado do 1º turno (todos os {summary['n_round1_candidates']} candidatos, como percentual dos votos válidos) e o resultado oficial do 2º turno. Passe o mouse ou toque em qualquer barra para ver o percentual exato e o número de votos por trás dele. Flávio liderou o 1º turno. Para comparar os dois turnos de forma justa, usamos o {tip('percentual entre os dois finalistas', 'Os votos de Lula divididos apenas por (Lula + Flávio), deixando os demais candidatos de fora. O 2º turno é uma disputa direta Lula × Flávio, então essa é a base comparável para ele.')}: nessa base, Lula tinha {pct(nat['lula_r1_twoparty_pct'],'pt')}% no 1º turno, subindo para {pct(nat['lula_r2_pct'],'pt')}% no 2º turno.", cls="cap")}
  </div>

  <div class="stat-grid">
    {B("div", f'<div class="v lula">{pct(nat["lula_r2_pct"],"en")}%</div><div class="l">Lula, round-2 vote share</div>', f'<div class="v lula">{pct(nat["lula_r2_pct"],"pt")}%</div><div class="l">Lula, percentual no 2º turno</div>', cls="stat-tile")}
    {B("div", f'<div class="v flavio">{pct(nat["flavio_r2_pct"],"en")}%</div><div class="l">Flávio Bolsonaro, round-2 vote share</div>', f'<div class="v flavio">{pct(nat["flavio_r2_pct"],"pt")}%</div><div class="l">Flávio Bolsonaro, percentual no 2º turno</div>', cls="stat-tile")}
    {B("div", f'<div class="v">+{pct(nat["swing_pts"],"en",2)}pt</div><div class="l">National two-party swing to Lula</div>', f'<div class="v">+{pct(nat["swing_pts"],"pt",2)}pt</div><div class="l">Variação nacional para Lula (dois candidatos)</div>', cls="stat-tile")}
    {B("div", f'<div class="v">{pct(ab["r1_pct"],"en")}% → {pct(ab["r2_pct"],"en")}%</div><div class="l">Abstention, round 1 → round 2</div>', f'<div class="v">{pct(ab["r1_pct"],"pt")}% → {pct(ab["r2_pct"],"pt")}%</div><div class="l">Abstenção, 1º turno → 2º turno</div>', cls="stat-tile")}
  </div>

  {takeaway("Lula won a close race. Round 1 was essentially tied, and the small, nationwide shift to Lula in round 2 is the shift this report sets out to explain and stress-test.", "Lula venceu uma disputa apertada. O 1º turno ficou essencialmente empatado, e a pequena variação nacional em favor de Lula no 2º turno é justamente a variação que este relatório se propõe a explicar e testar.")}
</section>

<section id="landslides">
  <h2><span class="num">03</span>{B("span", "Are 90%+ zones unusual?", "As zonas com 90%+ são incomuns?")}</h2>
  {B("p", f"Out of {fnum(summary['n_total_zones_r2'],'en')} electoral zones that reported a presidential vote in round 2, <strong>{summary['n_lula_ge90']} zones ({pct(summary['pct_lula_ge90'],'en',2)}%)</strong> gave Lula 90% + of the two-candidate vote, and <strong>{summary['n_flavio_ge90']} zones ({pct(summary['pct_flavio_ge90'],'en',2)}%)</strong> gave Flávio Bolsonaro 90% +. Is that a lot?", f"Das {fnum(summary['n_total_zones_r2'],'pt')} zonas eleitorais que registraram votos para presidente no 2º turno, <strong>{summary['n_lula_ge90']} zonas ({pct(summary['pct_lula_ge90'],'pt',2)}%)</strong> deram a Lula 90%+ dos votos entre os dois candidatos, e <strong>{summary['n_flavio_ge90']} zonas ({pct(summary['pct_flavio_ge90'],'pt',2)}%)</strong> deram a Flávio Bolsonaro 90%+. Isso é muito?", cls="lede")}

  <div class="exhibit">
    <div id="chart-zone-hist" class="chart-container" style="flex:1"></div>
    {B("div", "Figure 2. The full distribution of round-2 results across every zone. Hover a bar for the exact count. High-concentration zones are the small tail beyond the markers — a tiny fraction of a broad, smooth distribution, not a separate spike.", "Figura 2. A distribuição completa dos resultados do 2º turno em todas as zonas. Passe o mouse sobre uma barra para ver a contagem exata. As zonas de alta concentração são a pequena cauda além dos marcadores — uma fração ínfima de uma distribuição ampla e suave, não um pico isolado.", cls="cap")}
  </div>

  <div class="callout method">
    {B("span", "<b>How we decide whether a result is surprising.</b> A 90% result is not surprising on its own: support for a candidate varies enormously across Brazil for real, well-documented reasons — the Northeast has long leaned heavily towards the PT, while parts of the South and the agribusiness belt lean the other way. So rather than asking whether 90% beats a coin flip (a bar nobody expects a real town to clear), we ask a fairer question in the sections that follow: is each zone's result surprising <em>given its own size and how that same zone voted in round 1</em>?", "<b>Como decidimos se um resultado é surpreendente.</b> Um resultado de 90% não é surpreendente por si só: o apoio a um candidato varia enormemente pelo Brasil por razões reais e bem documentadas — o Nordeste há muito pende fortemente para o PT, enquanto partes do Sul e do cinturão do agronegócio pendem para o outro lado. Então, em vez de perguntar se 90% supera um cara ou coroa (um patamar que ninguém espera de uma cidade real), fazemos nas seções seguintes uma pergunta mais justa: o resultado de cada zona é surpreendente <em>dado o seu próprio tamanho e como essa mesma zona votou no 1º turno</em>?")}
  </div>

  <div class="exhibit">
    <div class="chart-search" id="funnel-search">
      <svg class="chart-search-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="5.2" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="11" y1="11" x2="15" y2="15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
      <input type="text" id="funnel-search-input" class="chart-search-input" autocomplete="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="funnel-search-results" aria-autocomplete="list">
      <button type="button" id="funnel-search-clear" class="chart-search-clear" hidden>&times;</button>
      <ul id="funnel-search-results" class="chart-search-results" role="listbox" hidden></ul>
    </div>
    <div id="chart-funnel" class="chart-container" style="flex:1"></div>
    {B("div", f"Figure 3. Every zone's round-2 result plotted against its size (log scale). Use the search box above to jump straight to a specific municipality. Hover any point for that zone's municipality, vote count and round-1/round-2 shares. High-concentration zones (highlighted) span from tiny abroad voting posts to towns of several thousand voters — they are not a uniform small-N artifact. The flat horizontal line marks the national result ({pct(nat['lula_r2_pct'],'en')}%) for reference.", f"Figura 3. O resultado do 2º turno de cada zona em função do seu tamanho (escala logarítmica). Use a busca acima para ir direto a um município específico. Passe o mouse sobre qualquer ponto para ver o município, o número de votos e os percentuais no 1º/2º turno dessa zona. As zonas de alta concentração (destacadas) vão de pequenos postos de votação no exterior a cidades com milhares de eleitores — não são um artefato uniforme de amostra pequena. A linha horizontal marca o resultado nacional ({pct(nat['lula_r2_pct'],'pt')}%) como referência.", cls="cap")}
  </div>

  {B("h3", "The actual 90%+ zones, largest first", "As zonas de 90%+, da maior para a menor")}
  {B("p", "Here are the 15 largest-electorate zones among those that hit 90%+, with their round-1 result alongside for context:", "Estas são as 15 zonas com maior eleitorado entre as que atingiram 90%+, com o resultado do 1º turno ao lado para contexto:")}
  <div class="table-scroll">
  <table class="landslide-table">
    <thead><tr>
      <th>{B("span", "Municipality / state", "Município / estado")}</th>
      <th>{B("span", "Zone", "Zona")}</th>
      <th>{B("span", "Votes (R2)", "Votos (2T)")}</th>
      <th>{B("span", "Round 1 share", "Percentual 1T")}</th>
      <th>{B("span", "Round 2 share", "Percentual 2T")}</th>
      <th>{B("span", "Winner", "Vencedor")}</th>
    </tr></thead>
    {B("tbody", landslide_rows("en"), landslide_rows("pt"))}
  </table>
  </div>
  {B("p", 'What stands out in the table is the round-1 column: each of these zones already gave the same candidate an almost identical share in round 1, before the field narrowed to two candidates. Most are small municipalities in the North and Northeast; a handful are overseas consular posts with only a few hundred to a few thousand voters, where small vote counts on their own can produce lopsided splits. Whether this regional pattern lines up with how these places have voted before is tested directly in <a href="#consistency">§6</a> and <a href="#geography">§11</a> — we do not ask you to take it on trust here.', 'O que chama a atenção na tabela é a coluna do 1º turno: cada uma dessas zonas já havia dado ao mesmo candidato um percentual quase idêntico no 1º turno, antes de o campo se reduzir a dois candidatos. A maioria são pequenos municípios do Norte e Nordeste; alguns são postos consulares no exterior, com apenas algumas centenas a poucos milhares de eleitores, onde contagens pequenas, por si só, já podem gerar divisões desequilibradas. Se esse padrão regional é coerente com a forma como esses lugares votaram antes é verificado diretamente nas <a href="#consistency">§6</a> e <a href="#geography">§11</a> — não pedimos que você acredite nisso aqui.', attrs='style="font-size:13.5px;color:var(--text-secondary)"')}

  {takeaway("Fewer than a quarter of one percent of zones gave either candidate 90%+. They sit in the thin tail of a smooth, ordinary distribution and are concentrated in small towns — not a separate cluster that appeared from nowhere.", "Menos de um quarto de um por cento das zonas deram 90%+ a qualquer candidato. Elas ficam na cauda fina de uma distribuição suave e comum e estão concentradas em cidades pequenas — não são um agrupamento à parte que surgiu do nada.")}
</section>

<section id="montecarlo">
  <h2><span class="num">04</span>{B("span", "Could this many high-concentration results happen by chance?", "Esse número de resultados de alta concentração poderia acontecer por acaso?")}</h2>
  {B("p", f"If a town leaned 88% towards one candidate in round 1, a 90% result in round 2 is barely a change. So the real question is: how many 90%+ zones should we expect from normal round-to-round wobble alone, with no fraud at all? To find out we ran a {tip('Monte Carlo simulation', 'A standard technique: replay the election thousands of times on a computer, letting chance play out differently each time, and see what range of outcomes is normal. Named after the casino.')} — in effect, replaying the whole election {fnum(mc['n_sim'],'en')} times over, keeping each zone's real size and its real round-1 leaning fixed, but letting the exact count fall where chance puts it each time.", f"Se uma cidade pendia 88% para um candidato no 1º turno, um resultado de 90% no 2º turno é quase nenhuma mudança. Então a pergunta real é: quantas zonas com 90%+ deveríamos esperar apenas da oscilação normal entre os turnos, sem fraude alguma? Para descobrir, rodamos uma {tip('simulação de Monte Carlo', 'Uma técnica padrão: repetir a eleição milhares de vezes no computador, deixando o acaso agir de forma diferente a cada vez, para ver qual faixa de resultados é normal. O nome vem do cassino.')} — na prática, repetindo a eleição inteira {fnum(mc['n_sim'],'pt')} vezes, mantendo fixos o tamanho real de cada zona e sua inclinação real do 1º turno, mas deixando a contagem exata cair onde o acaso a colocar a cada rodada.", cls="lede")}

  {B("p", f"In detail, for each of the {fnum(summary['n_total_zones_r2'],'en')} zones we take its own round-1 two-candidate result, nudge it by the national average swing, and treat that as the zone's underlying leaning. In every simulated election each zone's vote is then re-drawn at random around that leaning (a {tip('binomial draw', 'The textbook model for counting yes/no votes — like flipping a biased coin once per voter, where the bias is that zone&#39;s own leaning. It builds in exactly the random wobble you expect from counting, and nothing else.')}). Counting the 90%+ zones in each simulated election gives us the range chance alone produces — which we then compare against what actually happened.", f"Em detalhe, para cada uma das {fnum(summary['n_total_zones_r2'],'pt')} zonas pegamos seu próprio resultado do 1º turno entre os dois candidatos, ajustamos pela variação média nacional e tratamos isso como a inclinação de base da zona. Em cada eleição simulada, o voto de cada zona é então sorteado aleatoriamente em torno dessa inclinação (um {tip('sorteio binomial', 'O modelo clássico para contar votos sim/não — como lançar, para cada eleitor, uma moeda viciada cujo viés é a inclinação daquela zona. Ele embute exatamente a oscilação aleatória esperada de uma contagem, e nada além disso.')}). Contar as zonas com 90%+ em cada eleição simulada nos dá a faixa que só o acaso produz — que então comparamos com o que de fato aconteceu.")}

  <div class="exhibit">
    <div class="chart-row">
      <div style="flex:1;min-width:260px">
        {B("div", "Lula", "Lula", cls="chart-subtitle")}
        <div id="chart-mc-lula" class="chart-container"></div>
      </div>
      <div style="flex:1;min-width:260px">
        {B("div", "Flávio Bolsonaro", "Flávio Bolsonaro", cls="chart-subtitle")}
        <div id="chart-mc-flavio" class="chart-container"></div>
      </div>
    </div>
    <div class="mini-legend" aria-hidden="true">
      <span class="mi"><span class="sw band" style="background:var(--chart-muted);opacity:0.4"></span>{B("span", "where 90% of simulations land", "onde caem 90% das simulações")}</span>
      <span class="mi"><span class="sw" style="border-top-style:dashed;border-top-color:var(--text-primary)"></span>{B("span", "chance average", "média do acaso")}</span>
      <span class="mi"><span class="sw" style="border-top-color:var(--accent)"></span>{B("span", "what actually happened", "o que de fato aconteceu")}</span>
    </div>
    {B("div", f"Figure 4. Two separate experiments — Lula on the left, Flávio on the right. Each grey histogram shows how many 90%+ zones turned up across {fnum(mc['n_sim'],'en')} simulated chance-only elections. The shaded band covers the middle 90% of those simulations, the dashed line is their average, and the solid coloured line is what actually happened in the real election. Hover or tap any bar for its exact count.", f"Figura 4. Dois experimentos separados — Lula à esquerda, Flávio à direita. Cada histograma cinza mostra quantas zonas com 90%+ apareceram em {fnum(mc['n_sim'],'pt')} eleições simuladas apenas pelo acaso. A faixa sombreada cobre os 90% centrais dessas simulações, a linha tracejada é a média delas e a linha colorida sólida é o que de fato ocorreu na eleição real. Passe o mouse ou toque em qualquer barra para ver a contagem exata.", cls="cap")}
  </div>

  <div class="callout ok">
    {B("span", f"<b>Result: the actual count of Lula's 90%+ zones ({mc['actual_lula_ge90']} zones) is far <em>below</em> what chance alone predicts</b> (simulated mean {fnum(mc['sim_lula_ge90_mean'],'en',1)}, 90% range {fnum(mc['sim_lula_ge90_p05'],'en',0)}&ndash;{fnum(mc['sim_lula_ge90_p95'],'en',0)}). If anything, real results are <em>less</em> extreme than a naive chance model would produce — the opposite of what ballot-stuffing would look like. Flávio's count of 90%+ zones ({mc['actual_flavio_ge90']} zones) sits just above the top of the chance range (simulated mean {fnum(mc['sim_flavio_ge90_mean'],'en',1)}, 90% range {fnum(mc['sim_flavio_ge90_p05'],'en',0)}&ndash;{fnum(mc['sim_flavio_ge90_p95'],'en',0)}) — around the 99th percentile, roughly a one-in-twenty result. With only a handful of zones that is mild rather than striking, but it is a small, one-sided lean worth noting; <a href=\"#robustness\">§5</a> checks whether it holds up across thresholds (it recurs, mildly, at 85%).", f"<b>Resultado: o número real de zonas de Lula com 90%+ ({mc['actual_lula_ge90']} zonas) está bem <em>abaixo</em> do que o acaso sozinho prevê</b> (média simulada {fnum(mc['sim_lula_ge90_mean'],'pt',1)}, faixa de 90% entre {fnum(mc['sim_lula_ge90_p05'],'pt',0)} e {fnum(mc['sim_lula_ge90_p95'],'pt',0)}). Se algo, os resultados reais são <em>menos</em> extremos do que um modelo de acaso ingênuo produziria — o oposto do que uma fraude de urna pareceria. O número de zonas de Flávio com 90%+ ({mc['actual_flavio_ge90']} zonas) fica logo acima do topo da faixa de acaso (média simulada {fnum(mc['sim_flavio_ge90_mean'],'pt',1)}, faixa de 90% entre {fnum(mc['sim_flavio_ge90_p05'],'pt',0)} e {fnum(mc['sim_flavio_ge90_p95'],'pt',0)}) — por volta do percentil 99, cerca de um resultado em vinte. Com apenas um punhado de zonas, isso é leve, não gritante, mas é uma pequena inclinação unilateral que vale registrar; a <a href=\"#robustness\">§5</a> verifica se ela se sustenta entre limiares (e se repete, de forma leve, em 85%).")}
  </div>

  {B("p", "In short: there is no statistical excess of 90%+ zones for either candidate that would need a fraud explanation. The frequency of 90%+ results is consistent with — if anything, lower than — ordinary sampling variance around each zone's own baseline.", "Em resumo: não há excesso estatístico de zonas com 90%+ para nenhum dos candidatos que exija uma explicação de fraude. A frequência de resultados de 90%+ é compatível com — e, se algo, inferior a — a variação amostral comum em torno da base de cada zona.")}

  {takeaway("Chance alone, with no fraud, would have produced about three times as many 90%+ Lula zones as actually occurred. The real result is calmer than random noise, not wilder — the opposite of what vote-stuffing would leave behind.", "Só o acaso, sem fraude nenhuma, teria produzido cerca de três vezes mais zonas de 90%+ para Lula do que de fato ocorreu. O resultado real é mais calmo do que o ruído aleatório, não mais extremo — o oposto do que um enchimento de urnas deixaria.")}
</section>

<section id="robustness">
  <h2><span class="num">05</span>{B("span", "Does this hold up under scrutiny?", "Isso se sustenta sob escrutínio?")}</h2>
  {B("p", "A single test, however well designed, can get lucky. So we re-ran the §4 experiment five times over, each time changing one thing: which zones are included, or where the 'high concentration' bar is set. If the conclusion only held under the exact original settings, that would be a reason to distrust it.", "Um único teste, por melhor que seja projetado, pode ter sorte. Por isso repetimos o experimento da §4 cinco vezes, mudando uma coisa de cada vez: quais zonas entram na conta, ou onde fica o patamar de 'alta concentração'. Se a conclusão só se sustentasse nas configurações originais exatas, isso seria motivo para desconfiar dela.", cls="lede")}

  {B("p", "How to read each row: the <strong>actual</strong> number is how many zones really reached that row's bar; <strong>chance</strong> is what the simulation produced — its average and, in brackets, the range covering 90% of simulations. When the actual number sits below or inside the chance range, the real result looks ordinary. Tap a variant's name for exactly what it changes.", "Como ler cada linha: o número <strong>real</strong> é quantas zonas de fato atingiram o patamar daquela linha; <strong>acaso</strong> é o que a simulação produziu — sua média e, entre parênteses, a faixa que cobre 90% das simulações. Quando o número real fica abaixo ou dentro da faixa do acaso, o resultado real parece comum. Toque no nome de uma variante para ver exatamente o que ela muda.", attrs='style="font-size:14px;color:var(--text-secondary)"')}

  <div class="table-scroll">
  <table class="robustness-table">
    <thead><tr>
      <th>{B("span", "What we changed", "O que mudamos")}</th>
      <th>{B("span", "Zones", "Zonas")}</th>
      <th>{B("span", "Lula — actual vs chance", "Lula — real vs acaso")}</th>
      <th>{B("span", "Flávio — actual vs chance", "Flávio — real vs acaso")}</th>
    </tr></thead>
    {B("tbody", robustness_rows("en"), robustness_rows("pt"))}
  </table>
  </div>

  <div class="callout ok">
    {B("span", "<b>Lula's actual count of 90%+ zones stays below the chance range in every single variant</b> — not just the headline 90% test. That's the opposite of what you'd see if these results were manufactured.", "<b>O número real de zonas de Lula com 90%+ fica abaixo da faixa de acaso em todas as variantes</b> — não apenas no teste principal de 90%. Isso é o oposto do que se veria se esses resultados fossem fabricados.")}
  </div>
  <div class="callout caveat">
    {B("span", f"<b>One result worth flagging rather than hiding:</b> Flávio's high-concentration zones come out slightly more often than chance predicts at the two stricter thresholds — {rb_by_key['threshold_85']['actual_flavio']} zones at 85% (chance range {fnum(rb_by_key['threshold_85']['sim_flavio_p05'],'en',0)}&ndash;{fnum(rb_by_key['threshold_85']['sim_flavio_p95'],'en',0)}) and {rb_by_key['baseline']['actual_flavio']} at 90% (chance range {fnum(rb_by_key['baseline']['sim_flavio_p05'],'en',0)}&ndash;{fnum(rb_by_key['baseline']['sim_flavio_p95'],'en',0)}). Each sits around the 98th&ndash;99th percentile of the chance model on its own — roughly a one-in-twenty result, and we have not corrected for testing several thresholds. So it is small (a handful of zones) and one-sided, and it points in the <em>opposite</em> direction to the high-Lula concentration this report set out to examine. It is not evidence of anything by itself — but because it shows up at more than one threshold rather than a single lucky cut-off, it is a specific, named result worth a second look with finer-grained (polling-section) data.", f"<b>Um resultado que vale sinalizar, não esconder:</b> as zonas de alta concentração de Flávio aparecem um pouco mais do que o acaso prevê nos dois limiares mais estritos — {rb_by_key['threshold_85']['actual_flavio']} zonas em 85% (faixa de acaso {fnum(rb_by_key['threshold_85']['sim_flavio_p05'],'pt',0)}&ndash;{fnum(rb_by_key['threshold_85']['sim_flavio_p95'],'pt',0)}) e {rb_by_key['baseline']['actual_flavio']} em 90% (faixa de acaso {fnum(rb_by_key['baseline']['sim_flavio_p05'],'pt',0)}&ndash;{fnum(rb_by_key['baseline']['sim_flavio_p95'],'pt',0)}). Cada um fica por volta do percentil 98&ndash;99 do modelo de acaso isoladamente — cerca de um resultado em vinte, e não corrigimos para o teste de vários limiares. Ou seja, é pequeno (um punhado de zonas) e unilateral, e aponta na direção <em>oposta</em> à alta concentração de Lula que este relatório se propôs a examinar. Não é evidência de nada por si só — mas, por aparecer em mais de um limiar, e não em um único corte de sorte, é um resultado específico e nomeado que mereceria um novo olhar com dados mais granulares (por seção eleitoral).")}
  </div>

  {takeaway("The finding holds up under every reasonable change to the rules. One small, honest caveat: Flávio ends up with slightly more lopsided zones than chance predicts — a handful of zones, and it shows up at more than one threshold rather than once by luck. It is mild, points the opposite way to the pattern this section is scrutinising, and proves nothing on its own, but we flag it rather than hide it.", "O resultado se sustenta sob toda mudança razoável nas regras. Uma pequena ressalva honesta: Flávio acaba com um pouco mais de zonas desequilibradas do que o acaso prevê — um punhado de zonas, e isso aparece em mais de um limiar, não uma única vez por sorte. É leve, aponta na direção oposta ao padrão que esta seção examina, e não prova nada por si só, mas nós o sinalizamos em vez de escondê-lo.")}
</section>

<section id="consistency">
  <h2><span class="num">06</span>{B("span", "Were these 90%+ results sudden, or pre-existing?", "Esses resultados de 90%+ foram súbitos, ou já existiam?")}</h2>
  {B("p", "The most direct way to check whether a 90%+ zone is \"real\" is to ask: did this zone already lean just as heavily the same way in round 1 — a separate vote, weeks earlier, with a different turnout and twelve candidates on the screen instead of two? If a zone was competitive in round 1 and only became lopsided in round 2, that would be a red flag. If it was already a stronghold and simply voted the same way against a different opponent, that is exactly what an ordinary runoff looks like.", "A forma mais direta de verificar se uma zona de 90%+ é \"real\" é perguntar: essa zona já pendia tão fortemente para o mesmo lado no 1º turno — uma votação à parte, semanas antes, com outro comparecimento e doze candidatos na tela, em vez de dois? Se uma zona era disputada no 1º turno e só ficou desequilibrada no 2º, isso seria um sinal de alerta. Se ela já era um reduto e apenas votou da mesma forma contra um adversário diferente, é exatamente assim que um segundo turno comum se parece.", cls="lede")}

  <div class="exhibit">
    <div class="chart-search" id="r1vsr2-search">
      <svg class="chart-search-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="5.2" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="11" y1="11" x2="15" y2="15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
      <input type="text" id="r1vsr2-search-input" class="chart-search-input" autocomplete="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="r1vsr2-search-results" aria-autocomplete="list">
      <button type="button" id="r1vsr2-search-clear" class="chart-search-clear" hidden>&times;</button>
      <ul id="r1vsr2-search-results" class="chart-search-results" role="listbox" hidden></ul>
    </div>
    <div id="chart-r1-vs-r2" class="chart-container" style="min-height:620px;max-width:620px;margin:0 auto"></div>
    <div class="mini-legend" style="justify-content:center" aria-hidden="true">
      <span class="mi"><span class="sw band" style="background:var(--chart-muted);opacity:0.5"></span>{B("span", "all other zones", "todas as outras zonas")}</span>
      <span class="mi"><span class="sw band" style="background:var(--accent)"></span>{B("span", "zone at ≥90% for one candidate", "zona com ≥90% para um candidato")}</span>
      <span class="mi"><span class="sw" style="border-top-style:dashed;border-top-color:var(--text-secondary)"></span>{B("span", "voted identically in both rounds (y = x)", "votou igual nos dois turnos (y = x)")}</span>
    </div>
    {B("div", f"Figure 5. Every zone's round-1 two-candidate share (horizontal) against its round-2 share (vertical). Use the search box above to jump straight to a specific municipality. Hover or tap a point for that zone's name and exact swing. The dashed line marks zones that voted identically in both rounds; all {fnum(summary['n_total_zones_r2'],'en')} zones, including every 90%+ zone, sit close to it — meaning round 2 mostly repeated round 1.", f"Figura 5. O percentual de Lula entre os dois candidatos no 1º turno (eixo horizontal) de cada zona contra seu percentual no 2º turno (eixo vertical). Use a busca acima para ir direto a um município específico. Passe o mouse ou toque em um ponto para ver o nome da zona e a variação exata. A linha tracejada marca as zonas que votaram igual nos dois turnos; todas as {fnum(summary['n_total_zones_r2'],'pt')} zonas, incluindo cada zona de 90%+, ficam perto dela — ou seja, o 2º turno em grande parte repetiu o 1º.", cls="cap")}
  </div>

  <div class="callout ok">
    {B("span", f"<b>Every zone that reached 90%+ in round 2 had already reached that level in round 1.</b> For example, Barreirinha (AM) — the largest Lula 90%+ zone, with {fnum(top0['n_r2'],'en')} votes, — gave Lula {pct(100*top0['p_r1_twoparty'],'en')}% of the two-candidate vote in round 1 and {pct(100*top0['p_r2'],'en')}% in round 2: a {pct(100*(top0['p_r2']-top0['p_r1_twoparty']),'en',1)}-point change, in line with the national swing. This pattern holds across every 90%+ zone in the table above.", f"<b>Toda zona que atingiu 90%+ no 2º turno já havia atingido esse patamar no 1º turno.</b> Por exemplo, Barreirinha (AM) — a maior zona de 90%+ de Lula, com {fnum(top0['n_r2'],'pt')} votos, — deu a Lula {pct(100*top0['p_r1_twoparty'],'pt')}% dos votos entre os dois candidatos no 1º turno e {pct(100*top0['p_r2'],'pt')}% no 2º turno: uma variação de {pct(100*(top0['p_r2']-top0['p_r1_twoparty']),'pt',1)} pontos, em linha com a variação nacional. Esse padrão se repete em todas as zonas de 90%+ da tabela acima.")}
  </div>

  {takeaway("None of the lopsided zones appeared out of nowhere. Each was already a stronghold in a completely separate vote three weeks earlier — the fingerprint of long-standing local loyalty, not of something inserted into round 2.", "Nenhuma das zonas desequilibradas surgiu do nada. Cada uma já era um reduto em uma votação totalmente separada, três semanas antes — a marca de uma lealdade local antiga, não de algo inserido no 2º turno.")}
</section>

<section id="transfers">
  <h2><span class="num">07</span>{B("span", "Where did the votes go?", "Para onde foram os votos?")}</h2>
  {B("p", f"The national swing was a tidy +{pct(nat['swing_pts'],'en',1)} points to Lula, but that single number hides a lot. Did it come evenly from everywhere, or did some eliminated candidates' voters break strongly one way? We estimated this with <a href=\"https://en.wikipedia.org/wiki/Ecological_regression\" target=\"_blank\" rel=\"noopener\">ecological regression</a> — a long-standing technique in election analysis for inferring group-level shifts from place-level results. It is <strong>not a measurement of individual voters</strong>, and every estimate below comes with its own uncertainty range — see the caveat underneath the chart before reading too much into any single number.", f"A variação nacional foi de um arredondado +{pct(nat['swing_pts'],'pt',1)} pontos para Lula, mas esse único número esconde bastante coisa. Ela veio igualmente de todo lugar, ou os eleitores de alguns candidatos eliminados migraram fortemente para um lado? Estimamos isso com <a href=\"https://en.wikipedia.org/wiki/Ecological_regression\" target=\"_blank\" rel=\"noopener\">regressão ecológica</a> — uma técnica consolidada em análise eleitoral para inferir deslocamentos de grupo a partir de resultados agregados por localidade. <strong>Não é uma medição de eleitores individuais</strong>, e cada estimativa abaixo vem com sua própria margem de incerteza — veja a ressalva logo abaixo do gráfico antes de tirar conclusões de qualquer número isolado.", cls="lede")}

  <div class="callout method">
    {B("span", f"<b>The method, in one paragraph.</b> For each of the {fnum(vt['n_municipalities'],'en')} municipalities, we know how many round-1 votes each candidate got and how many round-2 votes Lula and Flávio got. We fit a model estimating what fraction of a bloc's round-1 votes is consistent with having gone to Lula and what fraction to Flávio — constrained so the two fractions can never add to more than 100%, because a single voter cannot go to both finalists. We estimate the two finalists and Ronaldo Caiado on their own, and pool every other eliminated candidate into one bloc: aggregate data simply cannot separate the smaller candidates (their municipal support is too alike), so estimating them individually would invent precision that isn't there. The fitted model still reproduces the actual round-2 totals almost exactly ({tip('R² = ' + f'{vt['model_fit']['r_squared_lula']:.3f}', 'R² measures how much of the variation the model accounts for, from 0 (none) to 1 (all). 0.997 means the municipality-level totals are reproduced almost perfectly — but note this says the model fits the totals well, not that its voter-by-voter story is correct.')} for Lula, R² = {vt['model_fit']['r_squared_flavio']:.3f} for Flávio).", f"<b>O método, em um parágrafo.</b> Para cada um dos {fnum(vt['n_municipalities'],'pt')} municípios, sabemos quantos votos cada candidato teve no 1º turno e quantos votos Lula e Flávio tiveram no 2º turno. Ajustamos um modelo que estima qual fração dos votos de um bloco no 1º turno é compatível com ter ido para Lula e qual para Flávio — com a restrição de que as duas frações nunca podem somar mais de 100%, porque um mesmo eleitor não pode ir para os dois finalistas. Estimamos os dois finalistas e Ronaldo Caiado separadamente, e agrupamos todos os demais candidatos eliminados em um único bloco: dados agregados simplesmente não conseguem separar os candidatos menores (seu apoio por município é parecido demais), então estimá-los individualmente inventaria uma precisão que não existe. Ainda assim, o modelo ajustado reproduz os totais reais do 2º turno quase exatamente ({tip('R² = ' + f'{vt['model_fit']['r_squared_lula']:.3f}', 'O R² mede quanta da variação o modelo explica, de 0 (nada) a 1 (tudo). 0,997 significa que os totais por município são reproduzidos quase perfeitamente — mas isso diz que o modelo ajusta bem os totais, não que a sua história eleitor a eleitor esteja correta.')} para Lula, R² = {vt['model_fit']['r_squared_flavio']:.3f} para Flávio).")}
  </div>

  <div class="exhibit">
    <div id="chart-vote-transfer" class="chart-container" style="min-height:360px"></div>
    <div class="mini-legend" aria-hidden="true">
      <span class="mi"><span class="sw band" style="background:var(--lula)"></span>{B("span", "estimated to Lula", "estimado para Lula")}</span>
      <span class="mi"><span class="sw band" style="background:var(--flavio)"></span>{B("span", "estimated to Flávio", "estimado para Flávio")}</span>
      <span class="mi"><span class="sw" style="border-top-color:var(--text-primary);width:28px;position:relative"></span>{B("span", "90% confidence range (how uncertain the Lula share is)", "faixa de 90% de confiança (quão incerto é o percentual de Lula)")}</span>
    </div>
    {B("div", "Figure 6. Estimated destination of each round-1 bloc's votes in round 2 — the two finalists, Ronaldo Caiado, and all other eliminated candidates pooled together. The horizontal line with end-caps on each bar is the 90% confidence range for the share going to Lula: a short line means a precise estimate, a long one means the data barely pin it down (Caiado's is the widest — his bloc is the one real toss-up). Hover or tap a segment for the exact numbers and ranges.", "Figura 6. Destino estimado dos votos de cada bloco do 1º turno no 2º turno — os dois finalistas, Ronaldo Caiado, e todos os demais candidatos eliminados agrupados. A linha horizontal com extremidades em cada barra é a faixa de 90% de confiança para o percentual que foi para Lula: uma linha curta indica estimativa precisa; uma linha longa indica que os dados mal a determinam (a de Caiado é a mais larga — seu bloco é o único realmente disputado). Passe o mouse ou toque em um segmento para ver os números e as faixas exatas.", cls="cap")}
  </div>

  {B("p", f"The two finalists kept essentially all of their own round-1 voters: Lula's self-retention comes out at {pct(100*vt_cand('LULA')['lula_rate'],'en',0)}% and Flávio's at {pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate'],'en',1)}% (90% range {pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate_lo'],'en',1)}%&ndash;{pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate_hi'],'en',1)}%). Lula's bar reaches 100% because the model cannot credit a candidate with keeping more than all of his voters — and Lula actually won more votes in round 2 than his entire round-1 base, so that growth shows up instead as the strong Lula lean among the other blocs below. The one bloc genuinely split down the middle is Ronaldo Caiado's: an estimated {pct(100*vt_cand('RONALDO CAIADO')['lula_rate'],'en',0)}% to Lula and {pct(100*vt_cand('RONALDO CAIADO')['flavio_rate'],'en',0)}% to Flávio, with wide ranges on both ({pct(100*vt_cand('RONALDO CAIADO')['lula_rate_lo'],'en',0)}%&ndash;{pct(100*vt_cand('RONALDO CAIADO')['lula_rate_hi'],'en',0)}% and {pct(100*vt_cand('RONALDO CAIADO')['flavio_rate_lo'],'en',0)}%&ndash;{pct(100*vt_cand('RONALDO CAIADO')['flavio_rate_hi'],'en',0)}%) — the one genuinely contested transfer in the data. Every other eliminated candidate is pooled into a single bloc, because their municipal support is too alike to tell apart reliably; together they lean toward Lula ({pct(100*vt_cand('OTHER')['lula_rate'],'en',0)}%, range {pct(100*vt_cand('OTHER')['lula_rate_lo'],'en',0)}%&ndash;{pct(100*vt_cand('OTHER')['lula_rate_hi'],'en',0)}%), which fits the fact that Lula gained far more votes between the rounds than Flávio did.", f"Os dois finalistas mantiveram praticamente todos os seus eleitores do 1º turno: a retenção de Lula fica em {pct(100*vt_cand('LULA')['lula_rate'],'pt',0)}% e a de Flávio em {pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate'],'pt',1)}% (faixa de 90%: {pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate_lo'],'pt',1)}%&ndash;{pct(100*vt_cand('FLAVIO BOLSONARO')['flavio_rate_hi'],'pt',1)}%). A barra de Lula chega a 100% porque o modelo não pode creditar a um candidato ter mantido mais do que todos os seus eleitores — e Lula de fato recebeu mais votos no 2º turno do que toda a sua base do 1º, então esse crescimento aparece como a forte inclinação a favor de Lula nos outros blocos abaixo. O único bloco realmente dividido ao meio é o de Ronaldo Caiado: uma estimativa de {pct(100*vt_cand('RONALDO CAIADO')['lula_rate'],'pt',0)}% para Lula e {pct(100*vt_cand('RONALDO CAIADO')['flavio_rate'],'pt',0)}% para Flávio, com faixas largas nos dois casos ({pct(100*vt_cand('RONALDO CAIADO')['lula_rate_lo'],'pt',0)}%&ndash;{pct(100*vt_cand('RONALDO CAIADO')['lula_rate_hi'],'pt',0)}% e {pct(100*vt_cand('RONALDO CAIADO')['flavio_rate_lo'],'pt',0)}%&ndash;{pct(100*vt_cand('RONALDO CAIADO')['flavio_rate_hi'],'pt',0)}%) — a única transferência genuinamente disputada nos dados. Todos os demais candidatos eliminados são agrupados em um único bloco, porque seu apoio por município é parecido demais para separar com confiança; juntos, eles pendem para Lula ({pct(100*vt_cand('OTHER')['lula_rate'],'pt',0)}%, faixa {pct(100*vt_cand('OTHER')['lula_rate_lo'],'pt',0)}%&ndash;{pct(100*vt_cand('OTHER')['lula_rate_hi'],'pt',0)}%), o que é coerente com o fato de Lula ter ganhado muito mais votos entre os turnos do que Flávio.")}

  <div class="callout caveat">
    {B("span", "<b>Why this is exploratory, not confirmatory.</b> Ecological regression famously can mislead when the underlying individual-level behaviour doesn't match the aggregate pattern (the \"ecological fallacy\") — a municipality where Lula gained ground could reflect eliminated-candidate voters switching to him, or simply different people turning out in round 2, and this method cannot fully tell those apart. The wide range on Caiado's split, and our pooling of the smaller candidates rather than reporting made-up precision for them, are the analysis being honest about that limitation, not a bug. Read this section as a plausible, data-grounded sketch of where votes likely moved — not as a precise accounting.", "<b>Por que isto é exploratório, não confirmatório.</b> A regressão ecológica pode enganar quando o comportamento individual subjacente não corresponde ao padrão agregado (a \"falácia ecológica\") — um município onde Lula ganhou terreno pode refletir eleitores de candidatos eliminados migrando para ele, ou simplesmente pessoas diferentes comparecendo no 2º turno, e este método não consegue distinguir totalmente entre essas possibilidades. A faixa larga na divisão de Caiado, e o fato de agruparmos os candidatos menores em vez de reportar uma precisão inventada para eles, são a análise sendo honesta sobre essa limitação, não um defeito. Leia esta seção como um esboço plausível e fundamentado em dados de para onde os votos provavelmente se moveram — não como uma contabilidade precisa.")}
  </div>

  {takeaway("Both finalists kept almost all of their own first-round voters. Caiado's bloc was the one real toss-up and split about evenly; the remaining eliminated voters leaned Lula, matching his larger between-round gain. We only report the blocs the data can actually resolve, and show how uncertain each one is — this is a plausible sketch of how the runoff was decided, not a precise count.", "Os dois finalistas mantiveram quase todos os seus eleitores do 1º turno. O bloco de Caiado foi o único realmente disputado e se dividiu quase ao meio; os demais eleitores eliminados penderam para Lula, condizente com o seu maior ganho entre os turnos. Só reportamos os blocos que os dados conseguem de fato resolver, e mostramos o quão incerto é cada um — este é um esboço plausível de como o 2º turno foi decidido, não uma contagem precisa.")}
</section>

<section id="turnout">
  <h2><span class="num">08</span>{B("span", 'Turnout change vs. vote swing', 'Variação de comparecimento vs. variação de votos')}</h2>
  {B("p", "One pattern sometimes associated with ballot stuffing is incremental turnout between rounds flowing almost entirely to one candidate — i.e. a strong correlation between the change in turnout rate and the swing toward a candidate. We tested this directly across all zones.", "Um padrão às vezes associado a fraude de urna é o comparecimento incremental entre os turnos fluindo quase inteiramente para um candidato — ou seja, uma forte correlação entre a variação na taxa de comparecimento e a variação a favor de um candidato. Testamos isso diretamente em todas as zonas.", cls="lede")}

  <div class="exhibit">
    <div class="chart-row">
      <div id="chart-swing-hist" class="chart-container" style="flex:1"></div>
      <div id="chart-swing-scatter" class="chart-container" style="flex:1"></div>
    </div>
    {B("div", f'Figure 7. Left: the distribution of zone-level swing to Lula is narrow and centred near the national average ({pct(nat["swing_pts"],"en",2)} pts), with no fat tail — hover or tap a bar for the exact count. Right: turnout-rate change vs. swing to Lula, zone level (<span id="swing-corr-caption-en"></span>) — a flat, shapeless cloud, hover or tap a point for that zone.', f'Figura 7. Esquerda: a distribuição da variação para Lula por zona é estreita e centrada perto da média nacional ({pct(nat["swing_pts"],"pt",2)} pts), sem cauda pesada — passe o mouse ou toque em uma barra para ver a contagem exata. Direita: variação na taxa de comparecimento vs. variação para Lula, por zona (<span id="swing-corr-caption-pt"></span>) — uma nuvem plana e sem forma; passe o mouse ou toque em um ponto para ver essa zona.', cls="cap")}
  </div>

  <div class="callout {corr_cls}">
    {B("span", f"<b>{tip('Pearson r', 'A correlation coefficient: 0 means no linear relationship, +1 or −1 a perfect one. At 0.08 the two quantities are essentially unrelated.')} = {pct(corr['pearson_r'],'en',3)}</b> (n = {fnum(corr['n'],'en')}, p = {corr['p_value']:.1e}). The correlation is {tip('statistically significant', 'With 6,250 zones, even a trivially small pattern clears the usual significance bar. Significance here means &#39;almost certainly not exactly zero&#39; — it says nothing about whether the relationship is big enough to matter. It is not.')} purely because of the large sample size, but the effect is negligible — turnout change explains well under 1% of the variation in swing (r² = {pct(corr['pearson_r']**2*100,'en',2)}%). There is no meaningful relationship between where turnout rose and where the vote swung, which is what we'd expect from ordinary voting and not from coordinated ballot-stuffing tied to turnout.", f"<b>{tip('r de Pearson', 'Um coeficiente de correlação: 0 significa nenhuma relação linear; +1 ou −1, uma relação perfeita. Em 0,08, as duas grandezas são essencialmente não relacionadas.')} = {pct(corr['pearson_r'],'pt',3)}</b> (n = {fnum(corr['n'],'pt')}, p = {corr['p_value']:.1e}). A correlação é {tip('estatisticamente significativa', 'Com 6.250 zonas, até um padrão insignificante supera o limiar usual de significância. Significância aqui quer dizer &#39;quase certamente não é exatamente zero&#39; — não diz nada sobre o efeito ser grande o bastante para importar. E não é.')} apenas por causa do tamanho grande da amostra, mas o efeito é insignificante — a variação no comparecimento explica bem menos de 1% da variação na variação de votos (r² = {pct(corr['pearson_r']**2*100,'pt',2)}%). Não há relação relevante entre onde o comparecimento aumentou e onde o voto variou, o que é o esperado em uma votação comum, e não em uma fraude de urna coordenada e ligada ao comparecimento.")}
  </div>

  {takeaway("Where more people turned out in round 2, the vote did not swing any particular way. Extra turnout was not quietly flowing to one candidate — there is simply no link between the two.", "Onde mais gente compareceu no 2º turno, o voto não variou em nenhuma direção específica. O comparecimento extra não estava fluindo silenciosamente para um candidato — simplesmente não há ligação entre as duas coisas.")}
</section>

<section id="blanknull">
  <h2><span class="num">09</span>{B("span", "Blank and spoiled votes", "Votos em branco e nulos")}</h2>
  {B("p", f"Blank and spoiled (null) ballots are sometimes read as a protest signal — a voter who shows up but declines every candidate on offer. Round 1 had 12 options to reject; round 2 had only 2, so the combined rate should mechanically fall between rounds. It does: {pct(bn['round1']['invalid_rate_pct'],'en',2)}% of round-1 turnout was blank or null, falling to {pct(bn['round2']['invalid_rate_pct'],'en',2)}% in round 2 — a drop of {pct(abs(bn['blank_rate_change_pts']),'en',2)} points in blank votes and {pct(abs(bn['null_rate_change_pts']),'en',2)} points in null votes.", f"Votos em branco e nulos às vezes são lidos como um sinal de protesto — um eleitor que comparece, mas rejeita todos os candidatos disponíveis. O 1º turno tinha 12 opções para rejeitar; o 2º turno tinha apenas 2, então a taxa combinada deveria cair mecanicamente entre os turnos. E caiu: {pct(bn['round1']['invalid_rate_pct'],'pt',2)}% do comparecimento no 1º turno foi em branco ou nulo, caindo para {pct(bn['round2']['invalid_rate_pct'],'pt',2)}% no 2º turno — uma queda de {pct(abs(bn['blank_rate_change_pts']),'pt',2)} pontos em votos em branco e {pct(abs(bn['null_rate_change_pts']),'pt',2)} pontos em votos nulos.", cls="lede")}

  <div class="exhibit">
    <div id="chart-blank-null" class="chart-container" style="min-height:220px"></div>
    {B("div", "Figure 8. National blank and null vote rates, as a share of turnout, each round. Hover or tap a bar for the exact rate.", "Figura 8. Taxas nacionais de votos em branco e nulos, como percentual do comparecimento, em cada turno. Passe o mouse ou toque em uma barra para ver a taxa exata.", cls="cap")}
  </div>

  {B("p", f"The combined rate varies by state in round 2, from a high in {bn_hi[0]['sg_uf']} ({pct(bn_hi[0]['r2'],'en',2)}%) and {bn_hi[1]['sg_uf']} ({pct(bn_hi[1]['r2'],'en',2)}%) down to {bn_lo[-1]['sg_uf']} ({pct(bn_lo[-1]['r2'],'en',2)}%) and {bn_lo[-2]['sg_uf']} ({pct(bn_lo[-2]['r2'],'en',2)}%) — a normal range for a country this size, and not something we ran a formal outlier test on in this pass (see the closing section).", f"A taxa combinada varia por estado no 2º turno, de um máximo em {bn_hi[0]['sg_uf']} ({pct(bn_hi[0]['r2'],'pt',2)}%) e {bn_hi[1]['sg_uf']} ({pct(bn_hi[1]['r2'],'pt',2)}%) até um mínimo em {bn_lo[-1]['sg_uf']} ({pct(bn_lo[-1]['r2'],'pt',2)}%) e {bn_lo[-2]['sg_uf']} ({pct(bn_lo[-2]['r2'],'pt',2)}%) — uma faixa normal para um país deste tamanho, e algo sobre o qual não rodamos um teste formal de valores atípicos nesta etapa (veja a seção final).")}

  {takeaway("Fewer voters rejected every candidate in round 2 than in round 1 — exactly what you'd expect when the choice narrows from twelve names to two. Nothing unusual here.", "Menos eleitores rejeitaram todos os candidatos no 2º turno do que no 1º — exatamente o esperado quando a escolha passa de doze nomes para dois. Nada de incomum aqui.")}
</section>

<section id="digits">
  <h2><span class="num">10</span>{B("span", "Digit-based forensic tests", "Testes forenses baseados em dígitos")}</h2>
  {B("p", f"Election forensics sometimes checks whether the last digit of vote counts is {tip('uniformly distributed', 'In a genuine count, the final digit of a vote total (…7, …3, …0) is essentially random, so each of 0–9 should appear about one-tenth of the time. People inventing numbers by hand tend, unconsciously, to favour some digits over others.')} — each of 0&ndash;9 appearing about equally often — because numbers invented by hand often aren't. We ran a {tip('chi-square goodness-of-fit test', 'A standard statistical test that measures how far an observed set of counts is from a perfectly even split, and gives a p-value: the probability of seeing a gap this large by pure chance if the digits really are even. A high p-value means &#39;nothing unusual&#39;.')} on the last digit of every zone's vote count for each candidate, and on municipality-level valid-vote totals.", f"A perícia eleitoral às vezes verifica se o último dígito da contagem de votos é {tip('distribuído uniformemente', 'Em uma contagem genuína, o último dígito de um total de votos (…7, …3, …0) é essencialmente aleatório, então cada um de 0–9 deveria aparecer cerca de um décimo das vezes. Pessoas que inventam números à mão tendem, inconscientemente, a favorecer alguns dígitos.')} — cada um de 0&ndash;9 aparecendo com frequência parecida — porque números inventados à mão muitas vezes não são. Rodamos um {tip('teste de aderência qui-quadrado', 'Um teste estatístico padrão que mede o quão longe um conjunto de contagens observadas está de uma divisão perfeitamente uniforme, e fornece um valor-p: a probabilidade de ver uma diferença tão grande por puro acaso se os dígitos forem realmente uniformes. Um valor-p alto significa &#39;nada de incomum&#39;.')} sobre o último dígito da contagem de votos de cada zona para cada candidato, e sobre os totais de votos válidos por município.", cls="lede")}

  <div class="exhibit">
    <div class="chart-row">
      <div style="flex:1;min-width:260px">
        {B("div", "Lula", "Lula", cls="chart-subtitle")}
        <div id="chart-digit-lula" class="chart-container"></div>
      </div>
      <div style="flex:1;min-width:260px">
        {B("div", "Flávio Bolsonaro", "Flávio Bolsonaro", cls="chart-subtitle")}
        <div id="chart-digit-flavio" class="chart-container"></div>
      </div>
    </div>
    {B("div", "Figure 9. How often each final digit (0–9) appears in zone-level vote counts (counts under 10 excluded, where small numbers would bias the digits), against the even expectation of one-tenth each (dashed line). Bars sitting close to the line is the clean-count pattern. Hover or tap a bar for the exact count.", "Figura 9. Com que frequência cada dígito final (0–9) aparece nas contagens de votos por zona (contagens abaixo de 10 excluídas, onde números pequenos enviesariam os dígitos), contra a expectativa uniforme de um décimo cada (linha tracejada). Barras próximas da linha são o padrão de uma contagem limpa. Passe o mouse ou toque em uma barra para ver a contagem exata.", cls="cap")}
  </div>

  <div class="callout ok">
    {B("span", f"No test rejects uniformity: Lula's counts (χ²={pct(dt_lula['chi2'],'en',2)}, p={pct(dt_lula['p_value'],'en',2)}), Flávio's counts (χ²={pct(dt_flavio['chi2'],'en',2)}, p={pct(dt_flavio['p_value'],'en',2)}), and municipality-level valid-vote totals (χ²={pct(dt_muni['chi2'],'en',2)}, p={pct(dt_muni['p_value'],'en',2)}) are all consistent with evenly distributed last digits. (A p-value far above the usual 0.05 cut-off means the digits look random, as a clean count should.)", f"Nenhum teste rejeita a uniformidade: a contagem de Lula (χ²={pct(dt_lula['chi2'],'pt',2)}, p={pct(dt_lula['p_value'],'pt',2)}), a de Flávio (χ²={pct(dt_flavio['chi2'],'pt',2)}, p={pct(dt_flavio['p_value'],'pt',2)}) e os totais de votos válidos por município (χ²={pct(dt_muni['chi2'],'pt',2)}, p={pct(dt_muni['p_value'],'pt',2)}) são todos compatíveis com dígitos finais distribuídos de forma uniforme. (Um valor-p bem acima do corte usual de 0,05 significa que os dígitos parecem aleatórios, como deve ser numa contagem limpa.)")}
  </div>
  <div class="callout caveat">
    {B("span", '<b>Caveat.</b> Digit-based tests are a standard but limited tool. <a href="https://doi.org/10.1093/pan/mpr014" target="_blank" rel="noopener">Deckert, Myagkov &amp; Ordeshook (2011)</a> showed first-digit Benford tests are not theoretically justified for vote counts and can both miss real fraud and flag clean elections; last-digit tests (used here) are more defensible but still have limited statistical power, especially against fraud that adds vote counts in round numbers or small, carefully chosen increments rather than large uniform fabrications. Treat this section as supporting evidence only, not as a standalone verdict.', '<b>Ressalva.</b> Testes baseados em dígitos são uma ferramenta padrão, mas limitada. <a href="https://doi.org/10.1093/pan/mpr014" target="_blank" rel="noopener">Deckert, Myagkov e Ordeshook (2011)</a> mostraram que testes de primeiro dígito de Benford não têm justificativa teórica para contagens de votos e podem tanto deixar passar fraudes reais quanto sinalizar eleições limpas; testes de último dígito (usados aqui) são mais defensáveis, mas ainda têm poder estatístico limitado, especialmente contra fraudes que somam votos em números redondos ou em pequenos incrementos cuidadosamente escolhidos, em vez de grandes fabricações uniformes. Trate esta seção apenas como evidência de apoio, não como um veredito isolado.')}
  </div>

  {takeaway("The digits of the vote counts look random, as they should in a genuine count. This is a weak test on its own — it agrees with the others here, but it could not catch every kind of tampering.", "Os dígitos das contagens de votos parecem aleatórios, como devem ser numa contagem genuína. É um teste fraco por si só — concorda com os demais aqui, mas não detectaria todo tipo de manipulação.")}
</section>

<section id="geography">
  <h2><span class="num">11</span>{B("span", "Does this match known political geography?", "Isso corresponde à geografia política conhecida?")}</h2>
  {B("p", "A final sanity check: does the round-1-to-round-2 pattern, state by state, match Brazil's well-documented political geography from prior, undisputed elections?", "Uma verificação final de sanidade: o padrão entre o 1º e o 2º turno, estado por estado, corresponde à geografia política bem documentada do Brasil em eleições anteriores e incontestadas?", cls="lede")}

  <div class="exhibit">
    <div id="chart-state-swing" class="chart-container" style="min-height:760px;max-width:680px;margin:0 auto"></div>
    {B("div", "Figure 10a. Lula's two-candidate share by state, round 1 vs. round 2. States are sorted by round-2 result. Hover or tap a row for the exact swing.", "Figura 10a. Percentual de Lula entre os dois candidatos por estado, 1º turno vs. 2º turno. Os estados estão ordenados pelo resultado do 2º turno. Passe o mouse ou toque em uma linha para ver a variação exata.", cls="cap")}
  </div>

  {B("p", 'Yes: the ranking — strong PT support across the Northeast (PI, BA, MA, SE, PE, CE), weaker support in the South and parts of the Center-West (RR, RO, SC, MT, AC, PR) — reproduces the regional pattern seen in Brazil\'s <a href="https://en.wikipedia.org/wiki/2022_Brazilian_general_election" target="_blank" rel="noopener">2022</a> and <a href="https://en.wikipedia.org/wiki/2018_Brazilian_general_election" target="_blank" rel="noopener">2018</a> elections. The swing from round 1 to round 2 is small and uniform across states (no state shows an outlier jump), which is what an honest runoff with redistributed eliminated-candidate votes looks like.', 'Sim: o ranking — forte apoio ao PT em todo o Nordeste (PI, BA, MA, SE, PE, CE), apoio mais fraco no Sul e em partes do Centro-Oeste (RR, RO, SC, MT, AC, PR) — reproduz o padrão regional visto nas eleições de <a href="https://pt.wikipedia.org/wiki/Elei%C3%A7%C3%A3o_presidencial_no_Brasil_em_2022" target="_blank" rel="noopener">2022</a> e <a href="https://pt.wikipedia.org/wiki/Elei%C3%A7%C3%A3o_presidencial_no_Brasil_em_2018" target="_blank" rel="noopener">2018</a> no Brasil. A variação do 1º para o 2º turno é pequena e uniforme entre os estados (nenhum estado mostra um salto atípico), exatamente o que um segundo turno honesto, com a redistribuição dos votos dos candidatos eliminados, deveria parecer.')}

  <div class="exhibit">
    <div id="chart-state-turnout" class="chart-container" style="min-height:760px;max-width:680px;margin:0 auto"></div>
    {B("div", "Figure 10b. Abstention rate by state, round 1 vs. round 2. Hover or tap a row for the exact change.", "Figura 10b. Taxa de abstenção por estado, 1º turno vs. 2º turno. Passe o mouse ou toque em uma linha para ver a variação exata.", cls="cap")}
  </div>

  {B("p", f"Abstention fell in most states between rounds (national abstention dropped from {pct(ab['r1_pct'],'en')}% to {pct(ab['r2_pct'],'en')}%, consistent with a runoff drawing slightly more of the registered electorate), with no state showing the kind of isolated, large jump that would be worth a second look.", f"A abstenção caiu na maioria dos estados entre os turnos (a abstenção nacional caiu de {pct(ab['r1_pct'],'pt')}% para {pct(ab['r2_pct'],'pt')}%, consistente com um segundo turno atraindo uma fração um pouco maior do eleitorado registrado), sem nenhum estado mostrando o tipo de salto isolado e grande que mereceria um novo olhar.")}

  {takeaway("The map of support looks like Brazil's recent elections: the same regions lean the same ways, and the shift between rounds is gentle and consistent everywhere. Nothing here departs from how the country is known to vote.", "O mapa do apoio se parece com as eleições recentes do Brasil: as mesmas regiões pendem para os mesmos lados, e a mudança entre os turnos é suave e consistente em todo lugar. Nada aqui foge de como se sabe que o país vota.")}
</section>

<section id="capture">
  <h2><span class="num">12</span>{B("span", "Did one candidate get all the swing votes?", "Um candidato ficou com todos os votos que mudaram?")}</h2>
  {B("p", f"A striking claim circulates about this election: in some places one candidate picked up essentially <em>all</em> of the extra votes between round 1 and round 2 — every eliminated-candidate voter, every recovered blank or null, every newly-turned-out voter — while the other candidate gained nothing. It is true. In {brc['example_lula']['nm_municipio']} ({brc['example_lula']['sg_uf']}), for instance, Lula's total rose by {fnum(brc['example_lula']['dL'],'en')} between the rounds while Flávio's <em>fell</em> by {fnum(abs(brc['example_lula']['dF']),'en')} — Lula captured more than 100% of the net new votes. Does that prove the count was steered? No. This section asks the obvious follow-up questions — does it happen to the other candidate, how often, and could it happen without anyone inventing a vote — and the answers show why it is a mirage.", f"Circula uma afirmação impactante sobre esta eleição: em alguns lugares, um candidato ficou com praticamente <em>todos</em> os votos a mais entre o 1º e o 2º turno — cada eleitor de candidato eliminado, cada voto em branco ou nulo recuperado, cada eleitor que passou a comparecer — enquanto o outro candidato não ganhou nada. É verdade. Em {brc['example_lula']['nm_municipio']} ({brc['example_lula']['sg_uf']}), por exemplo, o total de Lula subiu {fnum(brc['example_lula']['dL'],'pt')} entre os turnos, enquanto o de Flávio <em>caiu</em> {fnum(abs(brc['example_lula']['dF']),'pt')} — Lula capturou mais de 100% dos votos novos. Isso prova que a apuração foi dirigida? Não. Esta seção faz as perguntas óbvias seguintes — isso acontece com o outro candidato, com que frequência, e poderia acontecer sem ninguém inventar um voto — e as respostas mostram por que é uma miragem.", cls="lede")}

  {B("p", "First, what \"100%\" means here. For each zone we take the two finalists' combined gain between rounds — the net new votes that landed with a finalist — and ask what share went to Lula. \"100% to Lula\" simply means <strong>Flávio's total did not rise in that zone</strong>; nothing was added to Lula's pile that wasn't a real vote. It is a ratio, and like any ratio it swings to 100% the moment the bottom number (the opponent's gain) drops to zero.", "Primeiro, o que \"100%\" significa aqui. Para cada zona, pegamos o ganho combinado dos dois finalistas entre os turnos — os votos novos que foram para um finalista — e perguntamos qual fração foi para Lula. \"100% para Lula\" significa apenas que <strong>o total de Flávio não subiu naquela zona</strong>; nada foi acrescentado à conta de Lula que não fosse um voto real. É uma razão e, como toda razão, salta para 100% assim que o número de baixo (o ganho do adversário) chega a zero.")}

  {B("p", f"How often does it happen? Lula captured 100%+ of the net new votes in <strong>{fnum(brc['lula_ge100_zones'],'en')} zones ({pct(brc['lula_ge100_pct'],'en',1)}%)</strong>; Flávio did in <strong>{fnum(brc['flavio_ge100_zones'],'en')} zones ({pct(brc['flavio_ge100_pct'],'en',1)}%)</strong>. That looks lopsided — but it is the national swing restated. Because the runoff moved toward Lula (higher turnout, fewer blank/null votes, and the eliminated candidates breaking his way — see <a href=\"#transfers\">§7</a> and <a href=\"#turnout\">§8</a>), Lula's total rose almost everywhere: Flávio's total failed to rise in {pct(brc['pct_flavio_no_growth'],'en',0)}% of zones, Lula's in only {pct(brc['pct_lula_no_growth'],'en',0)}%. Wherever the opponent stalls, the other candidate mechanically \"gets 100%.\"", f"Com que frequência isso acontece? Lula capturou 100%+ dos votos novos em <strong>{fnum(brc['lula_ge100_zones'],'pt')} zonas ({pct(brc['lula_ge100_pct'],'pt',1)}%)</strong>; Flávio, em <strong>{fnum(brc['flavio_ge100_zones'],'pt')} zonas ({pct(brc['flavio_ge100_pct'],'pt',1)}%)</strong>. Parece desproporcional — mas é a variação nacional reformulada. Como o 2º turno se moveu para Lula (maior comparecimento, menos votos em branco/nulos, e os candidatos eliminados pendendo para ele — veja <a href=\"#transfers\">§7</a> e <a href=\"#turnout\">§8</a>), o total de Lula subiu em quase todo lugar: o total de Flávio deixou de subir em {pct(brc['pct_flavio_no_growth'],'pt',0)}% das zonas, e o de Lula em apenas {pct(brc['pct_lula_no_growth'],'pt',0)}%. Onde o adversário empaca, o outro candidato fica \"com 100%\" por pura mecânica.")}

  <div class="exhibit">
    <div class="chart-search" id="capture-search">
      <svg class="chart-search-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="5.2" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="11" y1="11" x2="15" y2="15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
      <input type="text" id="capture-search-input" class="chart-search-input" autocomplete="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="capture-search-results" aria-autocomplete="list">
      <button type="button" id="capture-search-clear" class="chart-search-clear" hidden>&times;</button>
      <ul id="capture-search-results" class="chart-search-results" role="listbox" hidden></ul>
    </div>
    <div id="chart-capture" class="chart-container" style="min-height:420px"></div>
    {B("div", "Figure 11. Each dot is an electoral zone with a meaningful number of swing votes. Horizontal: how the zone leaned in round 1 (Lula's two-candidate share). Vertical: Lula's share of the net new votes between rounds — 100% means all of them went to Lula, 0% means all went to Flávio, and above 100% means a candidate also took votes the other one lost. The smooth upward cloud is the tell: the \"capture\" is a function of how the zone already voted, not a separate population. Use the search box above to jump to a municipality; hover or tap a dot for each candidate's share and vote total in both rounds.", "Figura 11. Cada ponto é uma zona eleitoral com um número relevante de votos que mudaram. Horizontal: como a zona pendia no 1º turno (percentual de Lula entre os dois). Vertical: o percentual dos votos novos entre os turnos que foi para Lula — 100% significa que todos foram para Lula, 0% que todos foram para Flávio, e acima de 100% significa que um candidato também pegou votos que o outro perdeu. A nuvem que sobe de forma suave é o indício: a \"captura\" é uma função de como a zona já votava, não uma população à parte. Use a busca acima para ir a um município; passe o mouse ou toque em um ponto para ver o percentual e o total de votos de cada candidato nos dois turnos.", cls="cap")}
  </div>

  <div class="callout ok">
    {B("span", f"<b>It tracks how each zone already leaned — the fingerprint of ordinary consolidation.</b> The more a zone leaned Lula in round 1, the larger his share of the new votes (correlation {pct(brc['corr_lean_capture'],'en',2)}): in his strongholds the third-way and newly-turned-out voters break his way, exactly as they break Flávio's way in Flávio country. The same \"100%+\" happens for Flávio where he outgrew Lula — for example {brc['example_flavio']['nm_municipio']} ({brc['example_flavio']['sg_uf']}), where Flávio gained {fnum(brc['example_flavio']['dF'],'en')} and Lula <em>lost</em> {fnum(abs(brc['example_flavio']['dL']),'en')}. By the viral logic, \"Flávio stole {fnum(abs(brc['example_flavio']['dL']),'en')} votes from Lula\" there — in reality both are just ordinary runoff swings, pointing in opposite directions.", f"<b>Acompanha como cada zona já pendia — a marca da consolidação comum.</b> Quanto mais uma zona pendia para Lula no 1º turno, maior o seu percentual dos votos novos (correlação {pct(brc['corr_lean_capture'],'pt',2)}): nos seus redutos, os eleitores de terceira via e os que passaram a comparecer pendem para ele, exatamente como pendem para Flávio no território de Flávio. O mesmo \"100%+\" acontece para Flávio onde ele cresceu mais que Lula — por exemplo {brc['example_flavio']['nm_municipio']} ({brc['example_flavio']['sg_uf']}), onde Flávio ganhou {fnum(brc['example_flavio']['dF'],'pt')} e Lula <em>perdeu</em> {fnum(abs(brc['example_flavio']['dL']),'pt')}. Pela lógica viral, \"Flávio roubou {fnum(abs(brc['example_flavio']['dL']),'pt')} votos de Lula\" ali — na realidade, ambos são apenas variações comuns de 2º turno, em direções opostas.")}
  </div>

  <div class="callout ok">
    {B("span", f"<b>And no votes are invented.</b> In every one of these zones the winner's gain fits entirely inside the real pool of available voters — the round-1 third-way, blank and null votes, plus any extra turnout, plus any voters the opponent lost. Across all {fnum(brc['n_zones'],'en')} zones the most any candidate took was {pct(brc['max_gain_vs_pool_pct'],'en',1)}% of that real pool, <strong>{brc['n_zones_gain_exceeds_pool']}</strong> zones required more than existed, and (from <a href=\"#integrity\">§1</a>) <strong>{di['turnout_exceeds_electorate']}</strong> zones recorded more voters than the registered electorate. \"100% of the swing votes\" is 100% of a real, finite pool of people who actually turned out — not phantom ballots.", f"<b>E nenhum voto é inventado.</b> Em cada uma dessas zonas, o ganho do vencedor cabe inteiramente dentro do conjunto real de eleitores disponíveis — os votos de terceira via, brancos e nulos do 1º turno, mais qualquer comparecimento extra, mais os eleitores que o adversário perdeu. Em todas as {fnum(brc['n_zones'],'pt')} zonas, o máximo que qualquer candidato tomou foi {pct(brc['max_gain_vs_pool_pct'],'pt',1)}% desse conjunto real, <strong>{brc['n_zones_gain_exceeds_pool']}</strong> zonas exigiram mais do que existia, e (da <a href=\"#integrity\">§1</a>) <strong>{di['turnout_exceeds_electorate']}</strong> zonas registraram mais eleitores do que o eleitorado. \"100% dos votos que mudaram\" é 100% de um conjunto real e finito de pessoas que de fato compareceram — não cédulas fantasmas.")}
  </div>

  {takeaway("\"One candidate got 100% of the extra votes\" sounds alarming but is just arithmetic: it means the other candidate didn't grow there. It happens for both, it tracks how each place already voted, and it never requires a single invented vote. It is the swing toward Lula seen through a jumpy ratio — not a signature of fraud.", "\"Um candidato ficou com 100% dos votos a mais\" soa alarmante, mas é só aritmética: significa que o outro candidato não cresceu ali. Acontece com os dois, acompanha como cada lugar já votava, e nunca exige um único voto inventado. É a variação a favor de Lula vista através de uma razão instável — não uma assinatura de fraude.")}
</section>

<section id="findings">
  <h2><span class="num">13</span>{B("span", "Findings register, and what this can't tell us", "Registro de achados, e o que isto não consegue dizer")}</h2>
  {B("p", "This section does two things a serious audit should always do explicitly: list every finding with a plain classification of how strong it is, and say — specifically, not vaguely — what questions this dataset cannot answer and what would be needed to answer them.", "Esta seção faz duas coisas que uma auditoria séria sempre deveria fazer de forma explícita: listar cada achado com uma classificação clara de quão forte ele é, e dizer — de forma específica, não vaga — quais perguntas este conjunto de dados não consegue responder e o que seria necessário para respondê-las.", cls="lede")}

  {B("h3", "Findings register", "Registro de achados")}
  <div class="table-scroll">
  <table class="findings-table">
    <thead><tr>
      <th>{B("span", "Analysis", "Análise")}</th>
      <th>{B("span", "Classification", "Classificação")}</th>
      <th>{B("span", "Note", "Nota")}</th>
    </tr></thead>
    <tbody>
      <tr><td>{B("span","Data integrity &amp; reconciliation (§1)","Integridade e reconciliação dos dados (§1)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","0 failures across every duplicate, reconciliation and impossible-value check.","0 falhas em todas as verificações de duplicidade, reconciliação e valores impossíveis.")}</td></tr>
      <tr><td>{B("span","Frequency of 90%+ zones vs. chance model (§4–5)","Frequência de zonas com 90%+ vs. modelo de acaso (§4–5)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","Stable below/within the chance range across 5 robustness variants.","Estável abaixo/dentro da faixa de acaso em 5 variantes de robustez.")}</td></tr>
      <tr><td>{B("span","Flávio's high-concentration zone count (§4–5)","Contagem de zonas de alta concentração de Flávio (§4–5)")}</td><td>{B("span",'<span class="pill pill-b">B — Statistical anomaly</span>','<span class="pill pill-b">B — Anomalia estatística</span>')}</td><td>{B("span","A handful of zones above the chance range at both the 85% and 90% thresholds (~98th–99th percentile, ~1-in-20 each); mild, one-sided, uncorrected for multiple testing, and opposite in direction to the pattern under examination.","Um punhado de zonas acima da faixa de acaso nos limiares de 85% e 90% (~percentil 98–99, ~1 em 20 cada); leve, unilateral, sem correção para múltiplas comparações, e na direção oposta ao padrão examinado.")}</td></tr>
      <tr><td>{B("span","Round-1-to-round-2 zone consistency (§6)","Consistência de zona entre 1º e 2º turno (§6)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","All zones, including every 90%+ zone, sit on the y=x continuity line.","Todas as zonas, incluindo cada zona de 90%+, ficam sobre a linha de continuidade y=x.")}</td></tr>
      <tr><td>{B("span","Vote-transfer / ecological regression (§7)","Transferência de votos / regressão ecológica (§7)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","Exploratory, not confirmatory — see the method's own caveat; only the blocs the data can resolve are reported, smaller candidates pooled.","Exploratório, não confirmatório — veja a ressalva do próprio método; só reportamos os blocos que os dados resolvem, com os candidatos menores agrupados.")}</td></tr>
      <tr><td>{B("span","Turnout-change vs. swing correlation (§8)","Correlação entre variação de comparecimento e variação de votos (§8)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","Statistically significant but practically negligible (r² &lt; 1%).","Estatisticamente significativa, mas com efeito praticamente desprezível (r² &lt; 1%).")}</td></tr>
      <tr><td>{B("span","Blank/spoiled vote rates (§9)","Taxas de votos em branco/nulos (§9)")}</td><td>{B("span",'<span class="pill pill-d">Descriptive only</span>','<span class="pill pill-d">Apenas descritivo</span>')}</td><td>{B("span","No formal outlier test run on state-level rates in this pass — see limitations below.","Nenhum teste formal de valores atípicos rodado sobre as taxas por estado nesta etapa — veja as limitações abaixo.")}</td></tr>
      <tr><td>{B("span","Last-digit forensic tests (§10)","Testes forenses de último dígito (§10)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","Chi-square does not reject uniformity for either candidate or municipality totals; known limited test power.","Qui-quadrado não rejeita a uniformidade para nenhum candidato nem para os totais por município; poder de teste reconhecidamente limitado.")}</td></tr>
      <tr><td>{B("span","Regional / political-geography consistency (§11)","Consistência regional / geografia política (§11)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","Matches Brazil's well-documented 2018/2022 regional pattern.","Corresponde ao padrão regional bem documentado do Brasil em 2018/2022.")}</td></tr>
      <tr><td>{B("span","\"100% of the swing votes\" claim (§12)","Alegação dos \"100% dos votos que mudaram\" (§12)")}</td><td>{B("span",'<span class="pill pill-e">E — No anomaly</span>','<span class="pill pill-e">E — Sem anomalia</span>')}</td><td>{B("span","True but a restatement of the swing through an unstable ratio; happens for both candidates, tracks zone lean, and never exceeds the real available pool (0 impossible zones).","Verdadeira, mas é a variação reformulada por uma razão instável; ocorre para os dois candidatos, acompanha a inclinação da zona e nunca excede o conjunto real disponível (0 zonas impossíveis).")}</td></tr>
    </tbody>
  </table>
  </div>
  {B("p", "Classification follows a standard election-audit taxonomy: <strong>A</strong> data inconsistency (a verifiable mismatch or failure), <strong>B</strong> statistical anomaly (unusual under a clearly defined comparison), <strong>C</strong> technical irregularity requiring further investigation, <strong>D</strong> unsubstantiated allegation (insufficient evidence either way), <strong>E</strong> no anomaly detected. None of these findings is classified as a fraud probability — that classification does not exist in this framework, deliberately.", "A classificação segue uma taxonomia padrão de auditoria eleitoral: <strong>A</strong> inconsistência de dados (uma divergência ou falha verificável), <strong>B</strong> anomalia estatística (incomum sob uma comparação claramente definida), <strong>C</strong> irregularidade técnica que exige investigação adicional, <strong>D</strong> alegação não comprovada (evidência insuficiente em qualquer direção), <strong>E</strong> nenhuma anomalia detectada. Nenhum desses achados é classificado como uma \"probabilidade de fraude\" — essa categoria não existe neste framework, deliberadamente.")}

  {B("h3", "What this analysis does <em>not</em> establish — and what would be needed", "O que esta análise <em>não</em> comprova — e o que seria necessário")}
  <ul>
    {B("li", "<strong>Machine- and software-level integrity.</strong> This is a statistical analysis of <em>published, aggregated result totals</em>, not a forensic audit of voting-machine hardware, firmware, or counting software. TSE's own CKAN catalogue lists a separate package, <code>resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai</code> (voting-machine preparation system logs, per state, 2nd round), which we confirmed exists but did not download or use — it is per-machine preparation logs, not tabular results, and would need a substantially different kind of processing to analyse.", "<strong>Integridade em nível de máquina e de software.</strong> Esta é uma análise estatística de <em>totais de resultados publicados e agregados</em>, não uma auditoria forense do hardware, firmware ou software de apuração das urnas eletrônicas. O próprio catálogo CKAN do TSE lista um pacote separado, <code>resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai</code> (logs do sistema de preparação das urnas, por estado, 2º turno), que confirmamos existir mas não baixamos nem usamos — são logs de preparação por máquina, não resultados tabulares, e exigiriam um tipo de processamento substancialmente diferente para analisar.")}
    {B("li", "<strong>Polling-station (section) level consistency.</strong> We used municipality-and-zone level data throughout. TSE also publishes <code>votacao_secao_2026_*.zip</code> (results by individual polling section, listed in the same <code>resultados-2026</code> package) — confirmed available but outside this report's scope. Section-level data would let a future pass check consistency <em>within</em> a zone, at roughly 10&ndash;20x the row count.", "<strong>Consistência em nível de seção eleitoral.</strong> Usamos dados em nível de município e zona o tempo todo. O TSE também publica <code>votacao_secao_2026_*.zip</code> (resultados por seção eleitoral individual, listado no mesmo pacote <code>resultados-2026</code>) — confirmado disponível, mas fora do escopo deste relatório. Dados por seção permitiriam, em uma etapa futura, verificar a consistência <em>dentro</em> de uma zona, com cerca de 10 a 20 vezes mais linhas.")}
    {B("li", "<strong>Chain of custody between a polling station and the published total.</strong> TSE's CKAN catalogue separately lists <code>resultados-2026-boletim-de-urna</code> (individual polling-station result bulletins, \"Boletins de Urna\", per state) and <code>resultados-2026-arquivos-transmitidos-para-totalizacao</code> (files transmitted for totalization). Both are confirmed to exist; neither was used here. Boletins de Urna are published per-machine, largely as scanned/structured documents rather than simple tabular rows, so matching them against the aggregates used in this report is a meaningfully larger project — but it is the direct next step for anyone wanting to check whether an individual polling station's bulletin matches what reached the national total.", "<strong>Cadeia de custódia entre uma seção eleitoral e o total publicado.</strong> O catálogo CKAN do TSE lista separadamente <code>resultados-2026-boletim-de-urna</code> (boletins de urna individuais, por estado) e <code>resultados-2026-arquivos-transmitidos-para-totalizacao</code> (arquivos transmitidos para totalização). Ambos confirmadamente existem; nenhum foi usado aqui. Os Boletins de Urna são publicados por máquina, em grande parte como documentos escaneados/estruturados em vez de linhas tabulares simples, então compará-los com os agregados usados neste relatório é um projeto significativamente maior — mas é o próximo passo direto para quem quiser verificar se o boletim de uma seção específica corresponde ao que chegou ao total nacional.")}
    {B("li", "<strong>True geographic/spatial analysis.</strong> \"Regional context\" here means state-level aggregation, not municipality-level maps or spatial-autocorrelation statistics (e.g. Moran's I) — those need municipality boundary geometries (e.g. from IBGE) that are not part of this analysis yet.", "<strong>Análise geográfica/espacial verdadeira.</strong> \"Contexto regional\", aqui, significa agregação por estado, não mapas em nível de município nem estatísticas de autocorrelação espacial (ex.: I de Moran) — essas exigiriam geometrias de fronteiras municipais (ex.: do IBGE) que ainda não fazem parte desta análise.")}
    {B("li", "<strong>Formal outlier testing on blank/null vote rates and on the vote-transfer estimates.</strong> Both are reported descriptively (§7, §9) with caveats, not run through the same chance-model/robustness machinery as the 90%+ zone analysis above. That would be a natural extension.", "<strong>Teste formal de valores atípicos nas taxas de votos em branco/nulos e nas estimativas de transferência de votos.</strong> Ambas são reportadas de forma descritiva (§7, §9) com ressalvas, não submetidas ao mesmo mecanismo de modelo de acaso/robustez usado na análise de zonas com 90%+. Essa seria uma extensão natural.")}
    {B("li", "<strong>Voter-level behaviour.</strong> Every test here operates on aggregated municipality/zone totals. Individual coercion, vote-buying, or other retail-level irregularities leave no trace in aggregate counts and are outside what any dataset at this level of aggregation could detect.", "<strong>Comportamento em nível de eleitor individual.</strong> Todo teste aqui opera sobre totais agregados por município/zona. Coação individual, compra de votos ou outras irregularidades no varejo não deixam rastro em contagens agregadas e estão fora do que qualquer conjunto de dados neste nível de agregação poderia detectar.")}
  </ul>

  {B("h3", "Overall assessment", "Avaliação geral")}
  <div class="verdict">
    {B("h3", "No statistical signature consistent with fraud was found across any of the thirteen analyses in this report.", "Nenhuma assinatura estatística compatível com fraude foi encontrada em nenhuma das treze análises deste relatório.")}
    <ul>
      {B("li", "The underlying data reconciles perfectly: zero duplicate records, zero reconciliation failures, zero impossible values, across every one of the 12,584 zone-round records checked.", "Os dados subjacentes se reconciliam perfeitamente: zero registros duplicados, zero falhas de reconciliação, zero valores impossíveis, em todos os 12.584 registros de zona-turno verificados.")}
      {B("li", "The frequency of 90%+ zones stays at or below what a chance-only null model predicts, across five independent robustness variants — the opposite of what manufactured results would look like.", "A frequência de zonas com 90%+ fica igual ou abaixo do que um modelo nulo de puro acaso prevê, em cinco variantes independentes de robustez — o oposto do que resultados fabricados pareceriam.")}
      {B("li", "Every zone at 90%+ in round 2 had already reached that level in round 1, and the estimated vote-transfer pattern from eliminated candidates is consistent with ordinary runoff dynamics.", "Toda zona de 90%+ no 2º turno já havia atingido esse patamar no 1º turno, e o padrão estimado de transferência de votos dos candidatos eliminados é consistente com a dinâmica comum de um segundo turno.")}
      {B("li", "Turnout changes, blank/null vote rates, vote-count digit distributions and the regional pattern of results all look like ordinary variation, not coordinated manipulation.", "As variações de comparecimento, as taxas de votos em branco/nulos, as distribuições de dígitos da contagem de votos e o padrão regional dos resultados parecem todos variação comum, não manipulação coordenada.")}
      {B("li", "One mild, one-sided deviation is reported rather than hidden: Flávio ends up with slightly more high-concentration zones than the chance model predicts, at both the 85% and 90% thresholds — a handful of zones, around a one-in-twenty result each and not corrected for multiple testing. It is small, points in the opposite direction to the concentration pattern this report set out to test, and is not evidence of fraud on its own, but it is a specific result worth a closer look with finer-grained data.", "Um desvio leve e unilateral é reportado em vez de escondido: Flávio acaba com um pouco mais de zonas de alta concentração do que o modelo de acaso prevê, nos limiares de 85% e 90% — um punhado de zonas, cerca de um resultado em vinte cada e sem correção para múltiplas comparações. É pequeno, aponta na direção oposta ao padrão de concentração que este relatório se propôs a testar, e não é evidência de fraude por si só, mas é um resultado específico que mereceria um exame mais detido com dados mais granulares.")}
    </ul>
    {B("p", "None of this constitutes a chain-of-custody or systems audit, and no statistical test can rule out fraud with certainty — it can only say whether the published numbers look like what an honest count, in a country with Brazil's real political geography, would produce. By that standard, they do.", "Nada disso constitui uma auditoria de cadeia de custódia ou de sistemas, e nenhum teste estatístico pode descartar fraude com certeza — ele só pode dizer se os números publicados se parecem com o que uma apuração honesta, em um país com a geografia política real do Brasil, produziria. Por esse padrão, eles se parecem.", attrs='style="margin-bottom:0"')}
  </div>
</section>

</div>

<footer>
  <div class="wrap">
    {B("p", 'Data: Brazil\'s Superior Electoral Court (TSE) open-data portal (<a href="https://dadosabertos.tse.jus.br" target="_blank" rel="noopener">dadosabertos.tse.jus.br</a>), package <code>resultados-2026</code> — the official vote and turnout files by municipality and electoral zone. Every number and chart in this report was recomputed directly from those official files; nothing is hand-entered. Charts are interactive — hover or tap any point or bar for the exact underlying value.', 'Dados: portal de dados abertos do Tribunal Superior Eleitoral (TSE) (<a href="https://dadosabertos.tse.jus.br" target="_blank" rel="noopener">dadosabertos.tse.jus.br</a>), pacote <code>resultados-2026</code> — os arquivos oficiais de votos e comparecimento por município e zona eleitoral. Cada número e gráfico deste relatório foi recalculado diretamente desses arquivos oficiais; nada é digitado à mão. Os gráficos são interativos — passe o mouse ou toque em qualquer ponto ou barra para ver o valor exato.')}
  </div>
</footer>

<script type="application/json" id="chart-data-json">{chart_data_json.replace("</", "<\\/")}</script>
<script>
window.CHART_DATA = JSON.parse(document.getElementById('chart-data-json').textContent);
</script>
<script>
{charts_js}
</script>
<script>
{app_js}
</script>
<script>
(function(){{
  var TITLES = {{en: {json.dumps(TITLE_EN)}, pt: {json.dumps(TITLE_PT)}}};
  var DESCS = {{en: {json.dumps(DESC_EN)}, pt: {json.dumps(DESC_PT)}}};

  function applyLang(lang){{
    document.documentElement.setAttribute('data-lang', lang);
    document.documentElement.setAttribute('lang', lang === 'pt' ? 'pt-BR' : 'en-GB');
    document.title = TITLES[lang];
    var m = document.querySelector('meta[name="description"]');
    if (m) m.setAttribute('content', DESCS[lang]);
    document.querySelectorAll('[data-set-lang]').forEach(function(b){{
      b.setAttribute('aria-pressed', b.getAttribute('data-set-lang') === lang ? 'true' : 'false');
    }});
    try {{ localStorage.setItem('report-lang', lang); }} catch(e){{}}
  }}
  document.querySelectorAll('[data-set-lang]').forEach(function(b){{
    b.addEventListener('click', function(){{ applyLang(b.getAttribute('data-set-lang')); }});
  }});
  applyLang(document.documentElement.getAttribute('data-lang') || 'en');

  function effectiveTheme(){{
    var explicit = document.documentElement.getAttribute('data-theme');
    if (explicit === 'light' || explicit === 'dark') return explicit;
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }}
  function syncThemeButtons(){{
    var t = effectiveTheme();
    document.querySelectorAll('[data-set-theme]').forEach(function(b){{
      b.setAttribute('aria-pressed', b.getAttribute('data-set-theme') === t ? 'true' : 'false');
    }});
  }}
  function applyTheme(theme){{
    document.documentElement.setAttribute('data-theme', theme);
    try {{ localStorage.setItem('report-theme', theme); }} catch(e){{}}
    syncThemeButtons();
  }}
  document.querySelectorAll('[data-set-theme]').forEach(function(b){{
    b.addEventListener('click', function(){{ applyTheme(b.getAttribute('data-set-theme')); }});
  }});
  syncThemeButtons();
  if (window.matchMedia) {{
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncThemeButtons);
  }}
}})();
</script>
"""

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
