# 글벗 — 내 기록을 아는 AI 글쓰기 코치

> 주제 선정 → 구상·개요 → 초고 → 퇴고까지, 시·수필·소설·동화·희곡 등 **장르에 상관없이** 글쓰기 전 과정을 돕는 AI 비서

| 구분 | URL |
|---|---|
| 프론트엔드 (Vercel) | `{{FRONTEND_URL}}` |
| 백엔드 API (Render) | `{{BACKEND_URL}}` |
| Swagger UI | `{{BACKEND_URL}}/docs` |

※ 백엔드는 Render 무료 플랜이라 15분간 요청이 없으면 잠듭니다. 첫 접속 때 30~60초 걸릴 수 있으며, 프론트엔드는 접속 즉시 `/health`로 서버를 깨우고 늦어지면 안내 배너를 띄웁니다.

---

## 1. 무엇을 해결하나요?

일반 챗봇에게 "요즘 내 글쓰기 어때?", "이번 주엔 뭘 써볼까?"라고 물으면 누구에게나 할 법한 답만 돌아옵니다.
글벗은 **날짜별 글쓰기 기록(시계열 데이터)**을 분석한 요약을 시스템 프롬프트에 넣어서(**컨텍스트 주입**) 내 상황에 맞춰 답합니다.

- **주제 선정**: 내가 적게 써 본 장르나 소재를 짚어 주제 후보와 첫 문장 예시를 제안
- **구상·개요**: 장르별 뼈대(시: 이미지→정서 전환, 수필: 경험→사유, 소설: 인물·갈등·시점)와 **내 평균 분량 기준** 개요
- **초고**: 막힌 장면의 다음 선택지, 최근 기록을 근거로 한 오늘의 목표 분량
- **퇴고**: `analyze_text` 도구로 글자 수·문장 길이·반복어·반복 어미를 **실제로 측정한 뒤** `원문 → 수정안 (이유)` 형식으로 피드백
- **참고 작품**: 위키문헌에서 모은 한국 근대문학(퍼블릭 도메인) {{WORK_COUNT}}편 중 필요한 예문을 찾아 인용

## 2. 데이터: 시계열 글쓰기 기록

| 필드 | 의미 | 예 |
|---|---|---|
| `date` | 작성(발표)일 | `2026-09-20` |
| `value` | 글자 수 (공백 제외) | `1240` |
| `memo` | 작업 메모 | `도입을 절반으로 줄임` |
| `genre`, `title`, `author`, `stage`, `source`, `excerpt`, `url` | 글쓰기 도메인 부가 정보 | `수필`, `가을 산책`, `초고` … |

데이터는 두 출처가 한 컬렉션에 섞여 있습니다.

