// Vanilla-JS interactive chart toolkit for the election forensics report.
// No external dependencies (Artifact CSP blocks CDNs). Colors are read from
// CSS custom properties set on :root, so charts follow the page's light/dark
// theme automatically.
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const CSS = getComputedStyle(document.documentElement);
  function cssVar(name) {
    return CSS.getPropertyValue(name).trim();
  }
  const COLOR = {
    lula: () => cssVar("--lula"),
    flavio: () => cssVar("--flavio"),
    accent: () => cssVar("--accent"),
    muted: () => cssVar("--chart-muted"),
    grid: () => cssVar("--border"),
    text: () => cssVar("--text-secondary"),
    textStrong: () => cssVar("--text-primary"),
  };

  function el(tag, attrs, children) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    (children || []).forEach((c) => c && e.appendChild(c));
    return e;
  }

  // Locale-aware formatting: en-GB (1,234.5) vs pt-BR (1.234,5). `locale` is
  // passed explicitly by every chart render call (read from the current
  // data-lang at render time) rather than read globally here, so a chart
  // re-rendered after a language switch always reflects the new locale.
  function fmtPct(x, d, locale) {
    return x.toLocaleString(locale || "en-GB", { minimumFractionDigits: d === undefined ? 1 : d, maximumFractionDigits: d === undefined ? 1 : d }) + "%";
  }
  function fmtInt(x, locale) {
    return Math.round(x).toLocaleString(locale || "en-GB");
  }
  function linreg(xs, ys) {
    const n = xs.length;
    let sx = 0, sy = 0, sxy = 0, sxx = 0;
    for (let i = 0; i < n; i++) {
      sx += xs[i];
      sy += ys[i];
      sxy += xs[i] * ys[i];
      sxx += xs[i] * xs[i];
    }
    const slope = (n * sxy - sx * sy) / (n * sxx - sx * sx);
    const intercept = (sy - slope * sx) / n;
    return { slope, intercept };
  }
  function pearsonR(xs, ys) {
    const n = xs.length;
    const mx = xs.reduce((a, b) => a + b, 0) / n;
    const my = ys.reduce((a, b) => a + b, 0) / n;
    let num = 0, dx2 = 0, dy2 = 0;
    for (let i = 0; i < n; i++) {
      const dx = xs[i] - mx, dy = ys[i] - my;
      num += dx * dy;
      dx2 += dx * dx;
      dy2 += dy * dy;
    }
    return num / Math.sqrt(dx2 * dy2);
  }

  // ---------- scales ----------
  function linearScale(domain, range) {
    const [d0, d1] = domain,
      [r0, r1] = range;
    const m = (r1 - r0) / (d1 - d0 || 1);
    const f = (x) => r0 + (x - d0) * m;
    f.domain = domain;
    f.range = range;
    return f;
  }
  function logScale(domain, range) {
    const ld0 = Math.log10(domain[0]),
      ld1 = Math.log10(domain[1]);
    const [r0, r1] = range;
    const m = (r1 - r0) / (ld1 - ld0 || 1);
    const f = (x) => r0 + (Math.log10(x) - ld0) * m;
    f.domain = domain;
    f.range = range;
    return f;
  }

  function niceLinearTicks(domain, count) {
    const [lo, hi] = domain;
    const span = hi - lo;
    if (span <= 0) return [lo];
    const rawStep = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const norm = rawStep / mag;
    let step;
    if (norm < 1.5) step = 1 * mag;
    else if (norm < 3) step = 2 * mag;
    else if (norm < 7) step = 5 * mag;
    else step = 10 * mag;
    const start = Math.ceil(lo / step) * step;
    const ticks = [];
    for (let v = start; v <= hi + 1e-9; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
    return ticks;
  }
  function logTicks(domain) {
    const lo = Math.floor(Math.log10(domain[0]));
    const hi = Math.ceil(Math.log10(domain[1]));
    const ticks = [];
    for (let p = lo; p <= hi; p++) {
      const v = Math.pow(10, p);
      if (v >= domain[0] * 0.999 && v <= domain[1] * 1.001) ticks.push(v);
    }
    return ticks;
  }

  // ---------- shared tooltip ----------
  let tooltipEl = null;
  function ensureTooltip() {
    if (tooltipEl) return tooltipEl;
    tooltipEl = document.createElement("div");
    tooltipEl.className = "chart-tooltip";
    document.body.appendChild(tooltipEl);
    bindTouchDismiss();
    return tooltipEl;
  }
  function showTooltip(clientX, clientY, title, rows) {
    const t = ensureTooltip();
    t.textContent = "";
    if (title) {
      const h = document.createElement("div");
      h.className = "tt-title";
      h.textContent = title;
      t.appendChild(h);
    }
    rows.forEach((r) => {
      const row = document.createElement("div");
      row.className = "tt-row";
      if (r.color) {
        const key = document.createElement("span");
        key.className = "tt-key";
        key.style.background = r.color;
        row.appendChild(key);
      }
      const l = document.createElement("span");
      l.className = "tt-label";
      l.textContent = r.label;
      const v = document.createElement("span");
      v.className = "tt-value";
      v.textContent = r.value;
      row.appendChild(l);
      row.appendChild(v);
      t.appendChild(row);
    });
    t.style.display = "block";
    const pad = 16;
    let left = clientX + pad,
      top = clientY + pad;
    const rect = t.getBoundingClientRect();
    if (left + rect.width > window.innerWidth - 8) left = clientX - rect.width - pad;
    if (top + rect.height > window.innerHeight - 8) top = clientY - rect.height - pad;
    t.style.left = left + "px";
    t.style.top = top + "px";
  }
  function hideTooltip() {
    if (tooltipEl) tooltipEl.style.display = "none";
  }

  // --- touch support ---------------------------------------------------
  // Charts were hover-only, so on phones/tablets a tap showed nothing (or
  // flashed the tooltip for an instant before `pointerleave` fired at the
  // end of the tap). We now (a) treat a tap like a hover via `pointerdown`,
  // (b) keep the tooltip up after a touch instead of hiding it on leave,
  // and (c) dismiss it when the next tap lands outside any chart.
  let touchDismissBound = false;
  function bindTouchDismiss() {
    if (touchDismissBound) return;
    touchDismissBound = true;
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (ev.pointerType !== "touch") return;
        const t = ev.target;
        if (!t.closest || !t.closest(".chart-svg")) hideTooltip();
      },
      true
    );
  }
  // Wrap a pointerleave handler so a touch does NOT trigger the hide (the
  // tooltip stays until the user taps elsewhere); mouse leave still hides.
  function onLeaveGuarded(fn) {
    return (ev) => {
      if (ev && ev.pointerType === "touch") return;
      fn();
    };
  }
  // Attach the same handler to both hover-move and tap-down.
  function bindEnter(target, handler) {
    target.addEventListener("pointermove", handler);
    target.addEventListener("pointerdown", handler);
  }

  function svgPointerToLocal(svg, ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    return loc;
  }

  // ---------- axes ----------
  function drawXAxis(g, scale, ticks, y0, fmt) {
    const axis = el("g", { class: "axis axis-x" });
    ticks.forEach((t) => {
      const x = scale(t);
      axis.appendChild(el("text", { x: x, y: y0 + 22, "text-anchor": "middle" }, [])).textContent = fmt(t);
    });
    g.appendChild(axis);
  }
  function drawYAxis(g, scale, ticks, fmt) {
    const axis = el("g", { class: "axis axis-y" });
    ticks.forEach((t) => {
      const y = scale(t);
      axis.appendChild(el("text", { x: -10, y: y + 4, "text-anchor": "end" }, [])).textContent = fmt(t);
    });
    g.appendChild(axis);
  }
  function drawGridY(g, scale, ticks, innerW) {
    const grid = el("g", { class: "grid" });
    ticks.forEach((t) => {
      grid.appendChild(el("line", { x1: 0, x2: innerW, y1: scale(t), y2: scale(t) }));
    });
    g.appendChild(grid);
  }

  function axisLabel(g, text, x, y, rotate) {
    const attrs = { x, y, class: "axis-caption", "text-anchor": "middle" };
    if (rotate) attrs.transform = `rotate(-90 ${x} ${y})`;
    const t = el("text", attrs);
    t.textContent = text;
    g.appendChild(t);
  }

  // ===================================================================
  // Scatter (shared engine for funnel, r1-vs-r2, turnout-vs-swing)
  // ===================================================================
  function renderScatter(containerId, points, opts) {
    const container = document.getElementById(containerId);
    const width = opts.width || 720,
      height = opts.height || 440;
    const margin = opts.margin || { top: 16, right: 150, bottom: 50, left: 56 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const xScale = opts.xType === "log" ? logScale(opts.xDomain, [0, innerW]) : linearScale(opts.xDomain, [0, innerW]);
    const yScale = linearScale(opts.yDomain, [innerH, 0]);

    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg" });
    const g = el("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(g);

    const yTicks = niceLinearTicks(opts.yDomain, 6);
    drawGridY(g, yScale, yTicks, innerW);
    drawYAxis(g, yScale, yTicks, opts.yTickFormat || ((v) => v));

    const xTicks = opts.xType === "log" ? logTicks(opts.xDomain) : niceLinearTicks(opts.xDomain, 6);
    drawXAxis(g, xScale, xTicks, innerH, opts.xTickFormat || ((v) => v));

    (opts.hlines || []).forEach((hl) => {
      g.appendChild(el("line", { x1: 0, x2: innerW, y1: yScale(hl.y), y2: yScale(hl.y), class: hl.cls || "refline" }));
    });
    (opts.vlines || []).forEach((vl) => {
      g.appendChild(el("line", { x1: xScale(vl.x), x2: xScale(vl.x), y1: 0, y2: innerH, class: vl.cls || "refline" }));
    });
    if (opts.diagonal) {
      g.appendChild(
        el("line", {
          x1: xScale(opts.xDomain[0]),
          y1: yScale(opts.xDomain[0]),
          x2: xScale(opts.xDomain[1]),
          y2: yScale(opts.xDomain[1]),
          class: "diagonal",
        })
      );
    }
    (opts.lineSegments || []).forEach((ls) => {
      g.appendChild(
        el("line", { x1: xScale(ls.x1), y1: yScale(ls.y1), x2: xScale(ls.x2), y2: yScale(ls.y2), class: ls.cls || "trendline" })
      );
    });

    const ptsG = el("g", { class: "points" });
    g.appendChild(ptsG);
    const screenPts = new Array(points.length);
    points.forEach((p, i) => {
      const sx = xScale(p.x),
        sy = yScale(p.y);
      screenPts[i] = { sx, sy };
      ptsG.appendChild(el("circle", { cx: sx, cy: sy, r: p.r || 2, class: "pt", fill: p.color, "fill-opacity": p.op || 0.4 }));
    });

    axisLabel(g, opts.xLabel, innerW / 2, innerH + 40);
    axisLabel(g, opts.yLabel, -40, innerH / 2, true);

    if (opts.legend) {
      const lg = el("g", { transform: `translate(${innerW + 20}, 8)` });
      opts.legend.forEach((item, i) => {
        const y = i * 22;
        lg.appendChild(el("circle", { cx: 6, cy: y, r: 5, fill: item.color }));
        const t = el("text", { x: 16, y: y + 4, class: "legend-label" });
        t.textContent = item.label;
        lg.appendChild(t);
      });
      g.appendChild(lg);
    }

    const hi = el("circle", { r: 6, class: "pt-highlight", style: "display:none" });
    g.appendChild(hi);

    const cell = opts.cellSize || 14;
    const grid = new Map();
    screenPts.forEach((pt, i) => {
      const key = Math.round(pt.sx / cell) + "," + Math.round(pt.sy / cell);
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(i);
    });
    const hitRadius2 = Math.pow(opts.hitRadius || 18, 2);

    function findNearest(mx, my) {
      const cx = Math.round(mx / cell),
        cy = Math.round(my / cell);
      let best = -1,
        bestD = Infinity;
      for (let dx = -1; dx <= 1; dx++)
        for (let dy = -1; dy <= 1; dy++) {
          const arr = grid.get(cx + dx + "," + (cy + dy));
          if (!arr) continue;
          for (const i of arr) {
            const pt = screenPts[i];
            const d = (pt.sx - mx) * (pt.sx - mx) + (pt.sy - my) * (pt.sy - my);
            if (d < bestD) {
              bestD = d;
              best = i;
            }
          }
        }
      return bestD <= hitRadius2 ? best : -1;
    }

    const onScatterMove = (ev) => {
      const loc = svgPointerToLocal(svg, ev);
      const mx = loc.x - margin.left,
        my = loc.y - margin.top;
      if (mx < 0 || mx > innerW || my < 0 || my > innerH) {
        if (ev.pointerType !== "touch") {
          hi.style.display = "none";
          hideTooltip();
        }
        return;
      }
      const idx = findNearest(mx, my);
      if (idx >= 0) {
        const pt = screenPts[idx];
        hi.setAttribute("cx", pt.sx);
        hi.setAttribute("cy", pt.sy);
        hi.setAttribute("stroke", points[idx].color);
        hi.style.display = "block";
        const info = opts.tooltipFn(points[idx]);
        showTooltip(ev.clientX, ev.clientY, info.title, info.rows);
      } else if (ev.pointerType !== "touch") {
        hi.style.display = "none";
        hideTooltip();
      }
    };
    bindEnter(svg, onScatterMove);
    svg.addEventListener(
      "pointerleave",
      onLeaveGuarded(() => {
        hi.style.display = "none";
        hideTooltip();
      })
    );

    container.textContent = "";
    container.appendChild(svg);

    // Programmatic selection API (used by e.g. a search box): moves the
    // same highlight ring and tooltip a pointer hover would, but driven by
    // index instead of mouse position. Returns the point's on-screen
    // (viewport) coordinates so a caller can scroll it into view first.
    function selectByIndex(idx) {
      if (idx < 0 || idx >= screenPts.length) {
        hi.style.display = "none";
        hideTooltip();
        return null;
      }
      const pt = screenPts[idx];
      hi.setAttribute("cx", pt.sx);
      hi.setAttribute("cy", pt.sy);
      hi.setAttribute("stroke", points[idx].color);
      hi.style.display = "block";
      const svgPt = svg.createSVGPoint();
      svgPt.x = pt.sx;
      svgPt.y = pt.sy;
      const client = svgPt.matrixTransform(g.getScreenCTM());
      const info = opts.tooltipFn(points[idx]);
      showTooltip(client.x, client.y, info.title, info.rows);
      return { x: client.x, y: client.y };
    }
    function clearSelection() {
      hi.style.display = "none";
      hideTooltip();
    }
    return { selectByIndex, clearSelection };
  }

  // ===================================================================
  // Bars (shared engine: histograms, Monte Carlo panels, digit tests,
  // and horizontal candidate-result bars)
  // ===================================================================
  function renderBars(containerId, bars, opts) {
    const container = document.getElementById(containerId);
    const width = opts.width || 720,
      height = opts.height || 380;
    const horizontal = opts.orientation === "horizontal";
    const margin = opts.margin || (horizontal ? { top: 10, right: 54, bottom: 36, left: 150 } : { top: 16, right: 16, bottom: 46, left: 56 });
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const maxVal = opts.valueDomain ? opts.valueDomain[1] : Math.max(...bars.map((b) => b.value)) * 1.12;
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg" });
    const g = el("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(g);

    if (!horizontal) {
      const valScale = linearScale([0, maxVal], [innerH, 0]);
      const ticks = niceLinearTicks([0, maxVal], 5);
      drawGridY(g, valScale, ticks, innerW);
      drawYAxis(g, valScale, ticks, opts.valueTickFormat || ((v) => v));

      const n = bars.length;
      const bw = innerW / n;
      const barsG = el("g");
      g.appendChild(barsG);
      bars.forEach((b, i) => {
        const x0 = i * bw;
        const h = innerH - valScale(b.value);
        const rect = el("rect", {
          x: x0 + bw * (opts.gap || 0.06),
          y: valScale(b.value),
          width: bw * (1 - 2 * (opts.gap || 0.06)),
          height: Math.max(h, 0),
          fill: b.color || cssVar("--chart-muted"),
          class: "bar",
        });
        barsG.appendChild(rect);
        const hit = el("rect", { x: x0, y: 0, width: bw, height: innerH, fill: "transparent", class: "bar-hit" });
        bindEnter(hit, (ev) => {
          rect.classList.add("bar-hover");
          const info = opts.tooltipFn(b);
          showTooltip(ev.clientX, ev.clientY, info.title, info.rows);
        });
        hit.addEventListener("pointerleave", onLeaveGuarded(() => {
          rect.classList.remove("bar-hover");
          hideTooltip();
        }));
        barsG.appendChild(hit);
      });

      if (opts.xTickLabels !== false) {
        const everyNth = Math.max(1, Math.ceil(n / (opts.maxXLabels || 12)));
        const axis = el("g", { class: "axis axis-x" });
        bars.forEach((b, i) => {
          if (i % everyNth !== 0) return;
          const t = el("text", { x: i * bw + bw / 2, y: innerH + 20, "text-anchor": "middle" });
          t.textContent = b.label;
          axis.appendChild(t);
        });
        g.appendChild(axis);
      }

      (opts.markers || []).forEach((m) => {
        const idx = bars.findIndex((b) => b.key === m.key);
        if (idx < 0) return;
        const x = idx * bw + bw / 2;
        g.appendChild(el("line", { x1: x, x2: x, y1: 0, y2: innerH, class: "mark-line", stroke: m.color }));
        const t = el("text", { x: x + (m.align === "left" ? -6 : 6), y: 14, class: "mark-label", fill: m.color, "text-anchor": m.align === "left" ? "end" : "start" });
        t.textContent = m.label;
        g.appendChild(t);
      });
      // Continuous-position markers (e.g. a simulated mean at a fractional
      // count). `value` is in the same units as the bar keys; we map it onto
      // the category axis using the first bar's key as the origin and bw as
      // the per-unit step (bars are consecutive integer keys at centers).
      (opts.refMarkers || []).forEach((m) => {
        if (!bars.length) return;
        const x = (m.value - bars[0].key + 0.5) * bw;
        if (x < 0 || x > innerW) return;
        g.appendChild(el("line", { x1: x, x2: x, y1: 0, y2: innerH, class: m.dashed ? "mark-line refline-dash" : "mark-line", stroke: m.color, "stroke-dasharray": m.dashed ? "4 3" : null }));
        if (m.label) {
          const t = el("text", { x: x + (m.align === "left" ? -6 : 6), y: m.labelY || 30, class: "mark-label", fill: m.color, "text-anchor": m.align === "left" ? "end" : "start" });
          t.textContent = m.label;
          g.appendChild(t);
        }
      });
      // Shaded band across a continuous category range (e.g. the 90% range
      // of a simulated null distribution), drawn behind the bars.
      (opts.refBands || []).forEach((bnd) => {
        if (!bars.length) return;
        const x1 = (bnd.lo - bars[0].key) * bw + bw * (opts.gap || 0.06);
        const x2 = (bnd.hi - bars[0].key + 1) * bw - bw * (opts.gap || 0.06);
        const xa = Math.max(0, Math.min(x1, x2));
        const xb = Math.min(innerW, Math.max(x1, x2));
        if (xb <= xa) return;
        g.insertBefore(
          el("rect", { x: xa, y: 0, width: xb - xa, height: innerH, fill: bnd.color, "fill-opacity": bnd.opacity !== undefined ? bnd.opacity : 0.12 }),
          g.firstChild
        );
      });
      if (opts.refLine !== undefined) {
        g.appendChild(el("line", { x1: 0, x2: innerW, y1: valScale(opts.refLine), y2: valScale(opts.refLine), class: "refline-dash" }));
      }

      axisLabel(g, opts.valueLabel, -40, innerH / 2, true);
      if (opts.categoryLabel) axisLabel(g, opts.categoryLabel, innerW / 2, innerH + 40);
    } else {
      const valScale = linearScale([0, maxVal], [0, innerW]);
      const n = bars.length;
      const bh = innerH / n;
      bars.forEach((b, i) => {
        const y0 = i * bh;
        const w = valScale(b.value);
        const rect = el("rect", {
          x: 0,
          y: y0 + bh * 0.2,
          width: Math.max(w, 0),
          height: bh * 0.6,
          fill: b.color || cssVar("--chart-muted"),
          class: "bar",
        });
        g.appendChild(rect);
        if (b.valueLabel) {
          const t = el("text", { x: w + 8, y: y0 + bh / 2 + 4, class: "bar-value-label" });
          t.textContent = b.valueLabel;
          g.appendChild(t);
        }
        const lbl = el("text", { x: -10, y: y0 + bh / 2 + 4, "text-anchor": "end", class: "axis cat-label" });
        lbl.textContent = b.label;
        g.appendChild(lbl);

        const hit = el("rect", { x: 0, y: y0, width: innerW, height: bh, fill: "transparent" });
        bindEnter(hit, (ev) => {
          rect.classList.add("bar-hover");
          const info = opts.tooltipFn(b);
          showTooltip(ev.clientX, ev.clientY, info.title, info.rows);
        });
        hit.addEventListener("pointerleave", onLeaveGuarded(() => {
          rect.classList.remove("bar-hover");
          hideTooltip();
        }));
        g.appendChild(hit);
      });
      const ticks = niceLinearTicks([0, maxVal], 5);
      const axis = el("g", { class: "axis axis-x" });
      ticks.forEach((t) => {
        const x = valScale(t);
        const lab = el("text", { x, y: innerH + 20, "text-anchor": "middle" });
        lab.textContent = (opts.valueTickFormat || ((v) => v))(t);
        axis.appendChild(lab);
        axis.appendChild(el("line", { x1: x, x2: x, y1: 0, y2: innerH, class: "gridline-v" }));
      });
      g.appendChild(axis);
    }

    container.textContent = "";
    container.appendChild(svg);
  }

  // ===================================================================
  // Dot-line (state-level round1 -> round2)
  // ===================================================================
  function renderDotLine(containerId, rows, opts) {
    const container = document.getElementById(containerId);
    const width = opts.width || 680,
      height = opts.height || 820;
    const margin = { top: 10, right: 100, bottom: 40, left: 46 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const xScale = linearScale(opts.xDomain, [0, innerW]);
    const n = rows.length;
    const rh = innerH / n;

    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg" });
    const g = el("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(g);

    const ticks = niceLinearTicks(opts.xDomain, 6);
    ticks.forEach((t) => {
      g.appendChild(el("line", { x1: xScale(t), x2: xScale(t), y1: 0, y2: innerH, class: "gridline-v" }));
      const lab = el("text", { x: xScale(t), y: innerH + 20, "text-anchor": "middle" });
      lab.textContent = (opts.xTickFormat || ((v) => v))(t);
      g.appendChild(lab);
    });
    (opts.vlines || []).forEach((vl) => {
      g.appendChild(el("line", { x1: xScale(vl.x), x2: xScale(vl.x), y1: 0, y2: innerH, class: vl.cls || "refline" }));
    });

    rows.forEach((r, i) => {
      const y = i * rh + rh / 2;
      g.appendChild(el("text", { x: -10, y: y + 4, "text-anchor": "end", class: "axis cat-label" })).textContent = r.label;
      const x1 = xScale(r.v1),
        x2 = xScale(r.v2);
      g.appendChild(el("line", { x1, x2, y1: y, y2: y, class: "connector" }));
      g.appendChild(el("circle", { cx: x1, cy: y, r: 4.5, fill: r.color1 }));
      g.appendChild(el("circle", { cx: x2, cy: y, r: 4.5, fill: r.color2 }));

      const hit = el("rect", { x: 0, y: i * rh, width: innerW, height: rh, fill: "transparent" });
      bindEnter(hit, (ev) => {
        const info = opts.tooltipFn(r);
        showTooltip(ev.clientX, ev.clientY, info.title, info.rows);
      });
      hit.addEventListener("pointerleave", onLeaveGuarded(hideTooltip));
      g.appendChild(hit);
    });

    if (opts.legend) {
      const lg = el("g", { transform: `translate(${innerW - 150}, -4)` });
      opts.legend.forEach((item, i) => {
        const x = i * 140;
        lg.appendChild(el("circle", { cx: x, cy: 0, r: 5, fill: item.color }));
        const t = el("text", { x: x + 10, y: 4, class: "legend-label" });
        t.textContent = item.label;
        lg.appendChild(t);
      });
      g.appendChild(lg);
    }

    container.textContent = "";
    container.appendChild(svg);
  }

  // ===================================================================
  // Stacked horizontal bars (vote-transfer chart): one bar per category,
  // split into segments whose widths sum to <= 1. A gap at the end of a
  // bar (segments summing to < 1) is deliberately left visible -- it
  // represents "not accounted for by this estimate" rather than being
  // stretched to fill the space, so the chart doesn't visually overstate
  // how much of each candidate's vote this model actually explains.
  // ===================================================================
  function renderStackedBars(containerId, rows, opts) {
    const container = document.getElementById(containerId);
    const width = opts.width || 720,
      height = opts.height || 320;
    const margin = opts.margin || { top: 10, right: 20, bottom: 36, left: 170 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const xScale = linearScale([0, 1], [0, innerW]);
    const n = rows.length;
    const bh = innerH / n;

    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg" });
    const g = el("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(g);

    const ticks = [0, 0.25, 0.5, 0.75, 1];
    ticks.forEach((t) => {
      const x = xScale(t);
      g.appendChild(el("line", { x1: x, x2: x, y1: 0, y2: innerH, class: "gridline-v" }));
      const lab = el("text", { x, y: innerH + 20, "text-anchor": "middle" });
      lab.textContent = (opts.xTickFormat || ((v) => Math.round(v * 100) + "%"))(t);
      g.appendChild(lab);
    });

    rows.forEach((r, i) => {
      const y0 = i * bh + bh * 0.18;
      const barH = bh * 0.64;
      g.appendChild(el("text", { x: -10, y: i * bh + bh / 2 + 4, "text-anchor": "end", class: "axis cat-label" })).textContent = r.label;

      let x = 0;
      r.segments.forEach((seg) => {
        const w = xScale(seg.value) - xScale(0);
        if (w > 0.15) {
          const rect = el("rect", { x, y: y0, width: w, height: barH, fill: seg.color, class: "bar", "fill-opacity": seg.opacity !== undefined ? seg.opacity : 1 });
          g.appendChild(rect);
          const hit = el("rect", { x, y: i * bh, width: Math.max(w, 2), height: bh, fill: "transparent" });
          bindEnter(hit, (ev) => {
            rect.classList.add("bar-hover");
            const info = opts.tooltipFn(r, seg);
            showTooltip(ev.clientX, ev.clientY, info.title, info.rows);
          });
          hit.addEventListener("pointerleave", onLeaveGuarded(() => {
            rect.classList.remove("bar-hover");
            hideTooltip();
          }));
          g.appendChild(hit);
        }
        x += w;
      });
      // Outline the full [0,1] track so the "unaccounted for" gap at the
      // end of a short bar is legible as empty space, not a rendering gap.
      g.appendChild(el("rect", { x: 0, y: y0, width: innerW, height: barH, class: "track-outline", fill: "none" }));

      // 90% confidence-interval whisker on the estimated share to Lula (the
      // boundary between the two segments). Drawn on top so the reader sees
      // the uncertainty directly on the chart, not only in the tooltip. A
      // wide whisker = an estimate not to be trusted precisely.
      if (r.ci) {
        const yc = y0 + barH / 2;
        const xlo = xScale(r.ci.lo),
          xhi = xScale(r.ci.hi),
          xp = xScale(r.ci.point);
        const cap = Math.min(barH / 2, 6);
        const wc = r.ci.color || cssVar("--text-primary");
        g.appendChild(el("line", { x1: xlo, x2: xhi, y1: yc, y2: yc, class: "ci-whisker", stroke: wc }));
        g.appendChild(el("line", { x1: xlo, x2: xlo, y1: yc - cap, y2: yc + cap, class: "ci-whisker", stroke: wc }));
        g.appendChild(el("line", { x1: xhi, x2: xhi, y1: yc - cap, y2: yc + cap, class: "ci-whisker", stroke: wc }));
        g.appendChild(el("circle", { cx: xp, cy: yc, r: 3, class: "ci-point", fill: wc, stroke: cssVar("--surface-card"), "stroke-width": 1 }));
      }
    });

    if (opts.legend) {
      const lg = el("g", { transform: `translate(0, ${innerH + 44})` });
      opts.legend.forEach((item, i) => {
        const x = i * 160;
        lg.appendChild(el("rect", { x, y: -9, width: 12, height: 12, rx: 2, fill: item.color, "fill-opacity": item.opacity !== undefined ? item.opacity : 1 }));
        const t = el("text", { x: x + 18, y: 1, class: "legend-label" });
        t.textContent = item.label;
        lg.appendChild(t);
      });
      g.appendChild(lg);
    }

    container.textContent = "";
    container.appendChild(svg);
  }

  window.ReportCharts = {
    el,
    fmtPct,
    fmtInt,
    linreg,
    pearsonR,
    COLOR,
    renderScatter,
    renderBars,
    renderDotLine,
    renderStackedBars,
  };
})();
