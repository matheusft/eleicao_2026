// Wires CHART_DATA (embedded by render_report.py) into the chart toolkit,
// and re-renders every chart's text/number formatting in the current
// language (English UK / Brazilian Portuguese) whenever the page's
// data-lang attribute changes.
(function () {
  "use strict";
  const C = window.ReportCharts;
  const D = window.CHART_DATA;
  const [UF, MUN, ZONA, ABROAD, N, P2, P1, DTURN, SWING] = [0, 1, 2, 3, 4, 5, 6, 7, 8];
  let funnelHandle = null; // set by renderFunnel(); used by the Figure 3 search box
  let r1vsr2Handle = null; // set by renderR1vsR2(); used by the Figure 5 search box

  const I18N = {
    en: {
      locale: "en-GB",
      abroadTag: " (abroad)",
      search: {
        placeholder: "Search for a municipality…",
        noResults: "No municipality matches that search",
        abroad: "abroad",
      },
      national: {
        r1Tooltip: "Round 1 share",
        r2Tooltip: "Round 2 share",
        votes: "Total votes",
      },
      zoneHist: {
        valueLabel: "Number of electoral zones",
        categoryLabel: "Lula's share of the two-candidate vote in the zone",
        binRange: (lo, hi) => `${lo}%–${hi}%`,
        zonesInRange: "Zones in this range",
        lulaMarker: (n) => `${n} zones, Lula ≥90%`,
        flavioMarker: (n) => `${n} zones, Flávio ≥90%`,
      },
      funnel: {
        xLabel: "Zone size (two-candidate valid votes, log scale)",
        yLabel: "Lula's share of the two-candidate vote (%)",
        legendOther: "All other zones",
        legendLandslide: "≥90% for one candidate",
        zone: "Zone",
        twoCandVotes: "Two-candidate votes",
        lulaR2: "Lula's share (R2)",
        lulaR1: "Lula's share (R1)",
      },
      r1vsr2: {
        xLabel: "Lula's 2-candidate share in round 1 (%)",
        yLabel: "Lula's share in round 2 (%)",
        zone: "Zone",
        r1share: "Round 1 share",
        r2share: "Round 2 share",
        swing: "Swing",
      },
      swing: {
        categoryLabel: "Zone swing to Lula, round 1 → 2 (pts)",
        valueLabel: "Number of zones",
        zones: "Zones",
        meanMarker: (m) => `mean ${m}pt`,
        xLabel: "Turnout-rate change, round 1 → 2 (pts)",
        yLabel: "Swing to Lula (pts)",
        turnoutChange: "Turnout-rate change",
        swingToLula: "Swing to Lula",
        binRangePts: (lo, hi) => `${lo} to ${hi} pts`,
      },
      mc: {
        valueLabel: (n) => `Simulated trials (of ${n})`,
        categoryLabel: "Simulated count of 90%+ zones (per trial)",
        tooltipTitle: (k) => `${k} zones ≥90%`,
        simulatedTrials: "Simulated trials",
        actualMarker: (n) => `actual = ${n}`,
        meanMarker: (m) => `chance avg ${m}`,
        titleLula: "If chance alone drove Lula's 90%+ zones",
        titleFlavio: "If chance alone drove Flávio's 90%+ zones",
        legendBand: "Where 90% of simulations land",
      },
      digit: {
        valueLabel: "Zones",
        categoryLabel: "Last digit of vote count",
        tooltipTitle: (d) => `Last digit ${d}`,
        zones: "Zones",
        expected: "Expected (uniform)",
      },
      state: {
        legendR1: "Round 1 (2-cand. share)",
        legendR2: "Round 2",
        r1: "Round 1",
        r2: "Round 2",
        swing: "Swing",
        swingPts: (v) => `${v} pts`,
      },
      stateTurnout: {
        legendR1: "Round 1",
        legendR2: "Round 2",
        r1: "Round 1",
        r2: "Round 2",
        change: "Change",
        changePts: (v) => `${v} pts`,
      },
      transfer: {
        legendLula: "Estimated to Lula",
        legendFlavio: "Estimated to Flávio",
        otherName: "Other candidates",
        r1Votes: "Round-1 votes",
        toLula: "Estimated share to Lula",
        toFlavio: "Estimated share to Flávio",
        range90: (lo, hi) => `90% range: ${lo}–${hi}`,
        poorlyIdentified: "Too collinear with a larger candidate to estimate reliably — treat as inconclusive",
      },
      blankNull: {
        categoryLabel: "",
        valueLabel: "Rate (% of turnout)",
        blank: "Blank votes",
        nulls: "Spoiled (null) votes",
        round1: "Round 1",
        round2: "Round 2",
      },
    },
    pt: {
      locale: "pt-BR",
      abroadTag: " (exterior)",
      search: {
        placeholder: "Buscar por município…",
        noResults: "Nenhum município corresponde a essa busca",
        abroad: "exterior",
      },
      national: {
        r1Tooltip: "Percentual no 1º turno",
        r2Tooltip: "Percentual no 2º turno",
        votes: "Total de votos",
      },
      zoneHist: {
        valueLabel: "Número de zonas eleitorais",
        categoryLabel: "Percentual de Lula no total de dois candidatos na zona",
        binRange: (lo, hi) => `${lo}%–${hi}%`,
        zonesInRange: "Zonas nessa faixa",
        lulaMarker: (n) => `${n} zonas, Lula ≥90%`,
        flavioMarker: (n) => `${n} zonas, Flávio ≥90%`,
      },
      funnel: {
        xLabel: "Tamanho da zona (votos válidos de 2 candidatos, escala log)",
        yLabel: "Percentual de Lula no total de dois candidatos (%)",
        legendOther: "Todas as outras zonas",
        legendLandslide: "≥90% para um candidato",
        zone: "Zona",
        twoCandVotes: "Votos (2 candidatos)",
        lulaR2: "Percentual de Lula (2T)",
        lulaR1: "Percentual de Lula (1T)",
      },
      r1vsr2: {
        xLabel: "Percentual de Lula (2 candidatos) no 1º turno (%)",
        yLabel: "Percentual de Lula no 2º turno (%)",
        zone: "Zona",
        r1share: "Percentual no 1º turno",
        r2share: "Percentual no 2º turno",
        swing: "Variação",
      },
      swing: {
        categoryLabel: "Variação para Lula por zona, 1º → 2º turno (pts)",
        valueLabel: "Número de zonas",
        zones: "Zonas",
        meanMarker: (m) => `média ${m}pt`,
        xLabel: "Variação do comparecimento, 1º → 2º turno (pts)",
        yLabel: "Variação para Lula (pts)",
        turnoutChange: "Variação do comparecimento",
        swingToLula: "Variação para Lula",
        binRangePts: (lo, hi) => `${lo} a ${hi} pts`,
      },
      mc: {
        valueLabel: (n) => `Simulações (de ${n})`,
        categoryLabel: "Número simulado de zonas com 90%+ (por simulação)",
        tooltipTitle: (k) => `${k} zonas ≥90%`,
        simulatedTrials: "Simulações",
        actualMarker: (n) => `real = ${n}`,
        meanMarker: (m) => `média do acaso ${m}`,
        titleLula: "Se só o acaso gerasse as zonas de 90%+ de Lula",
        titleFlavio: "Se só o acaso gerasse as zonas de 90%+ de Flávio",
        legendBand: "Onde caem 90% das simulações",
      },
      digit: {
        valueLabel: "Zonas",
        categoryLabel: "Último dígito da contagem de votos",
        tooltipTitle: (d) => `Último dígito ${d}`,
        zones: "Zonas",
        expected: "Esperado (uniforme)",
      },
      state: {
        legendR1: "1º turno (2 candidatos)",
        legendR2: "2º turno",
        r1: "1º turno",
        r2: "2º turno",
        swing: "Variação",
        swingPts: (v) => `${v} pts`,
      },
      stateTurnout: {
        legendR1: "1º turno",
        legendR2: "2º turno",
        r1: "1º turno",
        r2: "2º turno",
        change: "Variação",
        changePts: (v) => `${v} pts`,
      },
      transfer: {
        legendLula: "Estimado para Lula",
        legendFlavio: "Estimado para Flávio",
        otherName: "Outros candidatos",
        r1Votes: "Votos no 1º turno",
        toLula: "Percentual estimado para Lula",
        toFlavio: "Percentual estimado para Flávio",
        range90: (lo, hi) => `faixa de 90%: ${lo}–${hi}`,
        poorlyIdentified: "Colinear demais com um candidato maior para estimar com confiança — trate como inconclusivo",
      },
      blankNull: {
        categoryLabel: "",
        valueLabel: "Taxa (% do comparecimento)",
        blank: "Votos em branco",
        nulls: "Votos nulos",
        round1: "1º turno",
        round2: "2º turno",
      },
    },
  };

  function currentLang() {
    const l = document.documentElement.getAttribute("data-lang");
    return l === "pt" ? "pt" : "en";
  }

  function col() {
    return {
      lula: C.COLOR.lula(),
      flavio: C.COLOR.flavio(),
      accent: C.COLOR.accent(),
      muted: C.COLOR.muted(),
    };
  }

  function zoneTitle(z, S) {
    return `${z[MUN]}${z[ABROAD] ? S.abroadTag : ""} / ${z[UF]}`;
  }

  // ---------------- 1. National results ----------------
  function renderNational(S, locale) {
    const CL = col();
    const nameColor = (name) => (name === "Lula" ? CL.lula : name === "Flavio Bolsonaro" ? CL.flavio : CL.muted);
    const r1 = D.national.round1.map((d) => ({ key: d[0], label: d[0] === "Flavio Bolsonaro" ? "Flávio Bolsonaro" : d[0], value: d[1], votes: d[2], color: nameColor(d[0]), valueLabel: d[1].toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%" }));
    C.renderBars("chart-national-r1", r1, {
      orientation: "horizontal",
      width: 620,
      height: 400,
      margin: { top: 10, right: 60, bottom: 36, left: 150 },
      valueDomain: [0, Math.max(...r1.map((b) => b.value)) * 1.25],
      valueTickFormat: (v) => v.toFixed(0) + "%",
      tooltipFn: (b) => ({ title: b.label, rows: [
        { label: S.national.r1Tooltip, value: b.value.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%", color: b.color },
        { label: S.national.votes, value: C.fmtInt(b.votes, locale) },
      ] }),
    });
    const r2 = D.national.round2.map((d) => ({ key: d[0], label: d[0] === "Flavio Bolsonaro" ? "Flávio Bolsonaro (PL)" : "Lula (PT)", value: d[1], votes: d[2], color: nameColor(d[0]), valueLabel: d[1].toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%" }));
    C.renderBars("chart-national-r2", r2, {
      orientation: "horizontal",
      width: 620,
      height: 170,
      margin: { top: 8, right: 64, bottom: 34, left: 150 },
      valueDomain: [0, 100],
      valueTickFormat: (v) => v.toFixed(0) + "%",
      tooltipFn: (b) => ({ title: b.label, rows: [
        { label: S.national.r2Tooltip, value: b.value.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%", color: b.color },
        { label: S.national.votes, value: C.fmtInt(b.votes, locale) },
      ] }),
    });
  }

  // ---------------- 2. Zone histogram ----------------
  function renderZoneHistogram(S, locale) {
    const CL = col();
    const binW = 2;
    const nbins = 50;
    const counts = new Array(nbins).fill(0);
    let nLula90 = 0,
      nFlavio90 = 0;
    D.zones.forEach((z) => {
      const share = z[P2] * 100;
      if (share >= 90) nLula90++;
      if (share <= 10) nFlavio90++;
      let bin = Math.floor(share / binW);
      if (bin < 0) bin = 0;
      if (bin > nbins - 1) bin = nbins - 1;
      counts[bin]++;
    });
    const bars = counts.map((c, i) => ({ key: i, label: i % 5 === 0 ? i * binW + "%" : "", value: c, color: CL.muted, bin: i }));
    C.renderBars("chart-zone-hist", bars, {
      width: 760,
      height: 380,
      maxXLabels: 11,
      valueLabel: S.zoneHist.valueLabel,
      categoryLabel: S.zoneHist.categoryLabel,
      tooltipFn: (b) => ({
        title: S.zoneHist.binRange(b.bin * binW, b.bin * binW + binW),
        rows: [{ label: S.zoneHist.zonesInRange, value: C.fmtInt(b.value, locale), color: CL.muted }],
      }),
      markers: [
        { key: 45, label: S.zoneHist.lulaMarker(nLula90), color: CL.lula, align: "left" },
        { key: 5, label: S.zoneHist.flavioMarker(nFlavio90), color: CL.flavio, align: "right" },
      ],
    });
  }

  // Lula's national round-2 two-candidate share, read from the data (not
  // hard-coded), used as the reference line in the funnel chart.
  function lulaNationalR2() {
    const row = (D.national.round2 || []).find((d) => d[0] === "Lula");
    return row ? row[1] : 50;
  }

  // ---------------- 3. Funnel ----------------
  function renderFunnel(S, locale) {
    const CL = col();
    const ns = D.zones.map((z) => z[N]);
    const xDomain = [Math.max(1, Math.min(...ns) * 0.8), Math.max(...ns) * 1.15];
    const points = D.zones.map((z) => {
      const share = z[P2] * 100;
      const landslide = share >= 90 || share <= 10;
      return {
        x: z[N],
        y: share,
        color: landslide ? CL.accent : CL.muted,
        op: landslide ? 0.95 : 0.35,
        r: landslide ? 3.6 : 2,
        meta: z,
      };
    });
    funnelHandle = C.renderScatter("chart-funnel", points, {
      width: 780,
      height: 460,
      xType: "log",
      xDomain,
      yDomain: [-2, 102],
      xLabel: S.funnel.xLabel,
      yLabel: S.funnel.yLabel,
      xTickFormat: (v) => (v >= 1000 ? v / 1000 + "k" : String(v)),
      yTickFormat: (v) => v + "%",
      hlines: [
        { y: 90, cls: "refline-dotted" },
        { y: 10, cls: "refline-dotted" },
        { y: lulaNationalR2(), cls: "refline" },
      ],
      legend: [
        { color: CL.muted, label: S.funnel.legendOther },
        { color: CL.accent, label: S.funnel.legendLandslide },
      ],
      tooltipFn: (p) => {
        const z = p.meta;
        const rows = [
          { label: S.funnel.zone, value: `#${z[ZONA]}` },
          { label: S.funnel.twoCandVotes, value: C.fmtInt(z[N], locale) },
          { label: S.funnel.lulaR2, value: C.fmtPct(z[P2] * 100, 2, locale), color: CL.lula },
        ];
        if (z[P1] !== null) rows.push({ label: S.funnel.lulaR1, value: C.fmtPct(z[P1] * 100, 2, locale) });
        return { title: zoneTitle(z, S), rows };
      },
    });
  }

  // ---------------- 4. Round1 vs Round2 ----------------
  function renderR1vsR2(S, locale) {
    const CL = col();
    const points = D.zones
      .filter((z) => z[P1] !== null)
      .map((z) => {
        const share = z[P2] * 100;
        const landslide = share >= 90 || share <= 10;
        return {
          x: z[P1] * 100,
          y: share,
          color: landslide ? CL.accent : CL.muted,
          op: landslide ? 0.95 : 0.3,
          r: landslide ? 3.6 : 1.8,
          meta: z,
        };
      });
    r1vsr2Handle = C.renderScatter("chart-r1-vs-r2", points, {
      width: 620,
      height: 620,
      margin: { top: 16, right: 20, bottom: 50, left: 56 },
      xType: "linear",
      xDomain: [0, 100],
      yDomain: [0, 100],
      xLabel: S.r1vsr2.xLabel,
      yLabel: S.r1vsr2.yLabel,
      xTickFormat: (v) => v + "%",
      yTickFormat: (v) => v + "%",
      diagonal: true,
      tooltipFn: (p) => {
        const z = p.meta;
        return {
          title: zoneTitle(z, S),
          rows: [
            { label: S.r1vsr2.zone, value: `#${z[ZONA]}` },
            { label: S.r1vsr2.r1share, value: C.fmtPct(z[P1] * 100, 2, locale) },
            { label: S.r1vsr2.r2share, value: C.fmtPct(z[P2] * 100, 2, locale), color: CL.lula },
            { label: S.r1vsr2.swing, value: (z[SWING] >= 0 ? "+" : "") + C.fmtPct(z[SWING] * 100, 2, locale) },
          ],
        };
      },
    });
  }

  // ---------------- 5. Swing histogram + turnout scatter ----------------
  function renderSwing(S, locale) {
    const CL = col();
    const swings = D.zones.filter((z) => z[SWING] !== null).map((z) => z[SWING] * 100);
    const lo = Math.min(...swings),
      hi = Math.max(...swings);
    const binW = (hi - lo) / 55;
    const nbins = Math.ceil((hi - lo) / binW) + 1;
    const counts = new Array(nbins).fill(0);
    swings.forEach((s) => {
      let bin = Math.floor((s - lo) / binW);
      if (bin < 0) bin = 0;
      if (bin > nbins - 1) bin = nbins - 1;
      counts[bin]++;
    });
    const mean = swings.reduce((a, b) => a + b, 0) / swings.length;
    const meanBin = Math.round((mean - lo) / binW);
    const bars = counts.map((c, i) => ({ key: i, label: i % 10 === 0 ? (lo + i * binW).toFixed(0) : "", value: c, color: CL.accent, lo: lo + i * binW, hi: lo + (i + 1) * binW }));
    C.renderBars("chart-swing-hist", bars, {
      width: 460,
      height: 380,
      valueLabel: S.swing.valueLabel,
      categoryLabel: S.swing.categoryLabel,
      tooltipFn: (b) => ({ title: S.swing.binRangePts(b.lo.toFixed(1), b.hi.toFixed(1)), rows: [{ label: S.swing.zones, value: C.fmtInt(b.value, locale), color: CL.accent }] }),
      markers: [{ key: meanBin, label: S.swing.meanMarker(mean.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })), color: C.COLOR.textStrong(), align: "left" }],
    });

    const sample = D.zones.filter((z) => z[DTURN] !== null && z[SWING] !== null);
    const xs = sample.map((z) => z[DTURN] * 100);
    const ys = sample.map((z) => z[SWING] * 100);
    const r = C.pearsonR(xs, ys);
    const { slope, intercept } = C.linreg(xs, ys);
    const xDomain = [Math.min(...xs), Math.max(...xs)];
    const points = sample.map((z, i) => ({ x: xs[i], y: ys[i], color: CL.muted, op: 0.25, r: 1.8, meta: z }));
    C.renderScatter("chart-swing-scatter", points, {
      width: 460,
      height: 380,
      margin: { top: 28, right: 20, bottom: 50, left: 56 },
      xType: "linear",
      xDomain,
      yDomain: [Math.min(...ys) * 1.05, Math.max(...ys) * 1.05],
      xLabel: S.swing.xLabel,
      yLabel: S.swing.yLabel,
      xTickFormat: (v) => v.toFixed(0),
      yTickFormat: (v) => v.toFixed(0),
      lineSegments: [{ x1: xDomain[0], y1: slope * xDomain[0] + intercept, x2: xDomain[1], y2: slope * xDomain[1] + intercept, cls: "trendline" }],
      hitRadius: 14,
      tooltipFn: (p) => {
        const z = p.meta;
        return {
          title: zoneTitle(z, S),
          rows: [
            { label: S.swing.turnoutChange, value: (z[DTURN] >= 0 ? "+" : "") + C.fmtPct(z[DTURN] * 100, 2, locale) },
            { label: S.swing.swingToLula, value: (z[SWING] >= 0 ? "+" : "") + C.fmtPct(z[SWING] * 100, 2, locale), color: CL.accent },
          ],
        };
      },
    });
    // Both language captions are kept in sync on every render (CSS alone
    // decides which one is visible), so a mid-render language switch never
    // shows a stale value.
    ["en", "pt"].forEach((capLang) => {
      const capLocale = I18N[capLang].locale;
      const caption = document.getElementById(`swing-corr-caption-${capLang}`);
      if (caption) caption.textContent = `r = ${r.toLocaleString(capLocale, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}  (n = ${xs.length.toLocaleString(capLocale)})`;
    });
  }

  // ---------------- 6. Monte Carlo ----------------
  function percentile(sortedArr, q) {
    const pos = (sortedArr.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sortedArr[base + 1] !== undefined) return sortedArr[base] + rest * (sortedArr[base + 1] - sortedArr[base]);
    return sortedArr[base];
  }

  function renderMonteCarlo(S, locale) {
    const CL = col();
    function panel(containerId, sims, actual, color) {
      const lo = Math.min(Math.min(...sims), actual),
        hi = Math.max(Math.max(...sims), actual);
      const counts = new Map();
      for (let v = lo; v <= hi; v++) counts.set(v, 0);
      sims.forEach((v) => counts.set(v, (counts.get(v) || 0) + 1));
      const bars = [];
      for (let v = lo; v <= hi; v++) bars.push({ key: v, label: String(v), value: counts.get(v), color: CL.muted });
      const mean = sims.reduce((a, b) => a + b, 0) / sims.length;
      const sorted = sims.slice().sort((a, b) => a - b);
      const p05 = Math.round(percentile(sorted, 0.05));
      const p95 = Math.round(percentile(sorted, 0.95));
      C.renderBars(containerId, bars, {
        width: 460,
        height: 340,
        margin: { top: 34, right: 16, bottom: 46, left: 56 },
        valueLabel: S.mc.valueLabel(D.monte_carlo.n_sim.toLocaleString(locale)),
        categoryLabel: S.mc.categoryLabel,
        maxXLabels: 10,
        tooltipFn: (b) => ({ title: S.mc.tooltipTitle(b.key), rows: [{ label: S.mc.simulatedTrials, value: C.fmtInt(b.value, locale), color: CL.muted }] }),
        refBands: [{ lo: p05, hi: p95, color: C.COLOR.muted(), opacity: 0.18 }],
        refMarkers: [
          // Place the mean label a line lower than the "actual" label so the
          // two never collide when the mean and the actual count are close
          // (as they are in the Flávio panel).
          { value: mean, label: S.mc.meanMarker(mean.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })), color: C.COLOR.textStrong(), align: actual < mean ? "left" : "right", dashed: true, labelY: 30 },
        ],
        markers: [{ key: actual, label: S.mc.actualMarker(actual), color: color, align: actual < (lo + hi) / 2 ? "right" : "left" }],
      });
    }
    panel("chart-mc-lula", D.monte_carlo.sims_lula90, D.monte_carlo.actual_lula90, CL.lula);
    panel("chart-mc-flavio", D.monte_carlo.sims_flavio90, D.monte_carlo.actual_flavio90, CL.flavio);
  }

  // ---------------- 7. Digit tests ----------------
  function renderDigitTest(S, locale) {
    const CL = col();
    function panel(containerId, test, color) {
      const bars = test.observed.map((v, i) => ({ key: i, label: String(i), value: v, color }));
      C.renderBars(containerId, bars, {
        width: 460,
        height: 320,
        valueLabel: S.digit.valueLabel,
        categoryLabel: S.digit.categoryLabel,
        refLine: test.expected_per_digit,
        tooltipFn: (b) => ({
          title: S.digit.tooltipTitle(b.key),
          rows: [
            { label: S.digit.zones, value: C.fmtInt(b.value, locale), color },
            { label: S.digit.expected, value: test.expected_per_digit.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) },
          ],
        }),
      });
    }
    panel("chart-digit-lula", D.digit_lula, CL.lula);
    panel("chart-digit-flavio", D.digit_flavio, CL.flavio);
  }

  // ---------------- 8. State swing ----------------
  function renderStateSwing(S, locale) {
    const CL = col();
    const rows = D.state_table
      .slice()
      .sort((a, b) => b[2] - a[2])
      .map((r) => ({ label: r[0], v1: r[1] * 100, v2: r[2] * 100, color1: CL.muted, color2: CL.accent }));
    C.renderDotLine("chart-state-swing", rows, {
      width: 680,
      height: rows.length * 26 + 50,
      xDomain: [15, 80],
      xTickFormat: (v) => v + "%",
      legend: [
        { color: CL.muted, label: S.state.legendR1 },
        { color: CL.accent, label: S.state.legendR2 },
      ],
      tooltipFn: (r) => ({
        title: r.label,
        rows: [
          { label: S.state.r1, value: C.fmtPct(r.v1, 1, locale) },
          { label: S.state.r2, value: C.fmtPct(r.v2, 1, locale), color: CL.accent },
          { label: S.state.swing, value: (r.v2 - r.v1 >= 0 ? "+" : "") + S.state.swingPts((r.v2 - r.v1).toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })) },
        ],
      }),
    });
  }

  const CANDIDATE_DISPLAY = {
    LULA: "Lula",
    "FLAVIO BOLSONARO": "Flávio Bolsonaro",
    "RONALDO CAIADO": "Ronaldo Caiado",
    "ESCRITOR AUGUSTO CURY": "Escritor Augusto Cury",
    "RENAN SANTOS": "Renan Santos",
  };

  // ---------------- 9. Vote transfer (where did round-1 votes go) ----------------
  function renderVoteTransfer(S, locale) {
    const CL = col();
    const cands = D.vote_transfer.candidates.slice();
    const finalists = cands.filter((c) => c.candidate === "LULA" || c.candidate === "FLAVIO BOLSONARO");
    const others = cands.filter((c) => c.candidate !== "LULA" && c.candidate !== "FLAVIO BOLSONARO" && c.candidate !== "OTHER").sort((a, b) => b.r1_votes - a.r1_votes);
    const other = cands.filter((c) => c.candidate === "OTHER");
    const ordered = [...finalists, ...others, ...other];

    const pctStr = (v) => (v * 100).toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
    const rows = ordered.map((c) => {
      const name = c.candidate === "OTHER" ? S.transfer.otherName : CANDIDATE_DISPLAY[c.candidate] || c.candidate;
      return {
        label: name + (c.poorly_identified ? " †" : ""),
        meta: c,
        segments: [
          { value: c.lula_rate, color: CL.lula, which: "lula" },
          { value: c.flavio_rate, color: CL.flavio, which: "flavio" },
        ],
      };
    });

    C.renderStackedBars("chart-vote-transfer", rows, {
      width: 740,
      height: rows.length * 46 + 70,
      margin: { top: 10, right: 20, bottom: 60, left: 180 },
      legend: [
        { color: CL.lula, label: S.transfer.legendLula },
        { color: CL.flavio, label: S.transfer.legendFlavio },
      ],
      tooltipFn: (r, seg) => {
        const c = r.meta;
        const isLula = seg.which === "lula";
        const rate = isLula ? c.lula_rate : c.flavio_rate;
        const lo = isLula ? c.lula_rate_lo : c.flavio_rate_lo;
        const hiVal = isLula ? c.lula_rate_hi : c.flavio_rate_hi;
        const rows = [
          { label: isLula ? S.transfer.toLula : S.transfer.toFlavio, value: pctStr(rate), color: seg.color },
          { label: S.transfer.range90(pctStr(lo), pctStr(hiVal)), value: "" },
          { label: S.transfer.r1Votes, value: C.fmtInt(c.r1_votes, locale) },
        ];
        if (c.poorly_identified) rows.push({ label: S.transfer.poorlyIdentified, value: "" });
        return { title: r.label.replace(" †", ""), rows: rows.filter((x) => x.value !== "" || x.label) };
      },
    });
  }

  // ---------------- 10. Blank and null votes ----------------
  function renderBlankNull(S, locale) {
    const CL = col();
    const bn = D.blank_null;
    const rows = [
      { key: "blank1", label: S.blankNull.blank + " — " + S.blankNull.round1, value: bn.round1.blank_rate_pct, color: CL.muted },
      { key: "blank2", label: S.blankNull.blank + " — " + S.blankNull.round2, value: bn.round2.blank_rate_pct, color: CL.accent },
      { key: "null1", label: S.blankNull.nulls + " — " + S.blankNull.round1, value: bn.round1.null_rate_pct, color: CL.muted },
      { key: "null2", label: S.blankNull.nulls + " — " + S.blankNull.round2, value: bn.round2.null_rate_pct, color: CL.accent },
    ];
    C.renderBars("chart-blank-null", rows, {
      orientation: "horizontal",
      width: 620,
      height: 220,
      margin: { top: 10, right: 60, bottom: 36, left: 190 },
      valueDomain: [0, Math.max(...rows.map((r) => r.value)) * 1.25],
      valueTickFormat: (v) => v.toFixed(1) + "%",
      tooltipFn: (b) => ({ title: b.label, rows: [{ label: S.blankNull.valueLabel, value: b.value.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%", color: b.color }] }),
    });
  }

  // ---------------- 11. Turnout / abstention by state ----------------
  function renderStateTurnout(S, locale) {
    const CL = col();
    const rows = D.state_table
      .filter((r) => r[3] !== null && r[4] !== null)
      .slice()
      .sort((a, b) => b[4] - a[4])
      .map((r) => ({ label: r[0], v1: r[3], v2: r[4], color1: CL.muted, color2: CL.accent }));
    C.renderDotLine("chart-state-turnout", rows, {
      width: 680,
      height: rows.length * 26 + 50,
      xDomain: [10, 30],
      xTickFormat: (v) => v + "%",
      legend: [
        { color: CL.muted, label: S.stateTurnout.legendR1 },
        { color: CL.accent, label: S.stateTurnout.legendR2 },
      ],
      tooltipFn: (r) => ({
        title: r.label,
        rows: [
          { label: S.stateTurnout.r1, value: C.fmtPct(r.v1, 1, locale) },
          { label: S.stateTurnout.r2, value: C.fmtPct(r.v2, 1, locale), color: CL.accent },
          { label: S.stateTurnout.change, value: (r.v2 - r.v1 >= 0 ? "+" : "") + S.stateTurnout.changePts((r.v2 - r.v1).toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })) },
        ],
      }),
    });
  }

  // ---------------- Chart search boxes (Figure 3, Figure 5) ----------------
  // Wired once per chart (the input/dropdown/clear-button DOM is static,
  // server-rendered HTML that survives chart re-renders); only the scatter
  // handle (reassigned by the render function on every init()) changes
  // underneath it. `zones` is the exact array the chart built its `points`
  // from, so array index == the index renderScatter expects.
  function setupChartSearch({ idPrefix, zones, chartContainerId, getHandle }) {
    const input = document.getElementById(`${idPrefix}-search-input`);
    const resultsEl = document.getElementById(`${idPrefix}-search-results`);
    const clearBtn = document.getElementById(`${idPrefix}-search-clear`);
    if (!input || !resultsEl || !clearBtn) return;

    function normalize(s) {
      return s
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase();
    }

    const index = zones.map((z, i) => ({
      i,
      norm: normalize(`${z[MUN]} ${z[UF]}`),
      muni: z[MUN],
      uf: z[UF],
      zona: z[ZONA],
      abroad: z[ABROAD],
    }));

    let activeIndex = -1;
    let currentMatches = [];

    function closeDropdown() {
      resultsEl.hidden = true;
      resultsEl.textContent = "";
      input.setAttribute("aria-expanded", "false");
      activeIndex = -1;
    }

    function updateActive(items) {
      items.forEach((li, idx) => li.setAttribute("aria-selected", idx === activeIndex ? "true" : "false"));
      if (activeIndex >= 0 && items[activeIndex]) items[activeIndex].scrollIntoView({ block: "nearest" });
    }

    function selectMatch(m) {
      input.value = `${m.muni} / ${m.uf}`;
      clearBtn.hidden = false;
      closeDropdown();
      const handle = getHandle();
      if (!handle) return;
      const pos = handle.selectByIndex(m.i);
      if (pos) {
        const el = document.getElementById(chartContainerId);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }

    function renderResults(matches) {
      currentMatches = matches;
      activeIndex = -1;
      resultsEl.textContent = "";
      const S = I18N[currentLang()].search;
      if (matches.length === 0) {
        const li = document.createElement("li");
        li.className = "empty";
        li.textContent = S.noResults;
        resultsEl.appendChild(li);
      } else {
        matches.forEach((m) => {
          const li = document.createElement("li");
          li.setAttribute("role", "option");
          li.setAttribute("aria-selected", "false");
          const muniSpan = document.createElement("span");
          muniSpan.className = "muni";
          muniSpan.textContent = m.muni + (m.abroad ? ` (${S.abroad})` : "");
          const meta = document.createElement("span");
          meta.className = "meta";
          meta.textContent = `${m.uf} · #${m.zona}`;
          li.appendChild(muniSpan);
          li.appendChild(meta);
          li.addEventListener("mousedown", (ev) => {
            ev.preventDefault(); // fire before the input's blur-triggered close
            selectMatch(m);
          });
          resultsEl.appendChild(li);
        });
      }
      resultsEl.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    input.addEventListener("input", () => {
      const q = input.value.trim();
      clearBtn.hidden = q.length === 0;
      if (q.length < 2) {
        closeDropdown();
        const handle = getHandle();
        if (handle) handle.clearSelection();
        return;
      }
      const nq = normalize(q);
      renderResults(index.filter((m) => m.norm.includes(nq)).slice(0, 8));
    });

    input.addEventListener("keydown", (ev) => {
      if (resultsEl.hidden) return;
      const items = Array.from(resultsEl.querySelectorAll('li[role="option"]'));
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        updateActive(items);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        updateActive(items);
      } else if (ev.key === "Enter") {
        if (activeIndex >= 0 && currentMatches[activeIndex]) {
          ev.preventDefault();
          selectMatch(currentMatches[activeIndex]);
        }
      } else if (ev.key === "Escape") {
        closeDropdown();
      }
    });

    input.addEventListener("blur", () => {
      setTimeout(closeDropdown, 100); // let a mousedown selection register first
    });

    clearBtn.addEventListener("click", () => {
      input.value = "";
      clearBtn.hidden = true;
      closeDropdown();
      const handle = getHandle();
      if (handle) handle.clearSelection();
      input.focus();
    });
  }

  function init() {
    const lang = currentLang();
    const S = I18N[lang];
    const locale = S.locale;
    renderNational(S, locale);
    renderZoneHistogram(S, locale);
    renderFunnel(S, locale);
    renderR1vsR2(S, locale);
    renderSwing(S, locale);
    renderMonteCarlo(S, locale);
    renderDigitTest(S, locale);
    renderStateSwing(S, locale);
    renderStateTurnout(S, locale);
    renderVoteTransfer(S, locale);
    renderBlankNull(S, locale);

    // The charts underneath the search boxes were just torn down and
    // rebuilt (new highlight circle, new handle), so any previous
    // selection no longer points at anything real -- reset the search
    // UI to match.
    ["funnel", "r1vsr2"].forEach((idPrefix) => {
      const searchInput = document.getElementById(`${idPrefix}-search-input`);
      const searchClear = document.getElementById(`${idPrefix}-search-clear`);
      if (searchInput) {
        searchInput.placeholder = S.search.placeholder;
        searchInput.setAttribute("aria-label", S.search.placeholder);
        searchInput.value = "";
      }
      if (searchClear) searchClear.hidden = true;
      const searchResults = document.getElementById(`${idPrefix}-search-results`);
      if (searchResults) {
        searchResults.hidden = true;
        searchResults.textContent = "";
      }
    });
  }

  window.ReportApp = { init, currentLang };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  setupChartSearch({
    idPrefix: "funnel",
    zones: D.zones,
    chartContainerId: "chart-funnel",
    getHandle: () => funnelHandle,
  });
  setupChartSearch({
    idPrefix: "r1vsr2",
    zones: D.zones.filter((z) => z[P1] !== null),
    chartContainerId: "chart-r1-vs-r2",
    getHandle: () => r1vsr2Handle,
  });

  // Re-render with new colors/text when the viewer toggles light/dark theme
  // or switches language (both are attributes on <html>).
  let rerenderQueued = false;
  function queueRerender() {
    if (rerenderQueued) return;
    rerenderQueued = true;
    requestAnimationFrame(() => {
      rerenderQueued = false;
      init();
    });
  }
  new MutationObserver(queueRerender).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-lang"] });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", queueRerender);
  }
})();
