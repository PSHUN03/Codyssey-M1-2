// 백엔드 REST API 호출 래퍼
export const API_BASE = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function query(params = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, v);
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function request(path, { method = "GET", body, params, timeout = 90000, raw = false } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let res;
  try {
    res = await fetch(API_BASE + path + query(params), {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw new ApiError("서버 응답이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.", 0);
    throw new ApiError("서버에 연결할 수 없어요. 네트워크나 서버 상태를 확인해 주세요.", 0);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = `요청이 실패했어요 (HTTP ${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) { /* JSON 이 아니면 기본 문구 */ }
    throw new ApiError(detail, res.status);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => request("/health", { timeout: 70000 }),
  summary: (params) => request("/api/data/summary", { params }),
  statistics: (params) => request("/api/data/statistics", { params }),
  listData: (params) => request("/api/data", { params }),
  createData: (body) => request("/api/data", { method: "POST", body }),
  updateData: (id, body) => request(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body }),
  deleteData: (id) => request(`/api/data/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exportData: (params) => request("/api/data/export", { params, raw: true }),
  listLibrary: (params) => request("/api/library", { params }),
  listBooks: (params) => request("/api/books", { params }),
  listConversations: () => request("/api/conversations"),
  getConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`),
  deleteConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  chat: (body) => request("/api/chat", { method: "POST", body, timeout: 120000 }),
};
