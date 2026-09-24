"""대화 기록(conversations 컬렉션) 저장/조회/삭제."""

from __future__ import annotations

from ..firebase import CONVERSATIONS_COLLECTION
from ..schemas import Message
from ..storage import get_store, now


def _title_from(messages: list[dict]) -> str:
    first = next((m["content"] for m in messages if m["role"] == "user"), "새 대화")
    first = " ".join(first.split())
    return first[:30] + ("…" if len(first) > 30 else "")


def _brief(doc: dict) -> dict:
    messages = doc.get("messages", [])
    last = messages[-1]["content"] if messages else ""
    return {
        "id": doc["id"],
        "title": doc.get("title") or _title_from(messages),
        "message_count": len(messages),
        "preview": " ".join(last.split())[:80],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _dump(messages: list[Message]) -> list[dict]:
    out = []
    for m in messages:
        d = m.model_dump(mode="python", exclude_none=True)
        d.setdefault("created_at", now())
        out.append(d)
    return out


def list_conversations() -> list[dict]:
    docs = get_store().list_all(CONVERSATIONS_COLLECTION)
    briefs = [_brief(d) for d in docs]
    return sorted(briefs, key=lambda b: b["updated_at"] or b["created_at"] or now(), reverse=True)


def get_conversation(conv_id: str) -> dict | None:
    doc = get_store().get(CONVERSATIONS_COLLECTION, conv_id)
    if doc is None:
        return None
    return {**_brief(doc), "messages": doc.get("messages", [])}


def create_conversation(messages: list[Message], title: str | None = None) -> dict:
    dumped = _dump(messages)
    doc = get_store().add(CONVERSATIONS_COLLECTION, {"title": title or _title_from(dumped), "messages": dumped})
    return {**_brief(doc), "messages": doc["messages"]}


def append_messages(conv_id: str, messages: list[Message]) -> dict | None:
    current = get_store().get(CONVERSATIONS_COLLECTION, conv_id)
    if current is None:
        return None
    merged = current.get("messages", []) + _dump(messages)
    doc = get_store().update(CONVERSATIONS_COLLECTION, conv_id, {"messages": merged[-200:]})
    return {**_brief(doc), "messages": doc["messages"]}


def delete_conversation(conv_id: str) -> bool:
    return get_store().delete(CONVERSATIONS_COLLECTION, conv_id)
