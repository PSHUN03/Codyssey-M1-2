// 통합 통계: 모든 출처(중복 제외)를 출처별 누적 막대로 — 시기 확인된 자료는 연대/세기별, 발표 시기 미상은 맨 끝 별도 막대
import { api } from "./api.js";
import { $, $$, compact, esc, fmt, hideTooltip, showTooltip } from "./ui.js";

const state = { data: null, group: "decade", hidden: new Set() };
const color = (key) => `var(--src-${key})`;

function visibleSources() {
  return state.data.sources.filter((s) => !state.hidden.has(s.key));
}

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}

function tiles(d) {
  const withDate = d.total ? Math.round((d.dated / d.total) * 100) : 0;
  $("#ov-tiles").innerHTML = `
    <div class="ov-tile"><div class="label">전체 자료</div><div class="value">${fmt(d.total)}</div><div class="sub">중복 ${fmt(d.duplicates_removed)}건 제외</div></div>
    <div class="ov-tile"><div class="label">본문이 있는 작품</div><div class="value">${fmt(d.with_text)}</div><div class="sub">나머지는 서지·목록 정보 + 원문 링크</div></div>
    <div class="ov-tile"><div class="label">시기 확인</div><div class="value">${fmt(d.dated)}</div><div class="sub">전체의 ${withDate}% · 출처별 기준은 표 참고</div></div>
    <div class="ov-tile"><div class="label">발표 시기 미상</div><div class="value">${fmt(d.undated)}</div><div class="sub">그래프 맨 오른쪽 막대로 따로 표시</div></div>`;
}

function legend(d) {
  const big = d.sources.find((s) => s.key === "kcisa" && s.total > d.total / 2);
  const hint = $("#ov-hint");
  if (hint) hint.textContent = big && !state.hidden.has("kcisa")
    ? "KCISA 자료는 대부분 기관 등록 연도(2010년대) 기준이라 막대가 커요. 범례에서 KCISA를 끄면 다른 출처의 흐름이 잘 보여요."
    : "범례를 눌러 출처를 켜고 끌 수 있어요. 세로 눈금은 시기가 확인된 막대 기준이고, 더 큰 '시기 미상' 막대는 물결 표시로 잘라 실제 건수를 적었어요.";
  $("#ov-legend").innerHTML = d.sources.map((s) => `
    <button type="button" class="ov-chip" data-key="${esc(s.key)}" aria-pressed="${!state.hidden.has(s.key)}"
      title="${esc(s.label)} · 연도 기준: ${esc(s.date_basis)}${s.has_text ? " · 본문 있음" : " · 목록 정보"}">
      <span class="sw" style="background:${color(s.key)}"></span>${esc(s.label)} <span class="n">${fmt(s.total)}</span>
    </button>`).join("");
}

function table(d) {
  $("#ov-table").innerHTML = `<table><thead><tr><th>출처</th><th class="num">자료 수</th><th class="num">시기 확인</th><th class="num">시기 미상</th><th class="num">중복 제외</th><th>본문</th><th>연도 기준</th></tr></thead><tbody>
    ${d.sources.map((s) => `<tr><td><span class="sw" style="background:${color(s.key)}"></span>${esc(s.label)}</td><td class="num">${fmt(s.total)}</td><td class="num">${fmt(s.dated)}</td><td class="num">${fmt(s.undated)}</td><td class="num">${fmt(s.duplicates_removed)}</td><td>${s.has_text ? "있음" : "링크"}</td><td>${esc(s.date_basis)}</td></tr>`).join("")}
    </tbody></table>`;
}

