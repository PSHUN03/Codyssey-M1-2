// 진입점: 탭 전환, 다크 모드, 서버 상태(콜드스타트 안내), 각 화면 초기화
import { api } from "./api.js";
import { initChat, loadConversations, loadSummaryPanel } from "./chat.js";
import { initData, loadList } from "./data.js";
import { initInsights, loadInsights } from "./insights.js";
import { $, $$, fillGenreSelects } from "./ui.js";

const loaded = { data: false, insights: false };
let insightsStale = false;

function showView(view) {
  $$(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.view === view)));
  $$(".view").forEach((v) => (v.dataset.active = String(v.id === `view-${view}`)));
  if (view === "data" && !loaded.data) { loaded.data = true; loadList(); }
  if (view === "insights" && (!loaded.insights || insightsStale)) { loaded.insights = true; insightsStale = false; loadInsights(); }
  try { history.replaceState(null, "", `#${view}`); } catch (_) {}
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
      setStatus("ok", h.ai_ready ? "연결됨" : "연결됨 (AI 키 없음)");
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
  initData(() => { loadSummaryPanel(); insightsStale = true; });
  initInsights();
  $$(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));

  const initial = location.hash.slice(1);
  showView(["chat", "data", "insights"].includes(initial) ? initial : "chat");

  await wakeServer();
  loadConversations();
  loadSummaryPanel();
  if (loaded.data) loadList();
  if (loaded.insights) loadInsights();
}

main();
