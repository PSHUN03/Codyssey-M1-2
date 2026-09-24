// 홈 채팅: 메시지 전송/표시, 로딩 표시, 주입된 요약 한 줄 / 대화 기록 화면: 목록·불러오기·삭제
import { api } from "./api.js";
import { $, $$, compact, esc, fmt, markdown, timeAgo, toast } from "./ui.js";

const TOOL_LABELS = {
  get_data_summary: "데이터 요약 조회",
  get_statistics: "기간별 통계 조회",
  search_works: "작품 검색",
  read_work: "본문 읽기",
  search_books: "참고 도서 검색",
  list_my_records: "내 기록 조회",
  list_conversations: "이전 대화 목록",
  get_conversation: "이전 대화 불러오기",
  analyze_text: "원고 분석",
};

const SUGGESTIONS = {
  "자유": [
    "내 글쓰기 기록을 요약해서 알려줘. 요즘 어떤 흐름이야?",
    "데이터에서 가장 긴 글과 가장 짧은 글은 뭐야?",
    "글쓰기 습관을 만들려면 목표를 어떻게 세우면 좋을까?",
  ],
  "주제 선정": [
    "내 기록을 보고 이번 주에 써볼 만한 주제 3개 추천해줘.",
    "요즘 한 장르만 쓴 것 같아. 새로 도전할 장르와 주제를 제안해줘.",
    "'고향'을 소재로 한 시를 쓰고 싶어. 참고할 만한 작품도 찾아줘.",
  ],
  "구상·개요": [
    "'첫 출근 날'을 주제로 한 수필 개요를 짜줘. 분량은 내 평균 정도로.",
    "짧은 단편소설을 구상하고 싶어. 인물과 갈등부터 같이 정해보자.",
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

// ------------------------------------------------------------ 메시지 렌더링
function toolChips(calls) {
  if (!calls || !calls.length) return "";
  return `<div class="tool-chips">${calls.map((c) => `
    <div class="tool-chip" title="${esc(JSON.stringify(c.arguments || {}))}">
      <span aria-hidden="true">⚙</span><span><code>${esc(c.name)}</code> ${esc(TOOL_LABELS[c.name] || "")}${c.reason ? ` — ${esc(c.reason)}` : ""}</span>
    </div>`).join("")}</div>`;
}

function addMessage({ role, content, stage, tool_calls, created_at }, { error = false, scroll = true } = {}) {
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
  if (scroll) el.scrollIntoView({ block: "end", behavior: "smooth" });
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
  setSaveState(null);
}

// 대화는 /api/chat 이 conversations 에 자동 저장한다 → 저장 결과를 채팅 카드에 표시
function setSaveState(conv) {
  const el = $("#save-state");
  if (!el) return; // 선택적 표시 요소 — 없으면(예: 옛 HTML 캐시) 조용히 건너뛴다
  if (!conv) { el.hidden = true; return; }
  el.textContent = `✓ 대화 기록에 저장됨 · 메시지 ${conv.message_count}개`;
  el.title = `conversations/${conv.id} — 눌러서 대화 기록 보기`;
  el.hidden = false;
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

// ------------------------------------------------------------ 대화 기록 화면
const plain = (s) => String(s || "").replace(/[*_`#>]+/g, "").replace(/\s+/g, " ").trim(); // 미리보기에서 마크다운 기호 제거

function renderConversations() {
  const list = $("#conv-list");
  if (!state.conversations.length) {
    list.innerHTML = `<li class="empty-card"><strong>아직 저장된 대화가 없어요</strong>홈에서 첫 메시지를 보내면 자동으로 저장돼요.</li>`;
    return;
  }
  list.innerHTML = state.conversations.map((c) => `
    <li class="conv-card" data-id="${esc(c.id)}" aria-current="${c.id === state.convId}">
      <span class="t">${esc(c.title)}</span>
      <span class="p">${esc(plain(c.preview))}</span>
      <span class="m">${esc(timeAgo(c.updated_at))} · 메시지 ${c.message_count}개</span>
      <div class="actions">
        <button class="btn btn-primary btn-sm" type="button" data-open="${esc(c.id)}">불러오기</button>
        <button class="btn btn-danger btn-sm" type="button" data-del="${esc(c.id)}">삭제</button>
      </div>
    </li>`).join("");
}

export async function loadConversations() {
  try {
    state.conversations = await api.listConversations();
    renderConversations();
  } catch (e) {
    $("#conv-list").innerHTML = `<li class="empty-card"><strong>대화 목록을 불러오지 못했어요</strong>${esc(e.message)}</li>`;
  }
}

async function openConversation(id) {
  if (state.sending) return;
  try {
    const conv = await api.getConversation(id);
    state.convId = conv.id;
    resetMessages();
    $("#chat-title").textContent = conv.title;
    conv.messages.forEach((m) => addMessage(m, { scroll: false }));
    setSaveState(conv);
    location.hash = "#/";
    requestAnimationFrame(() => ($("#messages").scrollTop = $("#messages").scrollHeight));
    toast(`'${conv.title}' 대화를 불러왔어요.`);
  } catch (e) {
    toast(e.message, { error: true });
  }
}

export function newChat() {
  if (state.sending) return;
  state.convId = null;
  resetMessages();
  $("#chat-title").textContent = "새 대화";
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
  let res;
  try {
    // 1) 서버 요청: 여기서 난 오류만 '전송 실패'로 보고 입력을 되돌린다
    try {
      res = await api.chat({
        message: text,
        conversation_id: state.convId,
        stage: state.stage,
        genre: $("#chat-genre").value || null,
      });
    } catch (e) {
      stopLoading();
      addMessage({ role: "assistant", content: `⚠ ${e.message}` }, { error: true });
      if (!input.value) input.value = text; // 다시 보낼 수 있게 복원
      autosize();
      return;
    }
    // 2) 응답 표시: 서버는 이미 답변을 만들고 대화를 저장했다. 여기서 화면 오류가 나도
    //    전송 실패로 알리거나 입력을 되돌리지 않는다 (같은 질문을 두 번 보내 중복 저장되는 것 방지)
    stopLoading();
    const isNew = !state.convId;
    state.convId = res.conversation_id;
    try {
      addMessage({ role: "assistant", content: res.reply, stage: state.stage, tool_calls: res.tool_calls });
      const title = $("#chat-title");
      if (isNew && title) title.textContent = text.length > 30 ? `${text.slice(0, 30)}…` : text;
      await loadConversations();
      setSaveState(state.conversations.find((c) => c.id === res.conversation_id) || { id: res.conversation_id, message_count: "" });
    } catch (e) {
      console.error("응답 표시 중 오류 (대화는 저장됨):", e);
      toast("답변은 저장됐지만 화면을 갱신하지 못했어요. 새로고침하면 대화 기록에서 볼 수 있어요.", { error: true });
    }
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

// ------------------------------------------------------------ 주입된 요약 (채팅 카드 안 한 줄)
export async function loadSummaryStrip() {
  const el = $("#summary-text");
  try {
    const s = await api.summary();
    const icon = { "상승": "▲", "하락": "▼", "유지": "■" }[s.trend_direction] || "";
    el.textContent = `${s.period} · ${fmt(s.count)}개 기록 · 평균 ${fmt(s.metrics?.average)}자 · 합계 ${compact(s.metrics?.total || 0)}자 · 최근 추세 ${icon} ${s.trend_direction}`;
    $("#summary-strip").title = `채팅할 때마다 이 요약이 AI의 시스템 프롬프트에 주입돼요.\n최근 추세: ${s.trend}`;
  } catch (e) {
    el.textContent = `요약을 불러오지 못했어요: ${e.message}`;
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
    if (b.dataset.text.includes("\n")) input.focus();
    else send(b.dataset.text);
  });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#chat-input").value); });
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); }
  });
  $("#chat-input").addEventListener("input", autosize);
  $("#conv-list").addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) { removeConversation(del.dataset.del); return; }
    const open = e.target.closest("[data-open]");
    if (open) openConversation(open.dataset.open);
  });
}