function chart(d) {
  const box = $("#ov-chart");
  const srcs = visibleSources();
  const keys = srcs.map((s) => s.key);
  const undated = Object.fromEntries(keys.map((k) => [k, d.undated_by_source[k] || 0]));
  const cols = d.series.map((p) => ({ label: p.period, parts: Object.fromEntries(keys.map((k) => [k, p.by_source[k] || 0])) }))
    .filter((c) => keys.some((k) => c.parts[k]));
  const hasUndated = keys.some((k) => undated[k]);
  if (hasUndated) cols.push({ label: "시기 미상", parts: undated, undated: true });
  if (!cols.length) { box.innerHTML = `<p class="empty-note">표시할 출처를 하나 이상 켜 주세요.</p>`; return; }

  const sum = (c) => keys.reduce((a, k) => a + c.parts[k], 0);
  const W = Math.max(box.clientWidth, 320);
  const H = 320;
  const m = { t: 22, r: 8, b: 34, l: 56 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  // 세로 눈금은 시기가 확인된 막대 기준 — 시기 미상 막대가 더 크면 위를 잘라 물결 표시와 실제 건수를 단다
  const datedCols = cols.filter((c) => !c.undated);
  const max = niceMax(Math.max(...(datedCols.length ? datedCols : cols).map(sum)));
  const clipped = (c) => c.undated && sum(c) > max;
  const gap = hasUndated ? 14 : 0; // 시기 미상 막대 앞 간격
  const band = (iw - gap) / cols.length;
  const bw = Math.max(3, Math.min(28, band - 3));
  const xOf = (i) => m.l + i * band + (cols[i].undated ? gap : 0);
  const y = (v) => m.t + ih - (v / max) * ih;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const labelEvery = Math.ceil(cols.length / Math.max(1, Math.floor(iw / 52)));

  const bars = cols.map((c, i) => {
    let acc = 0;
    const x = xOf(i) + (band - bw) / 2;
    const scale = clipped(c) ? max / sum(c) : 1; // 잘린 막대는 출처 비율만 유지
    const rects = keys.map((k) => {
      const v = c.parts[k] * scale;
      if (!v) return "";
      const y0 = y(acc + v);
      const h = Math.max(1, y(acc) - y0);
      acc += v;
      return `<rect x="${x}" y="${y0}" width="${bw}" height="${h}" fill="${color(k)}"></rect>`;
    }).join("");
    const cut = clipped(c)
      ? `<path class="bar-break" d="M${x - 2},${m.t + 14} l${bw / 4 + 1},-5 l${bw / 4 + 1},5 l${bw / 4 + 1},-5 l${bw / 4 + 1},5"></path>
         <path class="bar-break" d="M${x - 2},${m.t + 20} l${bw / 4 + 1},-5 l${bw / 4 + 1},5 l${bw / 4 + 1},-5 l${bw / 4 + 1},5"></path>`
      : "";
    return `<g class="stack" data-i="${i}">${rects}${cut}</g><rect class="hit" data-i="${i}" x="${xOf(i)}" y="${m.t}" width="${band}" height="${ih}"></rect>`;
  }).join("");

  // 시기 미상 막대 바로 앞 라벨은 겹치므로 생략
  const crowded = (i) => hasUndated && i === cols.length - 2 && band < 64;
  const xLabels = cols.map((c, i) => (((i % labelEvery === 0 && !crowded(i)) || c.undated)
    ? `<text x="${xOf(i) + band / 2}" y="${H - 12}" text-anchor="middle"${c.undated ? ' class="undated-label"' : ""}>${esc(c.label)}</text>` : "")).join("");
  const sep = hasUndated ? `<line class="undated-sep" x1="${xOf(cols.length - 1) - gap / 2}" x2="${xOf(cols.length - 1) - gap / 2}" y1="${m.t}" y2="${m.t + ih}"></line>` : "";
  const peak = (datedCols.length ? datedCols : cols).reduce((a, c) => (sum(c) > sum(a) ? c : a));
  const pi = cols.indexOf(peak);
  const und = cols.find((c) => c.undated);
  const undLabel = und
    ? `<text class="val-label" x="${xOf(cols.length - 1) + band / 2}" y="${Math.max(m.t - 6, y(Math.min(sum(und), max)) - 6)}" text-anchor="middle">${compact(sum(und))}</text>`
    : "";

  box.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" aria-label="출처별 누적 막대그래프">
      <g class="grid">${ticks.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"></line>`).join("")}</g>
      <g class="axis">${ticks.map((t) => `<text x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end">${compact(t)}</text>`).join("")}${xLabels}</g>
      ${sep}${bars}
      <line class="baseline" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"></line>
      ${peak.undated ? "" : `<text class="val-label" x="${xOf(pi) + band / 2}" y="${y(sum(peak)) - 6}" text-anchor="middle">${compact(sum(peak))}</text>`}
      ${undLabel}
    </svg>`;
  box.setAttribute("aria-label", `출처별 자료 수, 가장 많은 구간 ${peak.label} ${fmt(sum(peak))}건`);

  $$(".hit", box).forEach((hit) => {
    const c = cols[Number(hit.dataset.i)];
    hit.addEventListener("mousemove", (e) => {
      const rows = srcs.filter((s) => c.parts[s.key]).map((s) =>
        `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${color(s.key)};margin-right:6px"></span>${esc(s.label)} <b>${fmt(c.parts[s.key])}</b></div>`).join("");
      showTooltip(`<div><b>${esc(c.label)}</b> · ${fmt(sum(c))}건</div>${rows}`, e.clientX, e.clientY);
    });
    hit.addEventListener("mouseleave", hideTooltip);
  });
}

function genres(d) {
  const srcs = visibleSources();
  const rows = d.by_genre.map((g) => ({ key: g.key, parts: srcs.map((s) => [s, g.by_source[s.key] || 0]) }))
    .map((g) => ({ ...g, total: g.parts.reduce((a, [, v]) => a + v, 0) }))
    .filter((g) => g.total).sort((a, b) => b.total - a.total);
  if (!rows.length) { $("#ov-genres").innerHTML = `<p class="empty-note">데이터가 없어요.</p>`; return; }
  const max = rows[0].total;
  $("#ov-genres").innerHTML = rows.map((g) => `
    <div class="stack-bar" title="${esc(g.key)} · ${g.parts.filter(([, v]) => v).map(([s, v]) => `${s.label} ${fmt(v)}`).join(" · ")}">
      <span class="name">${esc(g.key)}</span>
      <span class="track"><span style="display:flex;width:${(g.total / max) * 100}%">${g.parts.filter(([, v]) => v).map(([s, v]) =>
        `<span class="seg-fill" style="width:${(v / g.total) * 100}%;background:${color(s.key)}"></span>`).join("")}</span></span>
      <span class="n">${fmt(g.total)}</span>
    </div>`).join("");
}

function render() {
  if (!state.data) return;
  legend(state.data);
  chart(state.data);
  genres(state.data);
}

export async function loadOverview(genre) {
  try {
    state.data = await api.catalogStats({ group: state.group, genre: genre || undefined });
    tiles(state.data);
    table(state.data);
    render();
  } catch (e) {
    $("#ov-tiles").innerHTML = `<p class="form-error">통합 통계를 불러오지 못했어요: ${esc(e.message)}</p>`;
  }
}

export function initOverview(getGenre) {
  $("#ov-legend").addEventListener("click", (e) => {
    const b = e.target.closest(".ov-chip");
    if (!b) return;
    const k = b.dataset.key;
    state.hidden.has(k) ? state.hidden.delete(k) : state.hidden.add(k);
    render();
  });
  $("#ov-group").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-group]");
    if (!b || b.dataset.group === state.group) return;
    state.group = b.dataset.group;
    $$("#ov-group button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    loadOverview(getGenre());
  });
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => state.data && chart(state.data), 150); });
}
