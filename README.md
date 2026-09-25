# 글벗 — 내 기록을 아는 AI 글쓰기 코치

> 주제 선정 → 구상·개요 → 초고 → 퇴고까지, 시·수필·소설·동화·희곡 등 **장르에 상관없이** 글쓰기 전 과정을 돕는 AI 비서

| 구분 | URL |
|---|---|
| 프론트엔드 (Vercel) | https://geulbeot-psi.vercel.app |
| 백엔드 API (Render) | https://geulbeot-api.onrender.com |
| Swagger UI | https://geulbeot-api.onrender.com/docs |

※ 백엔드는 Render 무료 플랜이라 15분간 요청이 없으면 잠듭니다. 첫 접속 때 30~60초 걸릴 수 있으며, 프론트엔드는 접속 즉시 `/health`로 서버를 깨우고 늦어지면 안내 배너를 띄웁니다.

---

## 1. 무엇을 해결하나요?

일반 챗봇에게 "요즘 내 글쓰기 어때?", "이번 주엔 뭘 써볼까?"라고 물으면 누구에게나 할 법한 답만 돌아옵니다.
글벗은 **날짜별 글쓰기 기록(시계열 데이터)**을 분석한 요약을 시스템 프롬프트에 넣어서(**컨텍스트 주입**) 내 상황에 맞춰 답합니다.

- **주제 선정**: 내가 적게 써 본 장르나 소재를 짚어 주제 후보와 첫 문장 예시를 제안
- **구상·개요**: 장르별 뼈대(시: 이미지→정서 전환, 수필: 경험→사유, 소설: 인물·갈등·시점)와 **내 평균 분량 기준** 개요
- **초고**: 막힌 장면의 다음 선택지, 최근 기록을 근거로 한 오늘의 목표 분량
- **퇴고**: `analyze_text` 도구로 글자 수·문장 길이·반복어·반복 어미를 **실제로 측정한 뒤** `원문 → 수정안 (이유)` 형식으로 피드백
- **참고 작품**: 위키문헌·공유마당·구텐베르크·KCISA 도서정보에서 모은 문학 자료 **34,494건**(중복 제외) 중 필요한 예문을 찾아 인용하고 더 읽을 작품·책을 추천. 본문이 있는 위키문헌 작품은 3,873편(시계열 2,834 + 발표 시기 미상 서재 1,039)

## 2. 데이터: 시계열 글쓰기 기록

| 필드 | 의미 | 예 |
|---|---|---|
| `date` | 작성(발표)일 | `2026-09-20` |
| `value` | 글자 수 (공백 제외) | `1240` |
| `memo` | 작업 메모 | `도입을 절반으로 줄임` |
| `genre`, `title`, `author`, `stage`, `source`, `excerpt`, `url` | 글쓰기 도메인 부가 정보 | `수필`, `가을 산책`, `초고` … |

### 한눈에 보기 — 출처별 자료 (중복 제외, 통계 화면 '모든 자료 한눈에'와 `GET /api/catalog/stats`)

| 출처 | 자료 수 | 본문 | 시기 기준 | 저장 위치 |
|---|---|---|---|---|
| 위키문헌 시계열 | 2,834편 | 있음 (글자 수) | 발표·창작 연월일 (문서 근거) | Firestore `data` |
| 내가 쓴 기록 | 직접 추가 | 있음 | 작성일 | Firestore `data` |
| 위키문헌 서재 | 1,039편 | 있음 | **발표 시기 미상** (별도 막대) | Firestore `library` |
| 공유마당 만료저작물 | 12,388건 (원자료 14,193 − 위키문헌과 중복 1,805) | 목록 + 원문 링크 | 공표 연월 · 창작 연도, 없으면 시기 미상 | `data/gongu_works.json` |
| 구텐베르크 (한국 관련 영어 작품) | 7편 | 있음 (영어) | 초판 연도 | `data/gutenberg_works.json` |
| KCISA 기관별 도서정보 | 18,225건 (원자료 18,302 − 중복 77) | 서지 정보 | 제목의 발행 연도 → 없으면 **기관 등록 연도** | `data/kcisa_books.json` |
| 한국문학번역원 번역서 · 국립중앙도서관 사서추천 | 키 발급 후 수집 | 서지 정보 | 출간 연도 | `data/lti_books.json`, `data/nlk_books.json` |

- **통계에 넣는 방식**: 날짜와 글자 수가 모두 있는 위키문헌 시계열 + 내 기록은 기존처럼 **글자 수 요약·추세**(AI 프롬프트에 주입)에 쓰고, 모든 출처는 **작품 수 기준 통합 통계**에 함께 넣는다. 발표 시기를 모르는 자료는 추측하지 않고 '시기 미상' 막대로 따로 센다.
- **중복**: 같은 작가·같은 대표 제목이면 본문이 있는 출처를 우선해 한 번만 센다 (위키문헌 > 구텐베르크 > 공유마당 > 번역원 > 국립중앙도서관 > KCISA).
- **검토했지만 넣지 않은 곳**: 문장웹진·글틴·시마을·리디북스(현재 작가·청소년의 저작권 있는 글이고 이용 허락·API가 없음, 시마을은 robots.txt로 크롤링 봇 차단, 리디북스는 봇 차단), 한국고전종합DB(무단 크롤링 금지 명시), 공유마당 국립중앙도서관 제공분(호적·교지 등 고문서 스캔본 위주), 구텐베르크 세계 문학 전체(한국어 글쓰기 도우미 성격상 한국 관련 작품만).

데이터는 아래 출처들로 이루어져 있습니다.

