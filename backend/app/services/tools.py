"""GPT Function Calling 도구 정의 + 실행기.

모든 도구에 `reason`(호출 이유) 인자를 필수로 두어, 모델이 어떤 근거로 도구를 골랐는지
응답/대화 기록에 남긴다. 실제 로직은 REST API 와 같은 서비스 함수를 재사용한다.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from ..schemas import GENRES, STAGES
from . import catalog_service, conversation_service, data_service, library_service, summary_service

_REASON = {"type": "string", "description": "이 도구를 호출하는 이유를 한 문장으로 (사용자에게 표시됨)"}


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {"reason": _REASON, **properties},
                "required": ["reason", *(required or [])],
                "additionalProperties": False,
            },
        },
    }


TOOLS = [
    _fn(
        "get_data_summary",
        "글 기록 DB의 요약(기간, 개수, 글자 수 통계, 추세, 장르/출처/단계 분포)을 조회한다. "
        "특정 장르·출처·기간이나 '내 기록만'의 요약이 필요할 때 사용한다.",
        {
            "genre": {"type": "string", "enum": list(GENRES)},
            "mine": {"type": "boolean", "description": "true면 사용자가 직접 작성한 기록만"},
            "start": {"type": "string", "description": "시작일 YYYY-MM-DD"},
            "end": {"type": "string", "description": "종료일 YYYY-MM-DD"},
        },
    ),
    _fn(
        "get_statistics",
        "연도/월/연대별 작품 수와 평균 글자 수 시계열, 다작 작가 순위, 연속 기록 일수를 조회한다.",
        {
            "group": {"type": "string", "enum": ["year", "month", "decade"]},
            "genre": {"type": "string", "enum": list(GENRES)},
            "mine": {"type": "boolean"},
        },
        ["group"],
    ),
    _fn(
        "search_works",
        "제목·지은이·메모·본문 발췌에서 키워드로 글을 찾는다. 참고할 만한 작품(예문), 특정 작가의 글, "
        "사용자가 예전에 쓴 글을 찾을 때 사용한다. 시계열 기록과 '참고 작품 서재'(발표 시기 미상 작품)를 함께 "
        "검색하며, 서재 작품은 date 가 null 이다. 결과에 본문 발췌와 id 가 포함된다.",
        {
            "keyword": {"type": "string", "description": "검색어 (예: 봄, 어머니, 윤동주)"},
            "genre": {"type": "string", "enum": list(GENRES)},
            "mine": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 5},
        },
    ),
    _fn(
        "search_books",
        "참고 자료 목록을 제목·저자·발행처·요약으로 찾는다. 출처: 공유마당 만료저작물(근대 문학·한시, 원문 링크), "
        "구텐베르크(한국 설화의 영어 번역), 문화공공데이터광장 보충 자료(번역원 번역서, 국립중앙·세종·어린이청소년도서관 "
        "사서추천, 청소년권장·대학신입생추천도서, 국립중앙도서관 소장 문학 등), KCISA 기관별 도서정보(시집·소설집·희곡 "
        "대본·평론). 본문은 없고 목록 정보와 링크만 있다(구텐베르크 제외). 더 읽어 볼 작품·책을 추천할 때 사용한다.",
        {
            "keyword": {"type": "string", "description": "검색어 (예: 시집, 윤동주, 희곡)"},
            "genre": {"type": "string", "enum": list(GENRES)},
            "source": {"type": "string", "enum": ["gongu", "gutenberg", "lib046", "lib047", "nlkf0201", "nlsf0401",
                                                  "nlcfsase", "kpef0102", "kpef0103", "kscd0820181", "nltot",
                                                  "nlkf021801", "nfmbook", "kcisa"],
                       "description": "출처를 좁힐 때만 (공유마당 gongu, 구텐베르크 gutenberg, 번역원 번역서 lib046·lib047, "
                                      "사서추천 nlkf0201·nlsf0401·nlcfsase, 청소년권장 kpef0102, 대학신입생 kpef0103, "
                                      "국립중앙도서관 소장 nltot, KCISA kcisa 등)"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 8},
        },
        ["keyword"],
    ),
    _fn(
        "read_work",
        "search_works·list_my_records 로 찾은 글의 저장된 본문을 읽는다. 사용자가 저장해 둔 자기 글을 "
        "퇴고·분석해 달라고 할 때, 또는 참고 작품의 더 긴 본문이 필요할 때 사용한다.",
        {"id": {"type": "string", "description": "search_works 결과의 id"}},
        ["id"],
    ),
    _fn(
        "list_my_records",
        "사용자가 직접 기록한 최근 글쓰기 기록(날짜, 글자 수, 단계, 메모)을 최신순으로 가져온다.",
        {
            "stage": {"type": "string", "enum": list(STAGES)},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    ),
    _fn(
        "list_conversations",
        "이전 대화 목록(제목, 미리보기)을 가져온다. 사용자가 '지난번에 얘기한 것'을 언급할 때 사용한다.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
    ),
    _fn(
        "get_conversation",
        "특정 이전 대화의 메시지를 가져온다. list_conversations 로 id 를 먼저 확인한다.",
        {"conversation_id": {"type": "string"}},
        ["conversation_id"],
    ),
    _fn(
        "analyze_text",
        "원고를 객관적으로 측정한다: 글자 수, 원고지 매수, 문장/문단 수, 평균 문장 길이, "
        "지나치게 긴 문장, 반복되는 단어, 반복되는 문장 끝맺음, 접속사 사용. 퇴고 피드백 전에 사용한다. "
        "사용자가 채팅에 붙여넣은 원고는 text 로, 저장된 글은 원문을 옮겨 적지 말고 id 로 넘긴다.",
        {"text": {"type": "string", "description": "채팅에 붙여넣은 원고 전문"},
         "id": {"type": "string", "description": "search_works·list_my_records 로 찾은 저장된 글의 id"}},
    ),
]

_PARTICLES = re.compile(r"(으로|에서|에게|까지|부터|처럼|보다|하고|이라|이다|은|는|이|가|을|를|에|의|도|로|와|과|만)$")
_STOPWORDS = {"그리고", "그러나", "하지만", "그래서", "그런데", "있다", "없다", "하는", "했다", "것이", "것은", "그것", "나는", "우리"}
_CONJUNCTIONS = ["그리고", "그러나", "하지만", "그래서", "그런데", "또한", "게다가", "따라서", "그러므로"]


def analyze_text(text: str) -> dict:
    text = text.strip()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?。…])\s+|\n+", text) if s.strip()]
    lengths = [len(s) for s in sentences]
    words = [_PARTICLES.sub("", w) for w in re.findall(r"[가-힣A-Za-z]{2,}", text)]
    word_freq = Counter(w for w in words if len(w) >= 2 and w not in _STOPWORDS)
    endings = Counter(re.sub(r"[^가-힣]", "", s)[-2:] for s in sentences if re.search(r"[가-힣]{2}", s))
    return {
        "chars_with_spaces": len(text),
        "chars_without_spaces": len(re.sub(r"\s", "", text)),
        "manuscript_pages_200": round(len(text) / 200, 1),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "avg_sentence_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "long_sentences": [s[:120] for s in sorted(sentences, key=len, reverse=True) if len(s) >= 70][:3],
        "repeated_words": [{"word": w, "count": c} for w, c in word_freq.most_common(8) if c >= 3],
        "repeated_endings": [{"ending": e, "count": c} for e, c in endings.most_common(3) if c >= 3],
        "conjunctions": {c: n for c in _CONJUNCTIONS if (n := text.count(c))},
    }


def _record_view(r: dict, excerpt: int = 0) -> dict:
    view = {k: r.get(k) for k in ("id", "date", "title", "author", "genre", "value", "stage", "source", "memo")}
    if excerpt and r.get("excerpt"):
        view["excerpt"] = r["excerpt"][:excerpt]
    view = {k: v for k, v in view.items() if v is not None}
    if r.get("date") is None and r.get("source") == "위키문헌":
        view["date"] = None  # 참고 작품 서재: 발표 시기 미상
        view["shelf"] = "참고 작품 서재"
    return view


def _summary_view(s: dict) -> dict:
    keep = ("period", "count", "metrics", "trend", "by_genre", "by_source", "by_stage", "longest", "shortest", "recent")
    return {k: s[k] for k in keep}


def execute(name: str, args: dict) -> dict:
    """도구 실행. 반환값은 JSON 직렬화 가능한 dict."""
    args = {k: v for k, v in args.items() if k != "reason" and v is not None}
    if name == "get_data_summary":
        return _summary_view(summary_service.get_summary(**args))
    if name == "get_statistics":
        stats = summary_service.get_statistics(group=args.pop("group", "year"), **args)
        stats["series"] = stats["series"][-40:]
        return stats
    if name == "search_works":
        limit = min(int(args.pop("limit", 3)), 5)
        keyword = args.pop("keyword", None)
        found = data_service.filter_records(data_service.all_records(), q=keyword, **args)
        if keyword:
            # 관련도: 제목 일치 > 제목 포함 > 지은이 > 메모·본문 발췌 (같은 순위면 날짜가 정확한 작품, 최신순)
            k = keyword.strip().lower()

            def rank(r):
                title, author = (r.get("title") or "").lower(), (r.get("author") or "").lower()
                return 0 if title == k else 1 if k in title else 2 if k in author else 3

            found = sorted(reversed(found), key=rank)
        else:
            found = list(reversed(found))
        if not args.get("mine"):  # 참고 작품 서재(발표 시기 미상)도 함께 — 같은 순위면 날짜가 있는 기록 먼저
            shelf = library_service.filter_works(library_service.all_works(), q=keyword, genre=args.get("genre"))
            if keyword:
                found = sorted(found + shelf, key=rank)
            else:
                found = found + shelf
        return {"total": len(found), "items": [_record_view(r, excerpt=250) for r in found[:limit]]}
    if name == "search_books":
        res = catalog_service.list_entries(q=args.get("keyword"), genre=args.get("genre"), source=args.get("source"),
                                           limit=min(int(args.get("limit", 5)), 8))
        keep = ("source_label", "title", "author", "genre", "year", "basis", "publisher", "origin", "note", "url",
                "wikisource_url")
        return {"total": res["total"], "by_source": res["by_source"],
                "note": "목록 정보와 링크만 있음. year 는 basis 가 가리키는 기준의 연도 (KCISA '기관 등록 연도'는 원작 발표일이 아님)",
                "items": [{k: b.get(k) for k in keep if b.get(k)} for b in res["items"]]}
    if name == "read_work":
        work = data_service.get_record(args["id"]) or library_service.get_work(args["id"])
        if not work:
            return {"error": "해당 id 의 글을 찾을 수 없습니다."}
        view = _record_view(work)
        view["text"] = (work.get("excerpt") or "")[:8000]
        view["text_is_partial"] = work.get("source") == "위키문헌"  # 가져온 작품은 앞부분만 저장
        return view
    if name == "list_my_records":
        limit = min(int(args.get("limit", 5)), 10)
        _, items = data_service.list_records(mine=True, stage=args.get("stage"), limit=limit)
        return {"items": [_record_view(r) for r in items]}
    if name == "list_conversations":
        limit = min(int(args.get("limit", 5)), 10)
        return {"items": [
            {k: str(v) for k, v in c.items() if k in ("id", "title", "preview", "updated_at")}
            for c in conversation_service.list_conversations()[:limit]
        ]}
    if name == "get_conversation":
        conv = conversation_service.get_conversation(args["conversation_id"])
        if not conv:
            return {"error": "해당 대화를 찾을 수 없습니다."}
        return {"title": conv["title"], "messages": [
            {"role": m["role"], "content": m["content"][:600]} for m in conv["messages"][-10:]
        ]}
    if name == "analyze_text":
        text = args.get("text") or ""
        if args.get("id"):
            work = data_service.get_record(args["id"]) or library_service.get_work(args["id"])
            if not work:
                return {"error": "해당 id 의 글을 찾을 수 없습니다."}
            text = work.get("excerpt") or ""
        if not text.strip():
            return {"error": "분석할 원고가 비어 있습니다. text 또는 id 를 넘겨 주세요."}
        return analyze_text(text[:20000])
    return {"error": f"알 수 없는 도구: {name}"}


def to_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)[:6000]