1. **위키문헌 작품 {{WORK_COUNT}}편** — [한국어 위키문헌](https://ko.wikisource.org) MediaWiki API로 수집 ([`backend/scripts/import_wikisource.py`](backend/scripts/import_wikisource.py))
   - 분류(시·시조·수필·단편/중편/장편소설·동화·희곡)와 시집·수필집 하위 작품을 순회
   - **날짜**: 본문 끝의 창작일(예: `1941. 11. 20.`) → 설명란의 발표 연·월 → `NNNN년 작품` 분류 순으로 추출, 날짜를 알 수 없는 작품은 제외
   - **글자 수**: 위키 문법·틀·각주를 걷어낸 본문(원문/현대 표기 병기 시 현대 표기)의 공백 제외 글자 수
   - 기간 {{PERIOD}}, 장르 분포 {{GENRE_DIST}}
2. **내가 쓴 기록** — 웹 화면의 '기록 관리' 탭이나 `POST /api/data`로 추가 (`source = "직접 작성"`)

### 요약 정보 (`GET /api/data/summary`)

- 기간·개수, 글자 수 합계/평균/중앙값/최대/최소/표준편차, 가장 긴 글·짧은 글
- **최근 추세**: 날짜순으로 정렬한 뒤 최근 N건(N = 전체의 1/5, 5~30건) 평균과 직전 N건 평균을 비교해 ±5% 이상이면 상승/하락, 아니면 유지
- 장르별·출처별·단계별 분포, 최근 기록 5건
- `?mine=true`, `?genre=시`처럼 범위를 좁혀서도 요약 가능

## 3. 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| DB | Firebase Firestore (`firebase-admin`) — 컬렉션 `data`, `conversations` |
| AI | OpenAI Chat Completions API (기본 `gpt-4.1-mini`) + Function Calling |
| 프론트엔드 | HTML / CSS / JavaScript (프레임워크·차트 라이브러리 없이 SVG 직접 렌더링) |
| 배포 | Render (백엔드), Vercel (프론트엔드) |
| 보너스 | MCP 서버 (`mcp` Python SDK v2, stdio) |

## 4. 프로젝트 구조

```
writing-assistant/
├─ backend/
│  ├─ main.py                  # FastAPI 앱, CORS, 예외 처리, 라우터 등록
│  ├─ mcp_server.py            # (보너스) MCP 서버 — REST API를 도구로 노출
│  ├─ app/
│  │  ├─ config.py             # 환경 변수 로딩
│  │  ├─ firebase.py           # Firestore 초기화 (키는 환경 변수로만)
│  │  ├─ storage.py            # 저장소 추상화 (Firestore / 로컬 확인용 메모리)
│  │  ├─ schemas.py            # Pydantic 요청·응답 모델 (검증 규칙)
│  │  ├─ prompts.py            # 시스템 프롬프트 템플릿 + 단계별 코칭 가이드
│  │  ├─ seed.py               # 수집 데이터 → data 컬렉션 적재
│  │  ├─ routers/              # HTTP 계층: data, conversations, chat
│  │  └─ services/             # 비즈니스 로직: data, summary, conversation, chat, tools
│  ├─ scripts/
│  │  ├─ import_wikisource.py  # 위키문헌 API 수집 → data/wikisource_works.json
│  │  └─ seed_firestore.py     # JSON → Firestore 적재
│  └─ data/wikisource_works.json
├─ frontend/
│  ├─ build.js                 # Vercel 빌드: API_BASE_URL → public/config.js
│  ├─ vercel.json
│  └─ public/ (index.html, styles.css, config.js, js/*.js)
├─ docs/screenshots/
└─ render.yaml                 # Render Blueprint
```

**분리 기준**: `routers`는 HTTP(경로·상태 코드·쿼리 파라미터)만, `services`는 순수 로직만 담당합니다. 그래서 `/api/chat`의 요약 조회와 GPT 도구 실행이 `GET /api/data/summary`와 **같은 서비스 함수**를 재사용하고, 저장소는 `storage.py` 인터페이스 뒤에 숨겨서 Firestore API가 서비스 밖으로 새지 않습니다.

## 5. API

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/data` | 새 기록 추가 |
| GET | `/api/data` | 목록 (필터: `genre`, `source`, `stage`, `q`, `start`, `end`, `mine` / `order`, `limit`, `offset`) |
| GET | `/api/data/{id}` | 1건 조회 |
| PUT | `/api/data/{id}` | 수정 (보낸 필드만 변경) |
| DELETE | `/api/data/{id}` | 삭제 |
| GET | `/api/data/summary` | 요약 (프롬프트 주입용) |
| GET | `/api/data/statistics` | (보너스) 연대/연도/월별 시계열, 다작 작가, 기록 일수, 최장 연속 기록 |
| GET | `/api/data/export?format=csv\|json` | (보너스) 내보내기 다운로드 |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록 — **messages 미포함**(`message_count`, `preview`만) |
| GET | `/api/conversations/{id}` | 특정 대화 전체 messages 불러오기 (요구사항 A 방식) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | AI 대화 (요약 주입 + 도구 호출 + 자동 저장) |
| GET | `/health` | 헬스 체크 / 콜드스타트 깨우기 |

### 입력 검증 (Pydantic)

- `date`: 실제 날짜 형식만 허용, **미래 날짜 거부**
- `value`: 0 이상 2,000,000 이하 정수
- `memo`: 1~500자, 공백만 입력 불가
- `genre`·`stage`: 정해진 값(Literal)만 허용 → 통계가 오타로 쪼개지지 않음
- `PUT`: 필드를 하나도 보내지 않으면 422
- 채팅 `message` 1~8,000자, 대화 messages 1~200개
- 422 응답은 `"입력값을 확인해 주세요 — date: 미래 날짜는 기록할 수 없습니다."`처럼 화면에 그대로 보여줄 수 있는 한국어 문장으로 변환

**이유**: 잘못된 값이 DB에 한 번 들어가면 요약 통계와 AI 답변이 함께 틀어집니다. 요청 단계에서 막으면 라우터·서비스 코드는 "값이 올바르다"고 믿고 단순하게 짤 수 있고, 같은 규칙이 Swagger 문서에도 자동으로 나타납니다. 위키문헌 적재 스크립트도 같은 `DataCreate` 모델을 통과시킵니다.

## 6. 컨텍스트 주입과 AI 호출 흐름

```
사용자 메시지 (+ 단계: 주제 선정/구상·개요/초고/퇴고, 장르)
   │
   ▼
POST /api/chat
   ├─ ① summary_service.get_summary()          ← GET /api/data/summary 와 같은 함수
   │     + get_summary(mine=True)              ← '내가 쓴 기록'만의 요약
   ├─ ② prompts.build_system_prompt()          ← 요약 수치 + 단계별 코칭 가이드를 시스템 프롬프트에 삽입
   ├─ ③ OpenAI Chat Completions (tools=7개, max_completion_tokens 제한)
   │     └─ tool_calls 가 오면 서버가 도구 실행 → 결과를 role=tool 로 돌려주고 재호출 (최대 3회)
   └─ ④ conversation_service: 사용자 질문 + AI 답변(+ 호출한 도구 기록)을 conversations 에 자동 저장
   │
   ▼
{ conversation_id, reply, tool_calls[{name, arguments, reason}], summary_used, usage }
```

시스템 프롬프트 (요약 부분):

```
[사용자 데이터 요약]
- 데이터 기간: {period}
- 총 레코드: {count}개
- 주요 지표: 합계 {total}자 / 평균 {average}자 / 중앙값 {median}자 / 최대 {max}자 / 최소 {min}자
- 최근 트렌드: {trend}
- 장르 분포: …
[사용자가 직접 쓴 기록]
- 기간 / 건수 / 평균, 최근 트렌드, 작업 단계 분포, 최근 기록
[현재 작업 단계: 퇴고]
- 구조 → 문단 → 문장 → 단어 순서로 점검 …
```

**원리**: GPT는 우리 DB를 모르므로 매 요청마다 "지금 이 사용자의 데이터는 이렇다"는 사실을 시스템 메시지로 넣어 줍니다. 전체 레코드({{WORK_COUNT}}+건)를 넣으면 토큰이 크게 늘어나므로 **요약만** 넣고, 더 자세한 정보(특정 작품 본문, 기간별 통계, 이전 대화)는 모델이 필요할 때 도구로 가져오게 했습니다.

## 7. (보너스) Function Calling — 어떤 근거로 어떤 도구를 부르나

모든 도구에 필수 인자 `reason`(호출 이유)을 두어 **모델이 스스로 적은 근거**를 응답의 `tool_calls`와 대화 기록에 남기고, 채팅 화면에 칩(⚙)으로 보여줍니다.

| 도구 | 언제 호출하나 (description에 명시한 근거) | 내부 동작 |
|---|---|---|
| `get_data_summary` | 특정 장르·기간·'내 기록만'의 요약이 필요할 때 | `summary_service.get_summary(**filters)` |
| `get_statistics` | 연도/월/연대별 흐름, 다작 작가, 연속 기록을 물을 때 | `summary_service.get_statistics()` |
| `search_works` | 예문·참고 작품·특정 작가의 글·내가 예전에 쓴 글을 찾을 때 | `data_service.filter_records(q=…)` + 본문 발췌 |
| `list_my_records` | 최근 작업 내역, 단계별 진행 상황이 필요할 때 | `data_service.list_records(mine=True)` |
| `list_conversations` / `get_conversation` | "지난번에 얘기한 것"을 언급할 때 | `conversation_service` |
| `analyze_text` | 퇴고 요청 시 (시스템 프롬프트 원칙 4번) | 글자 수·원고지 매수·문장 길이·반복어·반복 어미·접속사 측정 |

예) "'고향'을 소재로 한 시를 쓰고 싶어. 참고할 만한 작품도 찾아줘."

```
1. 모델 → search_works {keyword:"고향", genre:"시", reason:"고향을 다룬 시 예문을 찾기 위해"}
2. 서버 → 위키문헌 데이터에서 검색, 발췌 포함 결과 반환
3. 모델 → 결과를 근거로 《제목》·지은이를 밝혀 인용하며 주제 후보 제시
4. 서버 → 답변 + tool_calls 를 conversations 에 저장
```

{{TOOL_EXAMPLES}}

## 8. (보너스) MCP 서버 — 멀티채널 연동

[`backend/mcp_server.py`](backend/mcp_server.py)는 같은 기능을 **MCP 도구**로 노출합니다. DB에 직접 붙지 않고 **배포된 REST API를 호출**하므로 외부 클라이언트도 웹과 똑같은 검증·저장 규칙을 거칩니다.

```
Claude Desktop / Claude Code (MCP 클라이언트)
   │ stdio (JSON-RPC)
   ▼
mcp_server.py ──HTTP──▶ Render 백엔드 (/api/data/summary, /api/data, /api/conversations …) ──▶ Firestore
```

도구: `get_data_summary`, `get_statistics`, `search_works`, `list_my_records`, `list_conversations`, `get_conversation`, `add_writing_record`

Claude Code에 등록:

```bash
claude mcp add geulbeot -e GEULBEOT_API_URL={{BACKEND_URL}} -- python backend/mcp_server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "geulbeot": {
      "command": "C:/…/writing-assistant/backend/.venv/Scripts/python.exe",
      "args": ["C:/…/writing-assistant/backend/mcp_server.py"],
      "env": { "GEULBEOT_API_URL": "{{BACKEND_URL}}" }
    }
  }
}
```

{{MCP_VERIFY}}

## 9. (보너스) 인사이트·UX

- **추가 지표**: 중앙값, 표준편차, 가장 긴/짧은 글, 단계별 분포, `/api/data/statistics`의 기간별 시계열·다작 작가·기록 일수·최장 연속 기록
- **시각화**: '통계' 탭의 기간별 막대그래프 (연대/연도/월 × 작품 수/평균 글자 수/총 글자 수, 마우스 오버 툴팁, 표로 보기)
- **내보내기**: 기록 관리 탭에서 현재 필터 기준 CSV(엑셀 한글 호환 BOM) / JSON 다운로드
- **다크 모드**: 우측 상단 토글 (OS 설정을 따르다가, 직접 고르면 브라우저에 기억)
- **선택 UI**: 채팅의 글쓰기 단계 칩(자유/주제 선정/구상·개요/초고/퇴고) + 장르 선택 → 시스템 프롬프트의 코칭 가이드가 바뀜

## 10. 로컬 실행 방법

### 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  → 값 채우기
python -m scripts.seed_firestore  # 위키문헌 작품을 Firestore에 적재 (최초 1회)
uvicorn main:app --reload         # http://localhost:8000/docs
```

