// 기록 관리 화면: 추가/목록/수정/삭제 + CSV/JSON 내보내기
import { api } from "./api.js";
import { $, STAGES, esc, fmt, today, toast } from "./ui.js";

const PAGE_SIZE = 20;
const state = { offset: 0, total: 0, items: [], editingId: null, highlightId: null };
let onChange = () => {};

function filters() {
  return {
    mine: $("#f-mine").value,
    genre: $("#f-genre").value,
    q: $("#f-q").value.trim(),
    order: $("#f-order").value,
  };
}

function row(r) {
  const author = r.author ? `<span class="a">${esc(r.author)}</span>` : "";
  const src = r.source === "위키문헌"
    ? `<a class="tag src" href="${esc(r.url || "#")}" target="_blank" rel="noopener">위키문헌</a>`
    : `<span class="tag src">내 기록</span>`;
  return `
    <tr data-id="${esc(r.id)}" class="${r.id === state.editingId ? "editing" : ""}${r.id === state.highlightId ? " flash" : ""}">
      <td class="cell-date">${esc(r.date)}</td>
      <td class="cell-title">
        <span class="t">${esc(r.title || "(제목 없음)")}</span>${author} ${src}
        <span class="m">${esc(r.memo)}</span>
      </td>
      <td><span class="tag">${esc(r.genre)}</span></td>
      <td>${r.stage ? `<span class="tag">${esc(r.stage)}</span>` : ""}</td>
      <td class="num">${fmt(r.value)}</td>
      <td><div class="row-actions">
        <button class="btn btn-secondary btn-sm" data-edit="${esc(r.id)}" type="button">수정</button>
        <button class="btn btn-danger btn-sm" data-delete="${esc(r.id)}" type="button">삭제</button>
      </div></td>
    </tr>`;
}

function libraryRow(w) {
  const author = w.author ? `<span class="a">${esc(w.author)}</span>` : "";
  return `
    <tr data-id="${esc(w.id)}">
      <td class="cell-date">발표 시기 미상</td>
      <td class="cell-title">
        <span class="t">${esc(w.title)}</span>${author}
        <a class="tag src" href="${esc(w.url || "#")}" target="_blank" rel="noopener">위키문헌</a>
        <span class="m">${esc(w.memo)}</span>
      </td>
      <td><span class="tag">${esc(w.genre)}</span></td>
      <td></td>
      <td class="num">${fmt(w.value)}</td>
      <td><span class="caption">읽기 전용</span></td>
    </tr>`;
}

const isLibrary = () => $("#f-mine").value === "library";
const isBooks = () => $("#f-mine").value === "books";
const isReadOnly = () => isLibrary() || isBooks();

function bookRow(b) {
  const who = [b.author, b.publisher].filter(Boolean).map(esc).join(" · ");
  const link = b.url ? `<a class="tag src" href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.institution || "KCISA")}</a>`
    : `<span class="tag src">${esc(b.institution || "KCISA")}</span>`;
  return `
    <tr data-id="${esc(b.id)}">
      <td class="cell-date">서지 정보</td>
      <td class="cell-title">
        <span class="t">${esc(b.title)}</span>${who ? `<span class="a">${who}</span>` : ""} ${link}
        ${b.wikisource_url ? `<a class="tag src" href="${esc(b.wikisource_url)}" target="_blank" rel="noopener">위키문헌 원문</a>` : ""}
        <span class="m">${esc(b.collection || "")}${b.copies > 1 ? ` · 소장본 ${b.copies}권` : ""}</span>
      </td>
      <td><span class="tag">${esc(b.genre)}</span></td>
      <td></td>
      <td class="num">–</td>
      <td><span class="caption">읽기 전용</span></td>
    </tr>`;
}

export async function loadList() {
  const tbody = $("#data-rows");
  try {
    const f = filters();
    const res = isBooks()
      ? await api.listBooks({ q: f.q, genre: f.genre, limit: PAGE_SIZE, offset: state.offset })
      : isLibrary()
        ? await api.listLibrary({ q: f.q, genre: f.genre, limit: PAGE_SIZE, offset: state.offset })
        : await api.listData({ ...f, limit: PAGE_SIZE, offset: state.offset });
    state.total = res.total;
    state.items = res.items;
    tbody.innerHTML = res.items.length ? res.items.map(isBooks() ? bookRow : isLibrary() ? libraryRow : row).join("")
      : `<tr><td colspan="6" class="empty-note">조건에 맞는 기록이 없어요.</td></tr>`;
    $("#data-total").textContent = isBooks() ? `${fmt(res.total)}권 · 서지 정보`
      : isLibrary() ? `${fmt(res.total)}편 · 통계 제외` : `${fmt(res.total)}건`;
    $("#f-order").disabled = isReadOnly(); // 서재·도서 목록은 날짜순 정렬이 없다
    const page = Math.floor(state.offset / PAGE_SIZE) + 1;
    const pages = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
    $("#page-info").textContent = `${page} / ${pages}`;
    $("#prev-page").disabled = state.offset === 0;
    $("#next-page").disabled = state.offset + PAGE_SIZE >= res.total;
    state.highlightId = null;
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6"><p class="form-error">목록을 불러오지 못했어요: ${esc(e.message)}</p></td></tr>`;
  }
}

