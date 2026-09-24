// 공용 UI 유틸: 이스케이프, 숫자 포맷, 토스트, 툴팁, 간단한 마크다운 렌더러

export const GENRES = ["시", "시조", "수필", "단편소설", "중편소설", "장편소설", "동화", "희곡", "기타"];
export const STAGES = ["주제 선정", "구상·개요", "초고", "퇴고", "완성"];

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export const fmt = (n) => (n === null || n === undefined ? "-" : Math.round(Number(n)).toLocaleString("ko-KR"));

export function compact(n) {
  n = Number(n);
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(1).replace(/\.0$/, "")}억`;
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(1).replace(/\.0$/, "")}만`;
  return fmt(n);
}

export function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  return new Date(iso).toLocaleDateString("ko-KR");
}

export function today() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function fillGenreSelects() {
  document.querySelectorAll("select.genre-select").forEach((sel) => {
    const empty = sel.dataset.empty;
    sel.innerHTML = (empty ? `<option value="">${esc(empty)}</option>` : "") +
      GENRES.map((g) => `<option value="${g}">${g}</option>`).join("");
  });
}

let toastTimer;
export function toast(message, { error = false } = {}) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), error ? 4500 : 2500);
}

export function showTooltip(html, x, y) {
  const el = $("#tooltip");
  el.innerHTML = html;
  el.hidden = false;
  const { width, height } = el.getBoundingClientRect();
  const left = Math.min(x + 12, window.innerWidth - width - 8);
  const top = y - height - 12 < 8 ? y + 16 : y - height - 12;
  el.style.left = `${Math.max(8, left)}px`;
  el.style.top = `${top}px`;
}
export const hideTooltip = () => ($("#tooltip").hidden = true);

// ---- 아주 작은 마크다운 렌더러 (먼저 HTML 을 이스케이프하므로 XSS 안전)
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}

export function markdown(src) {
  const lines = esc(src).split(/\r?\n/);
  const out = [];
  let list = null; // "ul" | "ol"
  let para = [];
  const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join("<br>"))}</p>`); para = []; } };
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };

  for (const line of lines) {
    const t = line.trim();
    let m;
    if (!t) { flushPara(); closeList(); continue; }
    if ((m = t.match(/^#{1,6}\s+(.*)$/))) { flushPara(); closeList(); out.push(`<h4>${inline(m[1])}</h4>`); continue; }
    if ((m = t.match(/^&gt;\s?(.*)$/))) { flushPara(); closeList(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
    if ((m = t.match(/^[-*•]\s+(.*)$/))) {
      flushPara();
      if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(m[1])}</li>`); continue;
    }
    if ((m = t.match(/^(\d+)[.)]\s+(.*)$/))) {
      flushPara();
      // 번호 항목 사이에 글머리표가 끼어 목록이 끊겨도 원래 번호를 이어 가도록 start 지정
      if (list !== "ol") { closeList(); out.push(`<ol start="${Number(m[1])}">`); list = "ol"; }
      out.push(`<li>${inline(m[2])}</li>`); continue;
    }
    if (t === "---") { flushPara(); closeList(); continue; }
    closeList();
    para.push(t);
  }
  flushPara(); closeList();
  return out.join("");
}
