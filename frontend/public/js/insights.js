// 통계 화면: 요약 타일 + 기간별 막대그래프(SVG 직접 렌더링) + 장르/작가 분포
import { api } from "./api.js";
import { initOverview, loadOverview } from "./overview.js";
import { $, $$, compact, esc, fmt, hideTooltip, showTooltip } from "./ui.js";

const METRIC_LABEL = { count: "작품 수", average: "평균 글자 수", total: "총 글자 수" };
const GROUP_LABEL = { decade: "연대별", year: "연도별", month: "월별" };
const state = { metric: "count", series: [], group: "decade" };

function params() {
  return { mine: $("#i-mine").value, genre: $("#i-genre").value };
}

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}

function renderChart() {
  const { series, metric, group } = state;
  $("#chart-title").textContent = `${GROUP_LABEL[group]} ${METRIC_LABEL[metric]}`;
  const box = $("#chart");
  if (!series.length) {
    box.innerHTML = `<p class="empty-note">표시할 데이터가 없어요.</p>`;
    $("#chart-table").innerHTML = "";
    return;
  }
  const W = Math.max(box.clientWidth, 320);
  const H = 300;
  const m = { t: 20, r: 8, b: 32, l: 52 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const max = niceMax(Math.max(...series.map((d) => d[metric])));
  const band = iw / series.length;
  const bw = Math.max(2, Math.min(24, band - 2)); // 막대 두께 상한 24px, 이웃과 2px 간격
  const y = (v) => m.t + ih - (v / max) * ih;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const labelEvery = Math.ceil(series.length / Math.floor(iw / 44));
  const peak = series.reduce((a, b) => (b[metric] > a[metric] ? b : a));

  const bars = series.map((d, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    const h = Math.max(0, (d[metric] / max) * ih);
    const r = Math.min(4, bw / 2, h);
    const top = m.t + ih - h;
    // 윗부분만 둥근 막대 (기준선 쪽은 직각)
    const path = h <= 0 ? "" : `M${x},${m.t + ih} V${top + r} Q${x},${top} ${x + r},${top} H${x + bw - r} Q${x + bw},${top} ${x + bw},${top + r} V${m.t + ih} Z`;
    return `<path class="bar" data-i="${i}" d="${path}"></path>
      <rect class="hit" data-i="${i}" x="${m.l + i * band}" y="${m.t}" width="${band}" height="${ih}"></rect>`;
  }).join("");

  const xLabels = series.map((d, i) => (i % labelEvery === 0
    ? `<text x="${m.l + i * band + band / 2}" y="${H - 10}" text-anchor="middle">${esc(d.period)}</text>` : "")).join("");
  const pi = series.indexOf(peak);
  const peakLabel = `<text class="val-label" x="${m.l + pi * band + band / 2}" y="${y(peak[metric]) - 6}" text-anchor="middle">${compact(peak[metric])}</text>`;

  box.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" aria-label="${esc(GROUP_LABEL[group])} ${esc(METRIC_LABEL[metric])} 막대그래프">
      <g class="grid">${ticks.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"></line>`).join("")}</g>
      <g class="axis">${ticks.map((t) => `<text x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end">${compact(t)}</text>`).join("")}${xLabels}</g>
      ${bars}
      <line class="baseline" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"></line>
      ${peakLabel}
    </svg>`;
  box.setAttribute("aria-label", `${GROUP_LABEL[group]} ${METRIC_LABEL[metric]}, 최고 ${peak.period} ${fmt(peak[metric])}`);

  $$(".hit", box).forEach((hit) => {
    const i = Number(hit.dataset.i);
    const d = series[i];
    const bar = box.querySelector(`.bar[data-i="${i}"]`);
    hit.addEventListener("mousemove", (e) => {
      bar && bar.classList.add("hover");
      showTooltip(`<div>${esc(d.period)}</div><div>작품 수 <b>${fmt(d.count)}</b></div><div>평균 <b>${fmt(d.average)}</b>자</div><div>총 <b>${fmt(d.total)}</b>자</div>`, e.clientX, e.clientY);
    });
    hit.addEventListener("mouseleave", () => { bar && bar.classList.remove("hover"); hideTooltip(); });
  });

  $("#chart-table").innerHTML = `<table><thead><tr><th>기간</th><th class="num">작품 수</th><th class="num">평균 글자 수</th><th class="num">총 글자 수</th></tr></thead><tbody>
    ${series.map((d) => `<tr><td>${esc(d.period)}</td><td class="num">${fmt(d.count)}</td><td class="num">${fmt(d.average)}</td><td class="num">${fmt(d.total)}</td></tr>`).join("")}
  </tbody></table>`;
}

function hbars(el, items, unit) {
  if (!items.length) { el.innerHTML = `<p class="empty-note">데이터가 없어요.</p>`; return; }
  const max = Math.max(...items.map((i) => i.count));
  el.innerHTML = items.map((i) => `
    <div class="hbar" title="${esc(i.key)} · ${fmt(i.count)}${unit} · 평균 ${fmt(i.average)}자">
      <span class="name">${esc(i.key)}</span>
      <span class="track"><span class="fill" style="display:block;width:${(i.count / max) * 100}%"></span></span>
      <span class="n">${fmt(i.count)}${unit}</span>
    </div>`).join("");
}

function tiles(s, stats) {
  const m = s.metrics || {};
  const dirIcon = { "상승": "▲", "하락": "▼", "유지": "■" }[s.trend_direction] || "";
  $("#stat-tiles").innerHTML = `
    <div class="tile hero"><div class="label">기간</div><div class="value">${esc(s.period)}</div><div class="sub">${fmt(s.count)}개 레코드 · 기록한 날 ${fmt(stats.active_days)}일 · 최장 연속 ${fmt(stats.longest_streak_days)}일</div></div>
    <div class="tile hero dark"><div class="label">최근 추세 (AI에 주입)</div><div class="value">${dirIcon} ${esc(s.trend_direction)}</div><div class="sub" title="${esc(s.trend)}">${esc(s.trend)}</div></div>
    <div class="tile"><div class="label">평균 글자 수</div><div class="value">${fmt(m.average)}</div><div class="sub">중앙값 ${fmt(m.median)} · 표준편차 ${fmt(m.std)}</div></div>
    <div class="tile"><div class="label">총 글자 수</div><div class="value">${compact(m.total || 0)}</div><div class="sub">원고지 약 ${compact((m.total || 0) / 200)}매</div></div>
    <div class="tile"><div class="label">최대</div><div class="value">${fmt(m.max)}</div><div class="sub">${esc(s.longest ? `《${s.longest.title || "제목 없음"}》` : "")}</div></div>
    <div class="tile"><div class="label">최소</div><div class="value">${fmt(m.min)}</div><div class="sub">${esc(s.shortest ? `《${s.shortest.title || "제목 없음"}》` : "")}</div></div>`;
}

export async function loadInsights() {
  state.group = $("#i-group").value;
  loadOverview($("#i-genre").value);
  try {
    const p = params();
    const [s, stats] = await Promise.all([api.summary(p), api.statistics({ ...p, group: state.group })]);
    state.series = stats.series;
    tiles(s, stats);
    renderChart();
    hbars($("#genre-bars"), s.by_genre, "편");
    api.listLibrary({ limit: 1 }).then((lib) => {
      const note = $("#library-note");
      if (note) note.textContent = `※ 발표 시기를 확인할 수 없는 위키문헌 서재 ${fmt(lib.total)}편과 참고 자료(공유마당·KCISA 등)는 글자 수가 없거나 날짜가 없어 아래 그래프에서는 빠지고, 위 '모든 자료 한눈에'에 함께 집계돼요.`;
    }).catch(() => {});
    hbars($("#author-bars"), stats.top_authors, "편");
  } catch (e) {
    $("#stat-tiles").innerHTML = `<p class="form-error">통계를 불러오지 못했어요: ${esc(e.message)}</p>`;
  }
}

export function initInsights() {
  initOverview(() => $("#i-genre").value);
  ["#i-mine", "#i-genre", "#i-group"].forEach((s) => $(s).addEventListener("change", loadInsights));
  $(".chart-card .seg").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-metric]");
    if (!b) return;
    state.metric = b.dataset.metric;
    $$(".chart-card .seg button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    renderChart();
  });
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderChart, 150); });
}
