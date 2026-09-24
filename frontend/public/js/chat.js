// 채팅 화면: 메시지 전송/표시, 로딩 표시, 대화 기록 목록/불러오기/삭제, 데이터 요약 패널
import { api } from "./api.js";
import { $, $$, esc, fmt, markdown, timeAgo, toast } from "./ui.js";

const TOOL_LABELS = {
  get_data_summary: "데이터 요약 조회",
  get_statistics: "기간별 통계 조회",
  search_works: "작품 검색",
  list_my_records: "내 기록 조회",
  list_conversations: "이전 대화 목록",
  get_conversation: "이전 대화 불러오기",
  analyze_text: "원고 분석",
};

const SUGGESTIONS = {
  "자유": [
    "내 글쓰기 기록을 요약해서 알려줘. 요즘 어떤 흐름이야?",
    "데이터에서 가장 긴 글과 가장 짧은 글은 뭐야?",
    "글쓰기 습관을 만들려면 어떻게 목표를 세우면 좋을까?",
  ],
  "주제 선정": [
    "내 기록을 보고 이번 주에 써볼 만한 주제 3개 추천해줘.",
    "요즘 너무 한 장르만 쓴 것 같아. 새로 도전할 장르와 주제를 제안해줘.",
    "'고향'을 소재로 한 시를 쓰고 싶어. 참고할 만한 작품도 찾아줘.",
  ],
  "구상·개요": [
    "'첫 출근 날'을 주제로 한 수필 개요를 짜줘. 분량은 내 평균 정도로.",
    "짧은 단편소설 구상을 돕고 싶어. 인물과 갈등부터 같이 정해보자.",
  ],
  "초고": [
    "첫 문장이 안 써져. 비 오는 날 버스 정류장 장면으로 시작하는 첫 문장 후보를 줘.",
    "오늘 목표 분량을 내 최근 기록 기준으로 정해줘.",
  ],
  "퇴고": [
    "아래 글을 퇴고해줘.\n\n그날 나는 정말 정말 피곤했다. 그리고 버스를 탔다. 그리고 창밖을 보았는데 비가 오고 있었고 사람들은 우산을 쓰고 있었고 나는 우산이 없었다. 나는 조금 슬펐다.",
  ],
};

const state = { convId: null, stage: "자유", sending: false, conversations: [] };

// ------------------------------------------------------------ 렌더링
function toolChips(calls) {
  if (!calls || !calls.length) return "";
  return `<div class="tool-chips">${calls.map((c) => `
    <div class="tool-chip" title="${esc(JSON.stringify(c.arguments || {}))}">
      <span aria-hidden="true">⚙</span><span><code>${esc(c.name)}</code> ${esc(TOOL_LABELS[c.name] || "")}${c.reason ? ` — ${esc(c.reason)}` : ""}</span>
    </div>`).join("")}</div>`;
}

function addMessage({ role, content, stage, tool_calls, created_at }, { error = false } = {}) {
  $("#chat-empty").hidden = true;
  const el = document.createElement("div");
  el.className = `msg ${role}${error ? " error" : ""}`;
  const body = role === "assistant" ? markdown(content) : esc(content);
  const when = created_at ? timeAgo(created_at) : "";
  el.innerHTML = `
    ${role === "assistant" ? toolChips(tool_calls) : ""}
    <div class="bubble">${body}</div>
    <div class="meta">${role === "assistant" ? "글벗" : "나"}${stage && stage !== "자유" ? ` · ${esc(stage)}` : ""}${when ? ` · ${when}` : ""}</div>`;
  $("#messages").appendChild(el);
  el.scrollIntoView({ block: "end", behavior: "smooth" });
  return el;
}

function showLoading() {
  const el = document.createElement("div");
  el.className = "msg assistant loading";
  el.innerHTML = `<div class="bubble"><span class="typing" aria-label="답변 생성 중"><span></span><span></span><span></span></span><span class="loading-text">글벗이 생각하는 중…</span></div>`;
  $("#messages").appendChild(el);
  el.scrollIntoView({ block: "end", behavior: "smooth" });
  const slow = setTimeout(() => {
    const t = el.querySelector(".loading-text");
    if (t) t.textContent = "서버가 잠에서 깨는 중일 수 있어요 (최대 1분)…";
  }, 9000);
  return () => { clearTimeout(slow); el.remove(); };
}

