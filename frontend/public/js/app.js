// 진입점: 해시 라우팅(#/, #/history, #/records, #/insights), 다크 모드, 서버 깨우기(콜드스타트 안내)
import { API_BASE, api } from "./api.js";
import { initChat, loadConversations, loadSummaryStrip, newChat } from "./chat.js";
import { initData, loadList } from "./data.js";
import { initInsights, loadInsights } from "./insights.js";
import { $, $$, fillGenreSelects } from "./ui.js";

const PAGES = ["home", "history", "records", "insights"];
const loaded = { records: false, insights: false };
let insightsStale = false;
let serverReady = false;

function currentPage() {
  const name = location.hash.replace(/^#\/?/, "");
  return PAGES.includes(name) ? name : "home";
}

function route() {
  const page = currentPage();
  $$(".page").forEach((p) => (p.dataset.active = String(p.id === `page-${page}`)));
  $$(".nav-link").forEach((a) => (a.dataset.route === page ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  window.scrollTo({ top: 0 });
  if (!serverReady) return;
  if (page === "history") loadConversations();
  if (page === "records" && !loaded.records) { loaded.records = true; loadList(); }
  if (page === "insights" && (!loaded.insights || insightsStale)) { loaded.insights = true; insightsStale = false; loadInsights(); }
}

function initTheme() {
  $("#theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (_) {}
  });
}

function setStatus(state, label) {
  const pill = $("#server-status");
  pill.dataset.state = state;
  pill.querySelector(".label").textContent = label;
}

// Render 무료 티어는 잠들었다가 첫 요청에 깨어난다 → 먼저 /health 로 깨우고, 늦으면 안내 배너를 띄운다.
async function wakeServer() {
  const slow = setTimeout(() => { $("#wake-banner").hidden = false; setStatus("pending", "서버 깨우는 중"); }, 2500);
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const h = await api.health();
      clearTimeout(slow);
      $("#wake-banner").hidden = true;
      const degraded = $("#degraded-banner");
      if (degraded) degraded.hidden = !h.degraded;
      setStatus(h.degraded ? "pending" : "ok", h.degraded ? "읽기 전용" : h.ai_ready ? "연결됨" : "연결됨 (AI 키 없음)");
      return true;
    } catch (_) {
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
  clearTimeout(slow);
  $("#wake-banner").hidden = true;
  setStatus("error", "연결 실패");
  return false;
}

async function main() {
  fillGenreSelects();
  initTheme();
  initChat();
  initData(() => { loadSummaryStrip(); insightsStale = true; });
  initInsights();
  $("#docs-link").href = `${API_BASE}/docs`;
  $("#nav-new-chat").addEventListener("click", () => newChat());
  window.addEventListener("hashchange", route);
  route();

  await wakeServer();
  serverReady = true;
  loadSummaryStrip();
  route();
}

main();