1. **위키문헌 작품 2,834편** — [한국어 위키문헌](https://ko.wikisource.org) MediaWiki API로 수집 ([`backend/scripts/import_wikisource.py`](backend/scripts/import_wikisource.py))
   - **범위 (네 갈래로 찾고 한곳에서 거름)**
     1. **문학 분류 트리**: `문학`·`장르별 문학`·`한국의 문학`·`시`·`소설`·`수필`·`희곡`·`동화`·`전승문학`·`아동문학`에서 하위 분류를 재귀로 내려가며 97개 분류 순회 (고전소설·신소설·판소리·한국의 노래·문학 평론 등 포함, 요리책·논문·수상자 인물 분류는 제외)
     2. **연도별 작품 분류** 전체(세기 → 연대 → 연도 224개) — 이 경로로만 찾은 문서는 자기 장르 분류가 있어야 넣음
     3. **저자 문서** 430명(시인·소설가·수필가·평론가 분류 + 수집한 작품의 지은이)의 작품 목록 링크 — 링크가 달린 **소제목(`== 소설 ==`, `=== 동시/동요 ===` …)으로 장르**를 정하고, 문학 작가 분류에 없고 문학 소제목도 없는 저자 문서(의서·실록 편찬자 등)의 '저작' 목록 284건은 제외
     4. 연도 분류로 먼저 찾았지만 장르 분류가 없는 문서도 **저자 문서의 소제목·문학 작가 여부로 장르를 보충**하고(예: 현진건 「고향」, 김동인 「발가락이 닮았다」, 조명희 「낙동강」), 그래도 없으면 **머리말 설명란의 문구**(`작자 미상의 고전소설`, `강호가사`, `편지글`)로 판단. 역사서·선언문·성명서 등은 제외
     5. **목차 문서**: 시집·산문집·동화집처럼 **수록작이 각각 한 작품**인 문집(79개)은 수록작별로, 장편소설·희곡처럼 **장(章)으로 나뉜 한 작품**(73개, 예: 《무정》 7개 장, 《상록수》 17개 장, 《피노키오의 모험》)은 장 본문을 **합쳐 한 편**으로 셈 (하위 문서 이름이 대부분 `제1장`·`1`·`상권` 형식이면 장으로 판단)
   - **날짜**: 본문 끝의 창작일(예: `1941. 11. 20.`) → 설명란의 출전 발표 연·월·일(`1928년 7월 《조선지광》`, `〈조선〉, 1932.4.` 등 — 월까지 적혀 있으면 분류보다 우선) → 문서의 `NNNN년 작품` 분류 → **저자 문서의 작품 연보**(예: `* [[빈처]] (1921년)`) → 수록 시집 간행일(메모에 `수록 문집 간행 연도 기준`으로 표시). 날짜를 알 수 없는 작품은 추측하지 않고 제외
   - **신뢰성 규칙**
     - 시집 하위 문서는 '제목' 칸이 시집 이름이라 **'부제' 칸(또는 문서 경로)**에서 작품 제목을 읽고, 장르 분류에 함께 걸려 있어도 시집의 지은이·날짜를 물려받음 (예: 「나룻배와 행인」 ← 《님의 침묵》, 「가는 길」 ← 《진달래꽃》 1925-12-26)
     - 지은이 표기의 괄호 속 본명·한자 병기는 떼어 같은 작가가 통계에서 둘로 갈리지 않게 함 (예: `김소월(김정식)` → `김소월`)
     - 같은 지은이의 같은 작품이 여러 판본에 있으면(초판 시집과 후대 합본 등) **가장 정확하고 이른 날짜 하나**만 남김
     - 시집이 지은이 **사망 후 10년이 넘어** 나온 후대 판본이면(예: 1988년 선집 《향수》) 그 연도는 발표일이 아니므로 쓰지 않음 (사망 연도는 저자 문서 머리말에서 읽음). 사후 10년 이내의 유고 시집은 `사후 간행 문집`으로 표시
     - 시집의 서문·발문·후기 등 부속 글은 제외 (다른 사람이 쓴 경우가 많음)
     - 번역 작품은 역자를 밝히고(《오뇌의 무도》 → `김억(옮김)`), 위키 사용자가 요즘 옮긴 번역문·한국어 본문이 없는 외국어 원문은 제외
     - 머리말 틀의 필드 이름이 문서마다 달라(`지은이`·`글쓴이`·`author`, `설명`·`notes`, 한 줄짜리 틀) 모두 인식하고, 각주 속 인용 틀의 `제목=`은 무시 (예: 《백범일지》 → 김구)
     - 설명란의 날짜가 **대본으로 쓴 후대 판본**(`1971년 2월 1일 2판`)이면 발표일로 쓰지 않음 (예: 《담원시조》 1948)
     - **저작권**: 한국 저작권법상 보호 기간이 끝난 **1962년 이전 사망 작가**의 작품만 수록. 위키문헌 라이선스 틀과 관계없이 1963년 이후 사망 작가(공동 작가 포함)의 작품 9편은 제외
   - **실존 검증**: 전 작품을 문서 번호(pageid)로 다시 조회 → 시계열 2,834편 + 서재 1,039편 = 3,873편 모두 존재·제목 일치 ([`docs/data-verification.md`](docs/data-verification.md), `python -m scripts.verify_works`)
   - 요청 제한을 지키려고 요청 간격 1.5초 + `Retry-After` 재시도, 위키미디어 정책에 맞는 User-Agent(연락처 포함), 응답은 로컬 캐시(git 제외)
   - 장르 분포: 시 1,513 · 수필 396 · 소설 340 · 단편소설 218 · 시조 107 · 동화 63 · 기타 57 · 장편소설 47 · 평론 15 · 희곡 13 · 한시 13 · 노래 13 · 서간 13 · 중편소설 13 · 가사 11 · 고전시가 2
2. **내가 쓴 기록** — 웹 화면의 '기록 관리' 탭이나 `POST /api/data`로 추가 (`source = "직접 작성"`). 본문을 붙여넣으면 전문이 함께 저장되어 AI가 `read_work`로 읽고 퇴고를 도울 수 있음
3. **참고 작품 서재 1,039편 (발표 시기 미상)** — 장르: 시 239 · 시조 226 · 노래 226 · 수필 63 · 한시 62 · 기타 61 · 소설 50 · 고전시가 38 · 서간 20 · 가사 17 · 단편소설 15 · 판소리 7 · 희곡 5 · 평론 4 · 장편소설 3 · 동화 3
   — 위키문헌에 실제로 있지만 **발표 시기를 확인할 수 없는** 작품. 날짜를 추측해 넣지 않고 별도 컬렉션 `library`에 담아 글자 수 요약·추세(AI 주입)에서는 빼고, **통합 통계의 '발표 시기 미상' 막대**, AI 작품 검색(`search_works`)·원격 MCP·기록 관리의 '참고 작품 서재' 목록에서 씀
   - 본문이 스캔본 페이지에서 불러오는 형식(`<pages index=…>`)인 문서는 위키문헌이 **렌더링한 본문**을 받아 글자 수를 셈 (머리말 상자·쪽번호·각주·옛한글 안내 상자·라이선스 안내는 제외)
   - 이미 날짜와 함께 수록된 작품의 다른 판본, 서재 안의 중복은 제외
4. **KCISA 참고 자료 18,302건 (서지 정보)** — [한국문화정보원 문화 공공데이터광장](https://www.culture.go.kr/data) `문화체육관광부 외_기관별 도서정보`(API_LIB_051) ([`import_kcisa.py`](backend/scripts/import_kcisa.py), [`kcisa_build.py`](backend/scripts/kcisa_build.py))
   - 이 API는 검색 조건 없이 전체 **390,565건**을 1,000건씩 391쪽으로만 주므로 전 쪽을 받아(동시 4개 요청, 이어받기 가능) 로컬에서 문학 자료만 고름
   - 선별: 한국문학번역원 근대문학 전부 + 제목·자료 형식에 문학 형식이 드러난 자료(`공연대본`·희곡, 시집·시조집, 소설집·장편소설, 수필·에세이, 동화, 평론·비평, 문학전집·작품집). `[CD]`·`[DVD]`·공연 프로그램·도면 등 비문학 형식, '시집가는 날'·'인문학의 다섯 시선'처럼 낱말만 겹치는 제목, 음악·무용·미술 평론은 제외
   - **'권'이 아니라 '자료'**: 약 8,400건이 극단의 공연대본, 수천 건이 잡지의 평론·비평 기사이고 일반 도서(시집·소설집 등)는 일부. 같은 자료의 소장본 712건은 합쳐 `copies`에 기록
   - 장르: 희곡(공연대본) 10,237 · 평론 2,569 · 시 1,980 · 기타 1,139 · 소설 1,017 · 수필 988 · 동화 324 (위키문헌과 겹친 자료는 원문 장르를 따름) / 소장 기관: 한국문화예술위원회 예술자료원 18,101 · 국립어린이청소년도서관 142 · 한국문학번역원 51 · 문화체육관광부 8
   - **연도**: 본문이 없고 `ISSUED_DATE`는 원작 발행일이 아니라 기관의 등록·디지털화 날짜(대부분 2013~2017)라서, 제목에 발행 연도가 있으면(`2008 신춘문예 당선작`, `(1982)이상문학상 수상작품집` — 1,037건) 그 연도를, 없으면 **기관 등록 연도**(17,265건)를 쓰고 통계에 근거를 함께 표시 (`1920-30년대 희곡 연구`처럼 다루는 시대를 적은 연도는 쓰지 않음)
   - 쓰는 곳: 통합 통계, `GET /api/books`·`GET /api/catalog`, AI 도구 `search_books`(읽을거리 추천), 기록 관리의 '참고 자료' 목록
   - 읽기 전용이라 Firestore 대신 백엔드에 포함한 JSON(`data/kcisa_books.json`)을 메모리에서 검색 → Firestore 무료 한도(읽기 5만·쓰기 2만/일)를 쓰지 않음
5. **공유마당 만료저작물 14,193건 → 통계 12,388건** — [한국저작권위원회 공유마당](https://gongu.copyright.or.kr) 어문 '만료저작물'(저작재산권 보호 기간이 끝난 퍼블릭 도메인) 중 한국저작권위원회 제공 12,750건 + 한국고전번역원 제공 1,523건 ([`import_gongu.py`](backend/scripts/import_gongu.py))
   - 상세 페이지의 공표 연월·창작 연도·요약·장르 태그·원문 출전(예: 《개벽》)을 모으고, **원문 파일은 받지 않음**: robots.txt 가 원문 파일 경로(`/upload/`)를 모든 봇에 막고 다운로드에 이용 동의 절차가 있어서 목록 정보와 원문 링크만 저장
   - 장르: 태그를 우선하되 '시' 태그는 요약문의 더 구체적인 갈래(시조·한시·동요)를 따르고, 조선·고려 문인의 한자 제목 작품은 한시로. 성경 해설('학습물')·교양 강좌·고증·취지서는 제외
   - 한국고전번역원 제공분의 공표 연도(1960~80년대)는 **번역본이 나온 해**라 원작 시기로 쓰지 않고 '시기 미상'으로 둠
   - 장르(원자료): 시 5,349 · 한시 2,466 · 수필 2,036 · 기타(고전 문집 번역) 1,544 · 단편소설 1,004 · 평론 878 · 시조 389 · 노래 166 · 동화 125 · 소설 98 · 희곡 85 · 장편소설 41 · 가사 11 · 고전시가 1 / 시기: 공표 월 4,470 · 공표 연도 2,062 · 창작 연도 533 · 미상 7,128
   - 요청 간격 1초·연락처가 있는 User-Agent, 이어받기 가능 (4개 프로세스로 나눠 받음)
6. **구텐베르크 한국 관련 문학 7편** — [Project Gutenberg](https://www.gutenberg.org)의 한국어 책은 사전 1권뿐이라, 주제어 Korea 36권 중 문학만: H. N. Allen 《Korean Tales》(1889), 임방·이륙 원작 《Korean Folk Tales》(J. S. Gale 역, 1913), W. E. Griffis 《Korean Fairy Tales》(1922) 등 ([`import_gutenberg.py`](backend/scripts/import_gutenberg.py), 영어 본문 글자 수 포함). 역사·여행기·전쟁 기록과 국내 저작권이 남은 1950년대 이후 작가(《The Long March》)는 제외
7. **한국문학번역원 번역출간DB · 국립중앙도서관 사서추천도서(문학)** — 수집기([`import_bib_apis.py`](backend/scripts/import_bib_apis.py)) 준비 완료, 두 기관의 API 키(`LTI_API_KEY`, `NLK_API_KEY`)를 발급받으면 `python -m scripts.import_bib_apis lti|nlk` 로 추가

**중복 검토** ([`docs/duplicates-report.md`](docs/duplicates-report.md), `python -m scripts.review_duplicates`)

| 구분 | 결과 | 처리 |
|---|---|---|
| 위키문헌 — 같은 작품의 여러 판본 | 82편 | 날짜 근거가 가장 정확하고 이른 판본 하나만 |
| 위키문헌 — 서재 안의 중복·날짜 있는 판본과 겹침 | 150편 | 날짜 있는 판본 우선, 서재 안에서는 본문이 긴 쪽 |
| KCISA — 같은 책의 소장본 여러 권 | 712권 | 한 권으로 합치고 `copies`에 권수 기록 |
| KCISA — 같은 제목·작가, 발행처가 다른 판본 | 197종 | 서로 다른 판본이라 유지 |
| 위키문헌 ↔ KCISA — 같은 작가·같은 제목 | 50건 | 도서에 위키문헌 원문 링크(`wikisource_url`) 연결, 장르가 없던 번역원 자료는 원문 장르를 따름 |
| 통합 통계 — 공유마당이 위키문헌과 겹침 | 1,805건 | 본문이 있는 위키문헌 쪽만 셈 |
| 통합 통계 — KCISA가 앞 순위 출처와 겹침 | 77건 | 앞 순위 출처 쪽만 셈 |
| 공유마당 안의 같은 제목 | 291건 | 김정희 「기이(其二)」 연작, 여러 편의 「무제」, 이상 「선에 관한 각서」 1~7처럼 **서로 다른 작품**이라 합치지 않음 |

자세한 분석 결과(연대별·장르별 통계, 날짜 정밀도, 작가 순위)는 [`docs/data-analysis.md`](docs/data-analysis.md) — `python -m scripts.analyze_data`가 서비스와 같은 요약 함수로 생성합니다.

### 요약 정보 (`GET /api/data/summary`)

- 기간·개수, 글자 수 합계/평균/중앙값/최대/최소/표준편차, 가장 긴 글·짧은 글
- **최근 추세**: 날짜순으로 정렬한 뒤 최근 N건(N = 전체의 1/5, 5~30건) 평균과 직전 N건 평균을 비교해 ±5% 이상이면 상승/하락, 아니면 유지
- 장르별·출처별·단계별 분포, 최근 기록 5건
- `?mine=true`, `?genre=시`처럼 범위를 좁혀서도 요약 가능

## 3. 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| DB | Firebase Firestore (`firebase-admin`) — 컬렉션 `data`, `conversations`, `library` (+ 읽기 전용 참고 도서 JSON) |
| AI | OpenAI Chat Completions API + Function Calling — 모델 `gpt-5.4-mini` (Codyssey OpenAI 호환 게이트웨이 `OPENAI_BASE_URL` 경유, 개인 OpenAI 키면 주소만 비우면 됨) |
| 테스트 | pytest 18개 (메모리 저장소 + 가짜 GPT 클라이언트) |
| 프론트엔드 | HTML / CSS / JavaScript (프레임워크·차트 라이브러리 없이 SVG 직접 렌더링) |
| 배포 | Render (백엔드), Vercel (프론트엔드) |
| 보너스 | MCP 서버 (`mcp` Python SDK v2 — 원격 Streamable HTTP `/mcp` + 로컬 stdio) |

## 4. 프로젝트 구조

```
writing-assistant/
├─ backend/
│  ├─ main.py                  # FastAPI 앱, CORS, 예외 처리, 라우터 등록
│  ├─ mcp_server.py            # (보너스) 로컬 stdio MCP 서버 — REST API를 도구로 노출
│  ├─ app/
│  │  ├─ config.py             # 환경 변수 로딩
│  │  ├─ firebase.py           # Firestore 초기화 (키는 환경 변수로만)
│  │  ├─ storage.py            # 저장소 추상화 (Firestore / 로컬 확인용 메모리)
│  │  ├─ schemas.py            # Pydantic 요청·응답 모델 (검증 규칙)
│  │  ├─ prompts.py            # 시스템 프롬프트 템플릿 + 단계별 코칭 가이드
│  │  ├─ seed.py               # 수집 데이터 → data(시계열) · library(발표 시기 미상) 적재
│  │  ├─ rate_limit.py         # /api/chat 요청 횟수 제한
│  │  ├─ mcp_remote.py         # (보너스) 원격 MCP 서버 /mcp
│  │  ├─ routers/              # HTTP 계층: data, library, books, catalog, conversations, chat
│  │  └─ services/             # 비즈니스 로직: data, library, books, catalog(통합 통계), summary, conversation, chat, tools
│  ├─ scripts/
│  │  ├─ import_wikisource.py  # 위키문헌 API 수집 → data/wikisource_works.json
│  │  ├─ import_kcisa.py       # KCISA 기관별 도서정보 전체 다운로드 → kcisa_build.py 로 문학 자료 선별
│  │  ├─ import_gongu.py       # 공유마당 만료저작물 어문 목록 수집
│  │  ├─ import_gutenberg.py   # 구텐베르크 한국 관련 문학
│  │  ├─ import_bib_apis.py    # 한국문학번역원·국립중앙도서관 서지 API (키 필요)
│  │  ├─ review_duplicates.py  # 출처 간·출처 내 중복 검토 → docs/duplicates-report.md
│  │  ├─ seed_firestore.py     # JSON → Firestore 적재
│  │  ├─ analyze_data.py       # 분석 리포트 → docs/data-analysis.md
│  │  ├─ verify_works.py       # 전 작품 실존 재검증 → docs/data-verification.md
│  │  └─ mcp_smoke_test.py     # MCP 클라이언트로 원격/stdio 도구 호출 검증
│  ├─ tests/                   # pytest
│  └─ data/ (wikisource_works.json, gongu_works.json, gutenberg_works.json, kcisa_books.json)
├─ frontend/
│  ├─ build.js                 # Vercel 빌드: API_BASE_URL → config.js, 자산 주소에 배포 버전(?v=) 부착
│  ├─ vercel.json
│  └─ public/ (index.html, styles.css, config.js, js/*.js)
├─ docs/ (data-analysis.md, data-verification.md, duplicates-report.md, capture_screenshots.py, screenshots/)
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
| GET | `/api/library` | 참고 작품 서재 (발표 시기 미상 작품, 검색·장르 필터·페이지, 시계열 통계 제외) |
| GET | `/api/books` | KCISA 참고 자료 (문학 자료 서지 정보, 검색·장르 필터·페이지) |
| GET | `/api/catalog/stats` | **통합 통계** — 모든 출처(중복 제외)의 출처별·연대(세기)별·장르별 작품 수, 발표 시기 미상 별도 집계 (`group=decade\|century`, `genre`) |
| GET | `/api/catalog` | 참고 자료 통합 검색 (공유마당·구텐베르크·번역원·국립중앙도서관·KCISA, `source`·`genre`·`q`) |
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

## 6. Firestore 설계와 CRUD

```
(Firestore, asia-northeast3)
├─ data/{자동 ID}                         ← 시계열 기록 1건 = 문서 1개
│    date: "1941-11-20"   value: 64   memo: "《서시》 윤동주 — 창작일 기준"
│    genre: "시"  title  author  stage  source: "위키문헌" | "직접 작성"
│    excerpt(본문 앞 300자)  url  pageid(중복 방지)  created_at  updated_at
└─ conversations/{자동 ID}                ← 대화 1개 = 문서 1개
     title: "가을 수필 주제 찾기"   created_at   updated_at
     messages: [ {role, content, stage, created_at, tool_calls:[{name, arguments, reason}]}, … ]
```

- **왜 이렇게 나눴나**: 기록은 목록·필터·통계의 단위라 1건 = 1문서. 대화는 항상 통째로 불러오므로 메시지를 배열로 한 문서에 담아 읽기 1회로 끝냅니다 (최대 200개로 잘라 1MB 문서 한도를 지킴).
- **날짜는 `YYYY-MM-DD` 문자열**: 문자열 정렬이 곧 시간순이라 추세 계산과 기간 필터가 단순해집니다.
- **CRUD 구현** ([`app/storage.py`](backend/app/storage.py)):

| 동작 | Firestore 호출 |
|---|---|
| Create | `collection("data").add(doc)` — 자동 ID, `created_at/updated_at` 서버에서 기록 |
| Read (목록) | `collection("data").stream()` → 서버 메모리에 1시간 캐시, 필터·정렬·페이지는 캐시에서 처리 |
| Read (1건) | `document(id).get()` |
| Update | `document(id).update(바뀐 필드)` — 없는 ID는 404 |
| Delete | `document(id).delete()` — 없는 ID는 404 |
| 대량 적재 | `db.batch()` 400건씩 `commit()` (시드 스크립트) |

- 이 서버를 거친 쓰기는 **바뀐 문서만 캐시에 반영**해서 다음 요약·채팅이 곧바로 최신 데이터를 보면서도, 기록 1건 저장에 2,600여 건을 다시 읽지 않습니다 (Firestore 무료 한도: 하루 읽기 5만 회). 캐시는 1시간마다 새로 읽습니다.
- 서비스 계정 키는 `FIREBASE_SERVICE_ACCOUNT_JSON`(배포) 또는 `FIREBASE_CREDENTIALS_PATH`(로컬)로만 받고, Firestore 보안 규칙은 **프로덕션 모드(클라이언트 직접 접근 차단)** 입니다. 브라우저는 반드시 백엔드 API를 거칩니다.

## 7. 컨텍스트 주입과 AI 호출 흐름

```
사용자 메시지 (+ 단계: 주제 선정/구상·개요/초고/퇴고, 장르)
   │
   ▼
POST /api/chat
   ├─ ① summary_service.get_summary()          ← GET /api/data/summary 와 같은 함수
   │     + get_summary(mine=True)              ← '내가 쓴 기록'만의 요약
   ├─ ② prompts.build_system_prompt()          ← 요약 수치 + 단계별 코칭 가이드를 시스템 프롬프트에 삽입
   ├─ ③ GPT 호출 (tools=7개, max_completion_tokens 제한, 요청 횟수 제한 통과 후)
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

**원리**: GPT는 우리 DB를 모르므로 매 요청마다 "지금 이 사용자의 데이터는 이렇다"는 사실을 시스템 메시지로 넣어 줍니다. 전체 레코드(2,600+건)를 넣으면 토큰이 크게 늘어나므로 **요약만** 넣고, 더 자세한 정보(특정 작품 본문, 기간별 통계, 이전 대화)는 모델이 필요할 때 도구로 가져오게 했습니다.

## 8. (보너스) Function Calling — 어떤 근거로 어떤 도구를 부르나

모든 도구에 필수 인자 `reason`(호출 이유)을 두어 **모델이 스스로 적은 근거**를 응답의 `tool_calls`와 대화 기록에 남기고, 채팅 화면에 칩(⚙)으로 보여줍니다.

| 도구 | 언제 호출하나 (description에 명시한 근거) | 내부 동작 |
|---|---|---|
| `get_data_summary` | 특정 장르·기간·'내 기록만'의 요약이 필요할 때 | `summary_service.get_summary(**filters)` |
| `get_statistics` | 연도/월/연대별 흐름, 다작 작가, 연속 기록을 물을 때 | `summary_service.get_statistics()` |
| `search_works` | 예문·참고 작품·특정 작가의 글·내가 예전에 쓴 글을 찾을 때 | 시계열 기록 + 참고 작품 서재를 함께 검색, 관련도(제목 일치 > 제목 포함 > 지은이 > 본문) 순 + 본문 발췌 |
| `search_books` | 더 읽어 볼 작품·책(시집·소설집·희곡 대본·평론집 등)을 추천할 때 | 공유마당·구텐베르크·번역원·국립중앙도서관·KCISA 참고 자료를 제목·저자·발행처·요약으로 검색 (출처별로 좁히기 가능, 목록 정보와 링크) |
| `read_work` | 사용자가 저장해 둔 자기 글을 퇴고해 달라고 할 때, 참고 작품의 긴 본문이 필요할 때 | 저장된 본문(최대 8,000자)을 읽음 |
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

**배포 서버에 실제로 저장된 호출 기록** (`GET /api/conversations/{id}`의 `messages[].tool_calls`, `reason`은 모델이 직접 쓴 문장):

| 사용자 질문 (단계) | 호출한 도구와 인자 | 모델이 밝힌 근거 (`reason`) |
|---|---|---|
| "내 데이터 요약을 보고 기간, 개수, 평균 글자 수를 알려줘." (자유) | `get_data_summary {}` | 사용자의 전체 글 기록 요약에서 기간, 개수, 평균 글자 수를 확인하기 위해 |
| "…어떤 장르가 많고 추세가 어떤지 알려줘. 그리고 '고향'을 소재로 시를 쓰려는데 참고할 작품 하나와 주제 후보 3개를 추천해줘." (주제 선정, 장르: 시) | ① `get_data_summary {"mine": false}`<br>② `search_works {"keyword": "고향", "genre": "시", "limit": 1}` | ① 사용자 데이터의 장르 분포와 전체 추세를 확인하기 위해<br>② '고향' 소재 시의 참고 작품을 찾기 위해 |
| "아래 글을 퇴고해줘. (원고)" (퇴고) | `analyze_text {"text": "그날 나는 정말 정말 피곤했다. …"}` | 사용자 원고의 문장 길이, 반복어, 접속사 사용을 분석해 퇴고 근거를 마련합니다. |

세 번째 경우, 모델은 측정 결과(문장 4개, 평균 23.0자, 접속사 '그리고' 3회)를 근거로 `원문 → 수정안 (이유)` 형식의 제안 4개를 돌려줬습니다 (스크린샷 `history.png`).

## 9. (보너스) MCP 서버 — 멀티채널 연동

같은 기능을 **MCP 도구**로도 노출합니다. 두 가지 방식을 모두 제공하고, 둘 다 실제 MCP 클라이언트로 검증했습니다.

| 방식 | 주소 / 실행 | 동작 |
|---|---|---|
| **원격 (Streamable HTTP)** | `https://geulbeot-api.onrender.com/mcp` | 배포된 백엔드 안에서 실행 ([`app/mcp_remote.py`](backend/app/mcp_remote.py)). 웹 채팅의 Function Calling 과 **같은 서비스 함수**를 호출. 설치 없이 URL만으로 연결 |
| 로컬 (stdio) | `python backend/mcp_server.py` | 내 PC에서 실행되는 MCP 서버가 배포된 **REST API를 호출** ([`mcp_server.py`](backend/mcp_server.py)) |

```
외부 MCP 클라이언트 (Claude · ChatGPT 커넥터, Claude Code, MCP Inspector …)
   │
   ├─ Streamable HTTP ──▶ Render /mcp ──▶ services.tools / data_service ──▶ Firestore
   │
   └─ stdio ──▶ mcp_server.py ──HTTP──▶ Render /api/* ──▶ Firestore
```

도구: 원격 10개 — `get_data_summary`, `get_statistics`, `search_works`, `search_books`, `read_work`, `list_my_records`, `list_conversations`, `get_conversation`, `analyze_text`, `add_writing_record` / 로컬 stdio 7개 (REST API 에 없는 `search_books`·`read_work`·`analyze_text` 제외)

- 원격 MCP는 **DNS 리바인딩 방어**로 허용된 Host(`MCP_ALLOWED_HOSTS`)만 받고, 무료 서버의 재시작·슬립에 대비해 세션 없이(stateless) 요청마다 처리합니다.
- 연결 예시
  - Claude Code: `claude mcp add --transport http geulbeot https://geulbeot-api.onrender.com/mcp`
  - Claude.ai / ChatGPT: 커넥터(사용자 지정 MCP) 추가에서 위 URL 입력
  - 로컬 stdio: `claude mcp add geulbeot -e GEULBEOT_API_URL=https://geulbeot-api.onrender.com -- python backend/mcp_server.py`

**검증 결과** — [`scripts/mcp_smoke_test.py`](backend/scripts/mcp_smoke_test.py)가 MCP SDK의 `ClientSession`으로 연결해 도구를 호출합니다 (주소가 `/mcp`로 끝나면 원격, 아니면 stdio).

```bash
cd backend
python -m scripts.mcp_smoke_test https://geulbeot-api.onrender.com/mcp   # 원격
python -m scripts.mcp_smoke_test https://geulbeot-api.onrender.com       # 로컬 stdio
```

운영 서버 대상 실행 결과 (2026-09-25):

```text
연결: 원격 Streamable HTTP · https://geulbeot-api.onrender.com/mcp · 서버 이름: geulbeot
도구: get_data_summary, get_statistics, search_works, search_books, read_work, list_my_records, list_conversations, get_conversation, analyze_text, add_writing_record
- get_data_summary({}) → 성공: { "period": "1447-01-01 ~ 2026-09-24", "count": 2614, "metrics": { "total": 18518113, "average": 7084.2, "median": 316.0, "max": 633491, "min": 23, "std": 30867.0 }, "trend": "하락 (최근 30건 평균 7,220자, 직전
- get_statistics({"group": "decade", "genre": "시"}) → 성공: { "group": "decade", "filters": { "genre": "시" }, "series": [ { "period": "1480년대", "count": 3, "total": 534, "average": 178.0 }, { "period": "1890년대", "count": 1, "total": 165, "average": 165.0 }, { 
- search_works({"keyword": "고향", "genre": "시", "limit": 2}) → 성공: { "total": 61, "items": [ { "id": "thVSDAONzlgsKMxqajXV", "date": "1931-11-01", "title": "고향", "author": "박용철", "genre": "시", "value": 207, "source": "위키문헌", "memo": "《고향》 박용철 — 발표 월 기준 · 《박용철 …
- list_conversations({"limit": 3}) → 성공: { "items": [ { "id": "KSfXsBBwpH4mQ1FTf7m7", "title": "내 데이터 요약을 보고 어떤 장르가 많고 추세가 어떤지…", "preview": "좋아요. 먼저 데이터부터 보면, **가장 많은 장르는 시 1423건(평균 329자)**입니다. 그다음은 **수필 298건(평균 3,748자)**", "updated_at": "2

연결: 로컬 stdio · mcp_server.py → https://geulbeot-api.onrender.com · 서버 이름: geulbeot
도구: get_data_summary, get_statistics, search_works, list_my_records, list_conversations, get_conversation, add_writing_record
- get_data_summary({}) → 성공: { "period": "1447-01-01 ~ 2026-09-24", "period_start": "1447-01-01", "period_end": "2026-09-24", "count": 2614, "metrics": { "total": 18518113, "average": 7084.2, "median": 316.0, "max": 633491, "min"
- get_statistics({"group": "decade", "genre": "시"}) → 성공: { "group": "decade", "filters": { "genre": "시" }, "series": [ { "period": "1480년대", "count": 3, "total": 534, "average": 178.0 }, { "period": "1890년대", "count": 1, "total": 165, "average": 165.0 }, { 
- search_works({"keyword": "고향", "genre": "시", "limit": 2}) → 성공: { "date": "1960-11-01", "title": "무제 3", "author": "이상", "genre": "시", "value": 223, "memo": "《무제 3》 이상 — 발표 월 기준 · 〈현대문학〉, 1960.11.", "excerpt": "손가락 같은 여인이 입술로 지문을 찍으며 간다. 불상한 수인은 영원의 낙인을 받고 …
- list_conversations({"limit": 3}) → 성공: { "id": "KSfXsBBwpH4mQ1FTf7m7", "title": "내 데이터 요약을 보고 어떤 장르가 많고 추세가 어떤지…", "message_count": 2, "preview": "좋아요. 먼저 데이터부터 보면, **가장 많은 장르는 시 1423건(평균 329자)**입니다. 그다음은 **수필 298건(평균 3,748자)**", "created_
```

→ 웹 채팅(Function Calling), 원격 MCP, 로컬 MCP 세 채널이 **같은 Firestore 데이터**를 보는 것을 확인했습니다. 원격 `/mcp`는 `tests/test_mcp_remote.py`에서 JSON-RPC 메시지(initialize → tools/list → tools/call)와 허용되지 않은 Host 거부까지 자동 테스트합니다.

## 10. 화면 구성과 디자인

| 경로 | 화면 | 내용 |
|---|---|---|
| `#/` | 홈 | "글쓰기를 위한 AI" 소개 + 채팅 카드만. 채팅 카드 안에 주입된 요약 한 줄, 단계 칩, 장르 선택 |
| `#/history` | 대화 기록 | 저장된 대화 카드 목록 → 불러오기(홈 채팅으로 복원) / 삭제 |
| `#/records` | 기록 관리 | 기록 추가·수정·삭제 폼, 필터·검색·페이지 목록, CSV/JSON 내보내기 |
| `#/insights` | 통계 | **모든 자료 한눈에**(출처별 누적 막대·시기 미상 막대·장르별 누적·출처 표) + 글자 수 요약 타일, 기간별 막대그래프, 장르·작가 분포 |

- 해시 라우팅으로 한 페이지 안에서 화면 전환 (바닐라 JS, 프레임워크 없음)
- 디자인 토큰: 라임 그린 CTA(`#9fe870`) 하나만 강조색으로 사용, 세이지 캔버스(`#e8ebe6`) 위 흰 카드, 올리브 톤 잉크(`#0e0f0c`), 버튼·카드 반경 24px, 입력창 1px 잉크 테두리
- 타이포: 헤드라인 900 / 나머지 600·400. 한글 지원을 위해 Inter 기반 한글 폰트 **Pretendard**를 사용
- 다크 모드: 극성 반전 (잉크 바탕 + 세이지 글자), CTA는 그대로 라임 그린
- 반응형: 1024px 미만은 소개 → 채팅 세로 배치, 768px 미만은 1열 + 단계 칩 가로 스크롤

## 11. (보너스) 인사이트·UX

- **추가 지표**: 중앙값, 표준편차, 가장 긴/짧은 글, 단계별 분포, `/api/data/statistics`의 기간별 시계열·다작 작가·기록 일수·최장 연속 기록
- **통합 통계**: '통계' 탭 맨 위 '모든 자료 한눈에' — 전체·본문 있는 작품·시기 확인·시기 미상 타일, 출처별 색으로 쌓은 연대/세기별 막대(맨 끝 '시기 미상' 막대는 점선으로 구분), 범례를 눌러 출처를 켜고 끄면 세로 눈금 재계산(KCISA 등록 연도가 2010년대에 몰려 있어 끄면 다른 출처의 흐름이 보임), 장르별 누적 막대, 출처별 연도 기준 표
- **시각화**: '통계' 탭의 기간별 막대그래프 (연대/연도/월 × 작품 수/평균 글자 수/총 글자 수, 마우스 오버 툴팁, 표로 보기)
- **내보내기**: 기록 관리 탭에서 현재 필터 기준 CSV(엑셀 한글 호환 BOM) / JSON 다운로드
- **다크 모드**: 우측 상단 토글 (OS 설정을 따르다가, 직접 고르면 브라우저에 기억)
- **선택 UI**: 채팅의 글쓰기 단계 칩(자유/주제 선정/구상·개요/초고/퇴고) + 장르 선택 → 시스템 프롬프트의 코칭 가이드가 바뀜

## 12. 로컬 실행 방법

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

- 위키문헌 데이터를 새로 수집하려면 `python scripts/import_wikisource.py` (요청 제한 때문에 처음에는 1시간 이상, 캐시가 있으면 1분 안팎)
- 공유마당 목록: `python -m scripts.import_gongu fetch` (약 14,000건, 요청 간격 1초 — `fetch 04 --shard 0/3` 처럼 나눠 받을 수 있음) → `python -m scripts.import_gongu build` / 구텐베르크: `python -m scripts.import_gutenberg`
- 참고 도서 목록을 새로 만들려면 `.env`에 `KCISA_API_KEY`를 넣고 `python -m scripts.import_kcisa download` (전체 391쪽, 약 1시간) → `python -m scripts.import_kcisa build` → `python -m scripts.review_duplicates`
- Firebase 키 없이 화면만 확인하려면 `.env`에 `STORAGE_BACKEND=memory` (서버를 재시작하면 데이터가 초기화됨)

### 프론트엔드

```bash
cd frontend/public
python -m http.server 5500        # http://localhost:5500
```

### 테스트

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q                          # 21 passed — Firebase·OpenAI 키 없이 실행됨
```

`public/config.js`의 기본 API 주소는 `http://localhost:8000`입니다.

## 13. 환경 변수

### 백엔드 (Render / `backend/.env`)

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅(배포) | 서비스 계정 키 JSON **전체 문자열** |
| `FIREBASE_CREDENTIALS_PATH` | ✅(로컬) | 또는 키 파일 경로 (`./firebase-key.json`, git 제외) |
| `ALLOWED_ORIGINS` | ✅ | CORS 허용 도메인, 쉼표 구분 (예: `https://geulbeot.vercel.app`) |
| `OPENAI_BASE_URL` | | OpenAI 호환 게이트웨이 주소 (Codyssey: `https://copa.codyssey.kr/v1`). 비우면 OpenAI 공식 API |
| `OPENAI_MODEL` | | 기본 `gpt-5.4-mini` |
| `OPENAI_MAX_TOKENS` | | 답변 1회 최대 토큰, 기본 1200 (과금 방지) |
| `CHAT_RATE_PER_MINUTE` | | IP별 분당 채팅 요청 수, 기본 6 (초과 시 429) |
| `CHAT_DAILY_LIMIT` | | 서버 전체 하루 채팅 요청 수, 기본 300 |
| `MAX_TOOL_ROUNDS` | | 채팅 1회당 도구 호출 반복 상한, 기본 3 |
| `CHAT_HISTORY_LIMIT` | | GPT에 함께 보내는 이전 메시지 수, 기본 10 |
| `STORAGE_BACKEND` | | `firestore`(기본) / `memory`(로컬 확인용) |
| `KCISA_API_KEY` | | (수집 스크립트 전용) 한국문화정보원 서비스 키 — `scripts/import_kcisa.py`에서만 쓰고 배포 서버에는 넣지 않음 |
| `LTI_API_KEY`, `NLK_API_KEY` | | (수집 스크립트 전용) 한국문학번역원 번역출간DB · 국립중앙도서관 Open API 키 — `scripts/import_bib_apis.py` |

### 프론트엔드 (Vercel)

| 이름 | 필수 | 설명 |
|---|---|---|
| `API_BASE_URL` | ✅ | 백엔드 주소 (예: `https://geulbeot-api.onrender.com`). 빌드 때 `build.js`가 `config.js`로 만들어 넣음 |

## 14. 배포

### 백엔드 — Render (`geulbeot-api`, 싱가포르 리전, Free)

1. GitHub 저장소 연결 → **New Web Service** (또는 [`render.yaml`](render.yaml) Blueprint)
2. Build `cd backend && pip install -r requirements.txt` / Start `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` (Blueprint 사용 시 `rootDir: backend`)
3. 환경 변수
   - 일반 값: `PYTHON_VERSION=3.12.8`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `STORAGE_BACKEND=firestore`, `ALLOWED_ORIGINS`
   - **비밀 값은 대시보드에서만 입력**: `OPENAI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`(키 JSON을 한 줄로)
4. 코드를 푸시한 뒤 Render 대시보드의 **Manual Deploy**(또는 Render MCP `trigger_deploy`)로 재배포 → `https://geulbeot-api.onrender.com/docs` 확인 (서비스를 공개 저장소 URL로 만들어서 GitHub 푸시 자동 배포는 꺼져 있음. Render에 GitHub 앱을 연결하면 자동 배포로 바꿀 수 있음)

### 프론트엔드 — Vercel (`geulbeot`)

1. 같은 저장소 Import (Vercel GitHub 앱 설치 필요) → Root Directory `frontend`, Build `node build.js`, Output `public` ([`vercel.json`](frontend/vercel.json))
2. 환경 변수 `API_BASE_URL=https://geulbeot-api.onrender.com` → 빌드 때 `build.js`가 `public/config.js`로 만들어 넣음 (값이 없으면 빌드를 실패시켜 잘못된 배포를 막음)
3. 공개 주소는 프로덕션 도메인 **https://geulbeot-psi.vercel.app** (배포별 주소는 Vercel 배포 보호로 비공개 유지)
4. 이 주소를 Render의 `ALLOWED_ORIGINS`에 추가 → 다른 출처는 CORS 헤더를 받지 못함 (직접 확인: 허용 출처만 `access-control-allow-origin` 응답)

### 왜 CORS·환경 변수·키 관리가 필요한가

- **CORS**: 프론트(`*.vercel.app`)와 백엔드(`*.onrender.com`)는 출처가 다르므로, 브라우저는 백엔드가 허용한 출처의 요청만 응답을 읽게 합니다. `ALLOWED_ORIGINS`에 우리 프론트만 넣어 다른 사이트가 사용자의 브라우저를 통해 API를 쓰지 못하게 합니다.
- **환경 변수**: 로컬·배포 환경마다 다른 값(API 주소, 허용 도메인)을 코드 수정 없이 바꿀 수 있고, 비밀 값을 코드에서 분리합니다.
- **키 관리**: OpenAI 키가 노출되면 타인이 내 비용으로 API를 쓰고, Firebase 서비스 계정 키는 DB 전체 관리자 권한입니다. 그래서 키는 `.env`(git 제외)와 Render 환경 변수에만 두고, 프론트엔드에는 절대 넣지 않습니다(브라우저 코드는 누구나 볼 수 있음). 모든 OpenAI 호출은 백엔드에서만 일어납니다.

### 비용 관리

- **요청 횟수 제한**: `/api/chat`은 IP별 분당 6회, 서버 전체 하루 300회를 넘으면 `429`와 안내 문구를 돌려줌 ([`app/rate_limit.py`](backend/app/rate_limit.py))
- **토큰 제한**: `max_completion_tokens`(기본 1200), 도구 반복 최대 3회, 이전 대화 10개까지만 전송
- **작은 데이터로 먼저 검증**: Firestore에 `seed_firestore --limit 20`으로 20건만 넣고 채팅 2회(요약 질문, 퇴고 요청)로 흐름을 확인한 뒤 `--reset`으로 전체 적재 (현재 data 2,835건 · library 1,039건)
- 전체 데이터 대신 요약만 프롬프트에 넣음
- 요약·검색용 전체 레코드는 서버 메모리에 **6시간** 캐시하고 쓰기는 바뀐 문서만 반영해 Firestore 읽기 횟수 절약 (서버가 깨어날 때마다 약 3,900건을 읽으므로 1시간 캐시로는 하루 5만 회 한도에 닿을 수 있음)
- **한도 초과 대비**: Firestore 읽기가 실패하면 직전 캐시를, 캐시도 없으면 백엔드에 포함된 위키문헌 스냅샷으로 **읽기 전용** 응답을 하고 `/health`의 `degraded: true` + 화면 안내 배너로 알림 (사이트 전체가 503으로 멈추지 않음)
- 참고 자료(공유마당·KCISA 등 3만여 건)는 Firestore 대신 JSON 파일로 두어 무료 한도를 쓰지 않음

## 15. 스크린샷

모두 **배포된 사이트**에서 [`docs/capture_screenshots.py`](docs/capture_screenshots.py)로 실제 흐름을 실행하며 찍었습니다.

**① 데이터 요약이 보이는 채팅 화면 (질문 + 답변)** — 채팅 카드 상단 '요약 주입' 줄이 시스템 프롬프트에 들어가는 요약(기간·개수·평균·합계·추세)이고, 답변 위 ⚙ 칩이 호출한 도구와 근거입니다.

![chat](docs/screenshots/chat.png)

**② 데이터 관리 화면 (추가 동작)** — 본문을 붙여넣어 글자 수 자동 계산 → 저장 → 목록 맨 위에 강조 표시 + 저장 알림

![data](docs/screenshots/data.png)

**③ 대화 기록 화면 (불러오기 동작)** — 대화 기록 목록에서 '불러오기'를 누르면 홈 채팅에 이전 대화(퇴고 대화)가 다시 표시됩니다.

| 대화 기록 목록 | 불러온 대화 |
|---|---|
| ![history list](docs/screenshots/history_list.png) | ![history](docs/screenshots/history.png) |

**보너스·기타**

| 통계·시각화 | 다크 모드 | Swagger UI (배포 URL) |
|---|---|---|
| ![insights](docs/screenshots/insights.png) | ![dark](docs/screenshots/dark.png) | ![swagger](docs/screenshots/swagger.png) |

## 16. 과제 목표별 설명

| # | 과제 목표 | 이 프로젝트에서의 답 | 근거 |
|---|---|---|---|
| 1 | 시계열 분석 → 요약 → 서비스 활용 | 위키문헌 2,834편 + 내 기록을 날짜순으로 정렬해 통계·추세를 계산하고(모든 출처 3만 4천여 건은 통합 통계로 함께 표시), 그 요약을 채팅 프롬프트·요약 패널·통계 탭이 함께 씀 | §2, [`summary_service.py`](backend/app/services/summary_service.py), [`docs/data-analysis.md`](docs/data-analysis.md) |
| 2 | 라우터/서비스 분리 기준 | 라우터 = HTTP 규약(경로·쿼리·상태 코드), 서비스 = 비즈니스 로직, storage = DB. 채팅과 도구가 REST와 같은 서비스 함수를 재사용 | §4 |
| 3 | Pydantic 검증 이유와 방식 | 잘못된 값이 통계·AI 답변을 오염시키지 않도록 요청 단계에서 차단. `Field` 범위, `Literal` 장르/단계, 미래 날짜·공백 검사 validator, PUT 빈 요청 거부 | §5, [`schemas.py`](backend/app/schemas.py) |
| 4 | Firestore 저장과 CRUD | `data`(1건 = 1문서), `conversations`(대화 1개 = 1문서 + messages 배열), add/stream/get/update/delete/batch | §6 |
| 5 | 컨텍스트 주입 원리 | GPT는 DB를 모르므로 매 요청마다 요약을 시스템 메시지에 넣음. 전체 데이터 대신 요약만 넣어 토큰을 아끼고, 세부 정보는 도구로 필요할 때 조회 | §7 |
| 6 | CORS·환경 변수·키 관리 | 출처가 다른 프론트만 허용, 환경별 값 분리, 키는 서버 환경 변수에만 두고 브라우저에 노출하지 않음 | §14 |

## 요구사항 체크리스트

| 요구사항 | 구현 위치 / 확인 방법 |
|---|---|
| Python 3.10+ venv, fastapi·uvicorn·firebase-admin·openai·python-dotenv | [`requirements.txt`](backend/requirements.txt), Render는 Python 3.12.8 |
| 100개 이상 시계열 + 요약 정보 | 2,835건 (전 작품 위키문헌 실존 재조회: [`docs/data-verification.md`](docs/data-verification.md)), `GET /api/data/summary` |
| CORS, `uvicorn main:app --reload`, `/docs` | [`main.py`](backend/main.py) |
| Firestore, 키 환경 변수 관리, `data`·`conversations` 컬렉션 | §6 |
| 데이터 API 5개 (CRUD 4 + summary) | §5 |
| 대화 API 저장·목록·삭제 + (A) 단건 조회 | §5 — 채팅 카드에 "✓ 대화 기록에 저장됨" 표시로 저장 결과 확인 |
| `/api/chat`: 요약 조회 → 프롬프트 삽입 → GPT → 자동 저장 | §7, `tests/test_chat.py` |
| Render 배포, 배포 URL `/docs`, 콜드스타트 대응 | 맨 위 URL 표, `/health` 깨우기 + 안내 배너 + 로딩 문구 변경 |
| 바닐라 프론트: 채팅·로딩, 데이터 관리, 대화 기록, 요약 표시 | [`frontend/public`](frontend/public), §10 화면 구성, §15 스크린샷 |
| Vercel 배포 + `API_BASE_URL` 환경 변수 | [`frontend/build.js`](frontend/build.js), [`vercel.json`](frontend/vercel.json) |
| README: 소개·스택·URL·로컬 실행·환경 변수 | 이 문서 |
| 키를 코드에 노출하지 않음, 입력 검증, 예외 처리 | `.gitignore`, Pydantic, 404/422/429/502/503 처리 |
| 요청 횟수·토큰 제한, 작은 데이터로 먼저 검증 | §14 비용 관리 |
| (보너스) Function Calling + MCP + 호출 근거·흐름 문서화 | §8, §9 — 원격 MCP `/mcp`(배포 URL) + 로컬 stdio, 두 방식 모두 MCP 클라이언트로 검증 |
| (보너스) 추가 지표, 그래프, CSV/JSON 내보내기, 다크 모드 | §11 |

## 17. 트러블슈팅 기록

| 증상 | 원인 | 해결 |
|---|---|---|
| 채팅 답변 뒤 `⚠ Cannot set properties of null (setting 'textContent')` 오류 말풍선 | 새로 추가한 저장 표시(`#save-state`)를 쓰는 **새 JS가 캐시된 옛 HTML 위에서** 실행됨 (탭을 업데이트 전에 열어뒀거나, 캐시 제어가 약한 로컬 정적 서버). 서버는 이미 답변을 만들고 대화도 저장했는데, 화면 갱신 오류를 '전송 실패'로 표시하고 입력을 되돌려 **같은 질문을 다시 보내게** 만드는 설계 결함이 있었음 | ① 서버 요청 오류와 응답 표시 오류를 분리: 응답을 받은 뒤의 화면 오류는 실패로 알리지 않고 입력도 되돌리지 않음 ② 선택적 UI 요소가 없으면 조용히 건너뜀 ③ Vercel 빌드에서 HTML의 CSS·JS 주소와 JS 모듈 import 경로에 배포 버전(`?v=커밋`)을 붙이고 HTML은 `Cache-Control: no-cache` → 옛 HTML과 새 JS가 섞이지 않음 |
| 위키문헌 수집 중 1분마다 `HTTP 429` | 연락처 없는 일반 User-Agent가 엄격하게 제한됨 | 위키미디어 정책대로 User-Agent에 저장소 주소 포함 → 429 0회 |
| KCISA 도서정보 API에 검색 조건을 넣어도 전체 결과가 옴 | 이 API는 `serviceKey`·`numOfRows`·`pageNo` 외 조건을 받지 않음 (39만 건, 한 쪽 응답에 30초 이상) | 전 쪽을 받아 로컬에서 선별. 동시 4개 요청 + 쪽 단위 이어받기(`.part` 임시 파일) |
| 저자 문서로 찾은 작품에 의서(《언해태산집요》)·《태조실록》이 섞이고 장편 《영원의 미소》가 '기타'로 분류 | 저자 문서의 모든 링크를 문학 작품으로 간주 | 링크가 달린 소제목으로 장르를 정하고, 문학 작가 분류·문학 소제목이 모두 없는 저자 문서의 목록은 제외 |
| 장편의 장(「38. 몰래 엿들은 은주의 노래」, 「5」)이 각각 한 작품으로 들어감 | 목차 문서를 장르로만 시집형/연재형으로 나눔 | 하위 문서 이름이 대부분 장 번호 형식이면 연재형으로 합산 |
| 운영 사이트 데이터 API가 모두 `503` (`429 Quota exceeded`) | 하루에 적재·재배포·로컬 테스트를 반복하며 서버가 깰 때마다 전체 문서를 다시 읽어 Firestore 무료 읽기 한도(5만 회)를 소진, 마지막 재적재도 중간에 멈춤 | 읽기 실패 시 캐시 → 포함된 스냅샷으로 읽기 전용 응답(+ 안내 배너), 캐시 6시간, 한도 초기화(태평양 자정) 직후 재적재·재배포 |
| 현진건 「고향」, 김동인 「발가락이 닮았다」, 조명희 「낙동강」 등 대표작 200여 편이 빠짐 | 연도 분류로 먼저 후보가 된 문서는 저자 문서 단계에서 '이미 후보'로 건너뛰어 장르를 받지 못하고 '장르 없음'으로 제외됨 | 장르가 비어 있는 후보도 저자 문서 소제목·문학 작가 여부로 장르 보충, 설명란 문구로 한 번 더 판단 (제외 사유별 제목을 `data/.wikisource_skipped.json`에 남겨 재검토) |
| 공유마당 수필이 '비문학'으로 빠짐 (고유섭 「경인팔경」) | 요약문의 '미술 사학자'라는 말에 비문학 필터가 걸림 | 장르 태그를 우선하고 태그가 없을 때만 요약문으로 판단 |
| Render가 GitHub 푸시로 재배포되지 않음 | 서비스를 공개 저장소 URL로 만들어 GitHub 앱 연결이 없음 | 대시보드 Manual Deploy / Render MCP `trigger_deploy`로 재배포 |

## 18. 데이터 출처 및 라이선스

- 작품 데이터는 [한국어 위키문헌](https://ko.wikisource.org)의 퍼블릭 도메인 저작물(저작권 보호 기간 만료 — 1962년 이전 사망 작가·작자 미상 고전)이며, 각 레코드의 `url`에 원문 링크를 남겼습니다.
- 공유마당 자료는 한국저작권위원회가 '만료저작물(자유이용)'로 공개한 저작물의 목록 정보이며, 원문은 각 항목의 공유마당 링크에서 이용 동의 후 받을 수 있습니다. 구텐베르크 7편은 퍼블릭 도메인(초판 1889~1922, 작가 모두 1945년 이전 사망)입니다.
- 참고 도서 목록은 [한국문화정보원 문화 공공데이터광장](https://www.culture.go.kr/data) 오픈 API(`문화체육관광부 외_기관별 도서정보`)의 서지 정보(제목·저자·발행처·소장 기관·자료 URL)이며 본문은 저장하지 않습니다. 이용 조건은 포털 이용약관을 따르고, 각 도서의 `url`에 소장 기관 자료 링크를 남겼습니다.