// ------------------------------------------------------------ 폼
function resetForm() {
  const form = $("#data-form");
  form.reset();
  form.date.value = today();
  form.genre.value = "수필";
  form.stage.value = "초고";
  state.editingId = null;
  $("#form-title").textContent = "새 기록 추가";
  $("#form-submit").textContent = "저장";
  $("#cancel-edit").hidden = true;
  $("#form-error").hidden = true;
  $("#count-source").value = "";
  updateCount();
  document.querySelectorAll("#data-rows tr.editing").forEach((tr) => tr.classList.remove("editing"));
}

function startEdit(id) {
  const r = state.items.find((x) => x.id === id);
  if (!r) return;
  const form = $("#data-form");
  state.editingId = id;
  form.date.value = r.date;
  form.value.value = r.value;
  form.title.value = r.title || "";
  form.genre.value = r.genre || "기타";
  form.stage.value = r.stage || "";
  form.memo.value = r.memo;
  $("#form-title").textContent = "기록 수정";
  $("#form-submit").textContent = "수정 저장";
  $("#cancel-edit").hidden = false;
  $("#form-error").hidden = true;
  document.querySelectorAll("#data-rows tr").forEach((tr) => tr.classList.toggle("editing", tr.dataset.id === id));
  form.scrollIntoView({ behavior: "smooth", block: "start" });
  form.value.focus();
}

function readForm() {
  const form = $("#data-form");
  const errors = [];
  const date = form.date.value;
  const value = form.value.value === "" ? NaN : Number(form.value.value);
  const memo = form.memo.value.trim();
  if (!date) errors.push("날짜를 입력해 주세요.");
  else if (date > today()) errors.push("미래 날짜는 기록할 수 없어요.");
  if (!Number.isInteger(value) || value < 0) errors.push("글자 수는 0 이상의 정수여야 해요.");
  if (!memo) errors.push("메모를 입력해 주세요.");
  const body = {
    date, value, memo,
    genre: form.genre.value,
    stage: form.stage.value || null,
    title: form.title.value.trim() || null,
  };
  const text = $("#count-source").value.trim();
  if (text) body.excerpt = text; // 붙여넣은 본문을 함께 저장 → AI 가 read_work 로 읽어 퇴고에 활용
  return { errors, body };
}

async function submitForm(e) {
  e.preventDefault();
  const { errors, body } = readForm();
  const errEl = $("#form-error");
  if (errors.length) {
    errEl.textContent = errors.join(" ");
    errEl.hidden = false;
    return;
  }
  errEl.hidden = true;
  const btn = $("#form-submit");
  btn.disabled = true;
  try {
    let saved;
    if (state.editingId) {
      saved = await api.updateData(state.editingId, body);
      toast(`'${saved.title || saved.date}' 기록을 수정했어요.`);
    } else {
      saved = await api.createData(body);
      toast(`'${saved.title || saved.date}' 기록을 저장했어요.`);
      state.offset = 0;
      $("#f-order").value = "desc";
    }
    state.highlightId = saved.id;
    resetForm();
    await loadList();
    onChange();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.hidden = false;
  } finally {
    btn.disabled = false;
  }
}

async function remove(id) {
  const r = state.items.find((x) => x.id === id);
  if (!confirm(`'${r ? r.title || r.date : "이 기록"}'을(를) 삭제할까요? 되돌릴 수 없어요.`)) return;
  try {
    await api.deleteData(id);
    toast("기록을 삭제했어요.");
    if (state.editingId === id) resetForm();
    if (state.items.length === 1 && state.offset > 0) state.offset -= PAGE_SIZE;
    await loadList();
    onChange();
  } catch (e) {
    toast(e.message, { error: true });
  }
}

async function exportData(format) {
  try {
    const f = filters();
    const res = await api.exportData({ format, mine: f.mine, genre: f.genre });
    const blob = await res.blob();
    const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || `writing-data.${format}`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast(`${name} 파일을 내려받았어요.`);
  } catch (e) {
    toast(e.message, { error: true });
  }
}

function updateCount() {
  const text = $("#count-source").value;
  const noSpace = text.replace(/\s/g, "").length;
  $("#count-result").textContent = `${fmt(noSpace)}자 (공백 포함 ${fmt(text.length)}자)`;
  if (text) $("#data-form").value.value = noSpace;
}

export function initData(changeCallback) {
  onChange = changeCallback || onChange;
  $("#stage-select").innerHTML = `<option value="">선택 안 함</option>` + STAGES.map((s) => `<option value="${s}">${s}</option>`).join("");
  resetForm();
  $("#data-form").addEventListener("submit", submitForm);
  $("#cancel-edit").addEventListener("click", resetForm);
  $("#count-source").addEventListener("input", updateCount);
  $("#data-rows").addEventListener("click", (e) => {
    const edit = e.target.closest("[data-edit]");
    const del = e.target.closest("[data-delete]");
    if (edit) startEdit(edit.dataset.edit);
    if (del) remove(del.dataset.delete);
  });
  let debounce;
  const refilter = () => { state.offset = 0; loadList(); };
  ["#f-mine", "#f-genre", "#f-order"].forEach((s) => $(s).addEventListener("change", refilter));
  $("#f-q").addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(refilter, 300); });
  $("#prev-page").addEventListener("click", () => { state.offset = Math.max(0, state.offset - PAGE_SIZE); loadList(); });
  $("#next-page").addEventListener("click", () => { state.offset += PAGE_SIZE; loadList(); });
  document.querySelectorAll("[data-export]").forEach((b) => b.addEventListener("click", () => exportData(b.dataset.export)));
}