function resetMessages() {
  $$("#messages .msg").forEach((m) => m.remove());
  $("#chat-empty").hidden = false;
}

function renderSuggestions() {
  $("#suggestions").innerHTML = (SUGGESTIONS[state.stage] || []).map((s) =>
    `<button type="button" class="suggestion" data-text="${esc(s)}">${esc(s.split("\n")[0])}</button>`).join("");
}

function setStage(stage) {
  state.stage = stage;
  $$(".stage-chips .chip").forEach((c) => c.setAttribute("aria-checked", String(c.dataset.stage === stage)));
  renderSuggestions();
}

// ------------------------------------------------------------ 대화 기록
function renderConversations() {
  const list = $("#conv-list");
  if (!state.conversations.length) {
    list.innerHTML = `<li class="empty-note">아직 저장된 대화가 없어요. 첫 메시지를 보내면 자동으로 저장돼요.</li>`;
    return;
  }
  list.innerHTML = state.conversations.map((c) => `
    <li class="conv-item" data-id="${esc(c.id)}" aria-current="${c.id === state.convId}" tabindex="0" role="button">
      <span class="t">${esc(c.title)}</span>
      <span class="p">${esc(timeAgo(c.updated_at))} · ${c.message_count}개 메시지</span>
      <button class="del" type="button" data-del="${esc(c.id)}" aria-label="대화 삭제" title="삭제">✕</button>
    </li>`).join("");
}

export async function loadConversations() {
  try {
    state.conversations = await api.listConversations();
    renderConversations();
  } catch (e) {
    $("#conv-list").innerHTML = `<li class="empty-note">대화 목록을 불러오지 못했어요: ${esc(e.message)}</li>`;
  }
}

async function openConversation(id) {
  if (state.sending) return;
  try {
    const conv = await api.getConversation(id);
    state.convId = conv.id;
    resetMessages();
    $("#chat-title").textContent = conv.title;
    conv.messages.forEach((m) => addMessage(m));
    renderConversations();
  } catch (e) {
    toast(e.message, { error: true });
  }
}

function newChat() {
  state.convId = null;
  resetMessages();
  $("#chat-title").textContent = "새 대화";
  renderConversations();
  $("#chat-input").focus();
}

async function removeConversation(id) {
  const conv = state.conversations.find((c) => c.id === id);
  if (!confirm(`'${conv ? conv.title : "이 대화"}'를 삭제할까요?`)) return;
  try {
    await api.deleteConversation(id);
    if (state.convId === id) newChat();
    await loadConversations();
    toast("대화를 삭제했어요.");
  } catch (e) {
    toast(e.message, { error: true });
  }
}

// ------------------------------------------------------------ 전송
async function send(text) {
  text = text.trim();
  if (!text || state.sending) return;
  state.sending = true;
  $("#send-btn").disabled = true;
  const input = $("#chat-input");
  input.value = "";
  autosize();

  addMessage({ role: "user", content: text, stage: state.stage });
  const stopLoading = showLoading();
  try {
    const res = await api.chat({
      message: text,
      conversation_id: state.convId,
      stage: state.stage,
      genre: $("#chat-genre").value || null,
    });
    stopLoading();
    const isNew = !state.convId;
    state.convId = res.conversation_id;
    addMessage({ role: "assistant", content: res.reply, stage: state.stage, tool_calls: res.tool_calls });
    if (isNew) $("#chat-title").textContent = text.length > 30 ? `${text.slice(0, 30)}…` : text;
    loadConversations();
  } catch (e) {
    stopLoading();
    addMessage({ role: "assistant", content: `⚠ ${e.message}` }, { error: true });
    if (!input.value) input.value = text; // 다시 보낼 수 있게 복원
    autosize();
  } finally {
    state.sending = false;
    $("#send-btn").disabled = false;
    input.focus();
  }
}

function autosize() {
  const t = $("#chat-input");
  t.style.height = "auto";
  t.style.height = `${Math.min(t.scrollHeight, 200)}px`;
}