- 위키문헌 데이터를 새로 수집하려면 `python scripts/import_wikisource.py` (요청 제한 때문에 10분 이상 걸림)
- Firebase 키 없이 화면만 확인하려면 `.env`에 `STORAGE_BACKEND=memory` (서버를 재시작하면 데이터가 초기화됨)

### 프론트엔드

```bash
cd frontend/public
python -m http.server 5500        # http://localhost:5500
```

`public/config.js`의 기본 API 주소는 `http://localhost:8000`입니다.

## 11. 환경 변수

### 백엔드 (Render / `backend/.env`)

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅(배포) | 서비스 계정 키 JSON **전체 문자열** |
| `FIREBASE_CREDENTIALS_PATH` | ✅(로컬) | 또는 키 파일 경로 (`./firebase-key.json`, git 제외) |
| `ALLOWED_ORIGINS` | ✅ | CORS 허용 도메인, 쉼표 구분 (예: `https://geulbeot.vercel.app`) |
| `OPENAI_MODEL` | | 기본 `gpt-4.1-mini` |
| `OPENAI_MAX_TOKENS` | | 답변 1회 최대 토큰, 기본 900 (과금 방지) |
| `MAX_TOOL_ROUNDS` | | 채팅 1회당 도구 호출 반복 상한, 기본 3 |
| `CHAT_HISTORY_LIMIT` | | GPT에 함께 보내는 이전 메시지 수, 기본 10 |
| `STORAGE_BACKEND` | | `firestore`(기본) / `memory`(로컬 확인용) |

