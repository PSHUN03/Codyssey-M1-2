"""POST /api/chat 처리 흐름.

1. 데이터 요약 조회 (GET /api/data/summary 와 같은 summary_service.get_summary)
2. 요약을 시스템 프롬프트에 삽입 (컨텍스트 주입)
3. GPT 호출 (필요하면 Function Calling 으로 내부 기능을 도구처럼 호출, 최대 N회)
4. 사용자 질문 + AI 답변을 conversations 에 자동 저장
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from openai import OpenAI, OpenAIError

from ..config import settings
from ..prompts import build_system_prompt, summary_for_client
from ..schemas import ChatRequest, Message, ToolCallLog
from . import conversation_service, summary_service, tools

logger = logging.getLogger(__name__)


class ChatError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@lru_cache
def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None, timeout=60, max_retries=1)


def _complete(messages: list[dict], use_tools: bool):
    kwargs = {"tools": tools.TOOLS, "tool_choice": "auto"} if use_tools else {}
    return _client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        max_completion_tokens=settings.openai_max_tokens,
        **kwargs,
    )


def chat(req: ChatRequest) -> dict:
    if not settings.openai_api_key:
        raise ChatError(503, "OPENAI_API_KEY 가 설정되지 않았습니다. 서버 환경 변수를 확인하세요.")

    history: list[dict] = []
    if req.conversation_id:
        conv = conversation_service.get_conversation(req.conversation_id)
        if conv is None:
            raise ChatError(404, "이어서 대화할 conversation_id 를 찾을 수 없습니다.")
        history = [{"role": m["role"], "content": m["content"]} for m in conv["messages"][-settings.history_limit:]]

    # 1~2. 요약 조회 → 시스템 프롬프트 주입
    summary = summary_service.get_summary()
    mine = summary_service.get_summary(mine=True)
    system_prompt = build_system_prompt(summary, mine, req.stage, req.genre)

    messages: list[dict] = [{"role": "system", "content": system_prompt}, *history,
                            {"role": "user", "content": req.message}]

    # 3. GPT 호출 + 도구 실행 루프
    tool_logs: list[ToolCallLog] = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    try:
        for round_no in range(settings.max_tool_rounds + 1):
            response = _complete(messages, use_tools=round_no < settings.max_tool_rounds)
            if response.usage:
                usage_total["prompt_tokens"] += response.usage.prompt_tokens
                usage_total["completion_tokens"] += response.usage.completion_tokens
            msg = response.choices[0].message
            if not msg.tool_calls:
                break
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = tools.execute(call.function.name, args)
                except Exception as e:  # 도구 실패는 모델에게 알리고 계속 진행
                    logger.exception("tool %s failed", call.function.name)
                    result = {"error": str(e)}
                logged_args = {k: (v[:200] + "…" if isinstance(v, str) and len(v) > 200 else v)
                               for k, v in args.items() if k != "reason"}
                tool_logs.append(ToolCallLog(name=call.function.name, arguments=logged_args, reason=args.get("reason")))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": tools.to_json(result)})
    except OpenAIError as e:
        logger.exception("OpenAI 호출 실패")
        raise ChatError(502, f"AI 응답 생성 중 오류가 발생했습니다: {getattr(e, 'message', str(e))[:200]}") from e

    reply = (msg.content or "").strip() or "죄송해요, 답변을 만들지 못했어요. 질문을 조금 바꿔서 다시 물어봐 주세요."

    # 4. 대화 자동 저장
    new_messages = [
        Message(role="user", content=req.message, stage=req.stage),
        Message(role="assistant", content=reply, stage=req.stage, tool_calls=tool_logs or None),
    ]
    if req.conversation_id:
        conv = conversation_service.append_messages(req.conversation_id, new_messages)
    else:
        conv = conversation_service.create_conversation(new_messages)

    return {
        "conversation_id": conv["id"],
        "reply": reply,
        "tool_calls": tool_logs,
        "summary_used": summary_for_client(summary),
        "model": response.model,
        "usage": usage_total,
    }