// ------------------------------------------------------------ 요약 패널
function trendIcon(dir) {
  return { "상승": "▲", "하락": "▼", "유지": "■" }[dir] || "·";
}

export async function loadSummaryPanel() {
  const box = $("#summary-box");
  try {
    const [s, mine] = await Promise.all([api.summary(), api.summary({ mine: true })]);
    const m = s.metrics || {};
    box.innerHTML = `
      <div class="sum-grid">
        <div class="sum-item wide"><span class="k">기간</span><span class="v" style="font-size:14px">${esc(s.period)}</span></div>
        <div class="sum-item"><span class="k">레코드</span><span class="v">${fmt(s.count)}개</span></div>
        <div class="sum-item"><span class="k">평균 글자 수</span><span class="v">${fmt(m.average)}</span></div>
        <div class="sum-item"><span class="k">최대</span><span class="v">${fmt(m.max)}</span></div>
        <div class="sum-item"><span class="k">최소</span><span class="v">${fmt(m.min)}</span></div>
      </div>
      <div class="trend" data-dir="${esc(s.trend_direction)}"><span class="trend-icon" aria-hidden="true">${trendIcon(s.trend_direction)}</span><span><b>최근 추세</b> ${esc(s.trend)}</span></div>
      <div class="sum-section">
        <h3>내가 쓴 기록 · ${fmt(mine.count)}건</h3>
        ${mine.count ? `<div class="trend" data-dir="${esc(mine.trend_direction)}"><span class="trend-icon" aria-hidden="true">${trendIcon(mine.trend_direction)}</span><span>${esc(mine.trend)}</span></div>
        <ul class="mini-list" style="margin-top:6px">${mine.recent.slice(0, 3).map((r) => `<li><span class="name">${esc(r.date)} ${esc(r.title || "(제목 없음)")}</span><span class="n">${fmt(r.value)}자</span></li>`).join("")}</ul>`
        : `<p class="hint" style="margin:0">'기록 관리' 탭에서 내 글쓰기 기록을 추가하면 AI가 참고해요.</p>`}
      </div>
      <div class="sum-section">
        <h3>장르 분포</h3>
        <ul class="mini-list">${s.by_genre.slice(0, 6).map((g) => `<li><span class="name">${esc(g.key)}</span><span class="n">${fmt(g.count)}편 · 평균 ${fmt(g.average)}자</span></li>`).join("")}</ul>
      </div>
      ${s.longest ? `<div class="sum-section"><h3>가장 긴 글</h3><p style="margin:0;font-size:13px">《${esc(s.longest.title || "제목 없음")}》 ${esc(s.longest.author || "")} · ${fmt(s.longest.value)}자</p></div>` : ""}`;
  } catch (e) {
    box.innerHTML = `<p class="form-error">요약을 불러오지 못했어요: ${esc(e.message)}</p>`;
  }
}

// ------------------------------------------------------------ 초기화
export function initChat() {
  setStage("자유");
  $(".stage-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) setStage(chip.dataset.stage);
  });
  $("#suggestions").addEventListener("click", (e) => {
    const b = e.target.closest(".suggestion");
    if (!b) return;
    const input = $("#chat-input");
    input.value = b.dataset.text;
    autosize();
    if (b.dataset.text.endsWith(":") || b.dataset.text.includes("\n")) input.focus();
    else send(b.dataset.text);
  });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#chat-input").value); });
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); }
  });
  $("#chat-input").addEventListener("input", autosize);
  $("#new-chat").addEventListener("click", newChat);
  $("#refresh-summary").addEventListener("click", loadSummaryPanel);
  $("#conv-list").addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) { e.stopPropagation(); removeConversation(del.dataset.del); return; }
    const item = e.target.closest(".conv-item");
    if (item) openConversation(item.dataset.id);
  });
  $("#conv-list").addEventListener("keydown", (e) => {
    const item = e.target.closest(".conv-item");
    if (item && (e.key === "Enter" || e.key === " ") && e.target === item) { e.preventDefault(); openConversation(item.dataset.id); }
  });
}