### 프론트엔드 (Vercel)

| 이름 | 필수 | 설명 |
|---|---|---|
| `API_BASE_URL` | ✅ | 백엔드 주소 (예: `{{BACKEND_URL}}`). 빌드 때 `build.js`가 `config.js`로 만들어 넣음 |

## 12. 배포

### 백엔드 — Render

1. GitHub 저장소 연결 → **New Web Service** (또는 `render.yaml` Blueprint)
2. Root Directory `backend`, Build `pip install -r requirements.txt`, Start `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. 환경 변수: `OPENAI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ALLOWED_ORIGINS`, `PYTHON_VERSION=3.12.8`
4. 배포 후 `https://<서비스>.onrender.com/docs` 확인

### 프론트엔드 — Vercel

1. 같은 저장소 Import → Root Directory `frontend` (빌드 설정은 `vercel.json`)
2. 환경 변수 `API_BASE_URL` = Render 주소 → Deploy
3. 발급된 Vercel 주소를 Render의 `ALLOWED_ORIGINS`에 추가

### 왜 CORS·환경 변수·키 관리가 필요한가

- **CORS**: 프론트(`*.vercel.app`)와 백엔드(`*.onrender.com`)는 출처가 다르므로, 브라우저는 백엔드가 허용한 출처의 요청만 응답을 읽게 합니다. `ALLOWED_ORIGINS`에 우리 프론트만 넣어 다른 사이트가 사용자의 브라우저를 통해 API를 쓰지 못하게 합니다.
- **환경 변수**: 로컬·배포 환경마다 다른 값(API 주소, 허용 도메인)을 코드 수정 없이 바꿀 수 있고, 비밀 값을 코드에서 분리합니다.
- **키 관리**: OpenAI 키가 노출되면 타인이 내 비용으로 API를 쓰고, Firebase 서비스 계정 키는 DB 전체 관리자 권한입니다. 그래서 키는 `.env`(git 제외)와 Render 환경 변수에만 두고, 프론트엔드에는 절대 넣지 않습니다(브라우저 코드는 누구나 볼 수 있음). 모든 OpenAI 호출은 백엔드에서만 일어납니다.

### 비용 관리

- `max_completion_tokens`(기본 900), 도구 반복 3회, 이전 대화 10개로 요청당 토큰 상한을 둠
- 전체 데이터 대신 요약만 프롬프트에 넣음
- 요약·검색용 전체 레코드는 서버 메모리에 5분 캐시(쓰기 시 즉시 무효화)해 Firestore 읽기 횟수 절약

## 13. 스크린샷

| 데이터 요약이 보이는 채팅 | 데이터 관리 (CRUD) | 대화 기록 불러오기 |
|---|---|---|
| ![chat](docs/screenshots/chat.png) | ![data](docs/screenshots/data.png) | ![history](docs/screenshots/history.png) |

| 통계·시각화 | 다크 모드 | Swagger UI |
|---|---|---|
| ![insights](docs/screenshots/insights.png) | ![dark](docs/screenshots/dark.png) | ![swagger](docs/screenshots/swagger.png) |

## 14. 데이터 출처 및 라이선스

작품 데이터는 [한국어 위키문헌](https://ko.wikisource.org)의 퍼블릭 도메인 저작물(저작권 보호 기간 만료)이며, 각 레코드의 `url`에 원문 링크를 남겼습니다.
