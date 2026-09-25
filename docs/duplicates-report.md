# 중복 검토 보고서

> 자동 생성: `python -m scripts.review_duplicates` · 2026-09-25T02:00:59+00:00

| 구분 | 결과 | 처리 |
|---|---|---|
| 위키문헌 내부 — 같은 작품의 여러 판본 (시계열) | 82편 | 날짜 근거가 가장 정확하고 이른 판본 하나만 남김 |
| 위키문헌 내부 — 서재 중복·날짜 있는 판본과 겹침 | 150편 | 날짜 있는 판본을 남기고, 서재 안에서는 본문이 긴 쪽 하나만 |
| KCISA 내부 — 같은 책의 소장본 여러 권 | 712권 | 한 권으로 합치고 `copies`에 권수 기록 |
| KCISA 내부 — 같은 제목·작가, 발행처가 다른 판본 | 197종 | 서로 다른 판본이라 모두 유지 |
| 위키문헌 ↔ KCISA — 같은 작가·같은 제목 | 50건 | 도서 정보에 위키문헌 원문 링크(`wikisource_url`) 연결 |

## 위키문헌 원문과 연결된 참고 도서 (최대 40건)

| 도서 제목 | 저자 | 소장 기관 | 위키문헌 원문 |
|---|---|---|---|
| 가실 | 이광수 | 한국문학번역원 | [가실](https://ko.wikisource.org/wiki/%EA%B0%80%EC%8B%A4) |
| 경영 | 김남천 | 한국문학번역원 | [경영](https://ko.wikisource.org/wiki/%EA%B2%BD%EC%98%81) |
| 고국 | 최서해 | 한국문학번역원 | [고국](https://ko.wikisource.org/wiki/%EA%B3%A0%EA%B5%AD) |
| 고향 | 현진건 | 한국문학번역원 | [고향](https://ko.wikisource.org/wiki/%EA%B3%A0%ED%96%A5_%28%ED%98%84%EC%A7%84%EA%B1%B4%29) |
| 광화사 | 김동인 | 한국문학번역원 | [광화사](https://ko.wikisource.org/wiki/%EA%B4%91%ED%99%94%EC%82%AC) |
| 규원 | 나혜석 | 한국문학번역원 | [규원](https://ko.wikisource.org/wiki/%EA%B7%9C%EC%9B%90) |
| 금 따는 콩밭 | 김유정 | 한국문학번역원 | [금 따는 콩밭](https://ko.wikisource.org/wiki/%EA%B8%88_%EB%94%B0%EB%8A%94_%EC%BD%A9%EB%B0%AD) |
| 기아와 살육 | 최서해 | 한국문학번역원 | [기아(飢餓)와 살육](https://ko.wikisource.org/wiki/%EA%B8%B0%EC%95%84%EC%99%80_%EC%82%B4%EB%A5%99) |
| 꿈하늘 | 신채호 | 한국문학번역원 | [꿈하늘](https://ko.wikisource.org/wiki/%EA%BF%88%ED%95%98%EB%8A%98) |
| 냉동어 | 채만식 | 한국문학번역원 | [냉동어](https://ko.wikisource.org/wiki/%EB%83%89%EB%8F%99%EC%96%B4) |
| 농촌 사람들 | 조명희 | 한국문학번역원 | [농촌 사람들](https://ko.wikisource.org/wiki/%EB%86%8D%EC%B4%8C_%EC%82%AC%EB%9E%8C%EB%93%A4) |
| 동해 | 이상 | 한국문학번역원 | [동해](https://ko.wikisource.org/wiki/%EB%8F%99%ED%95%B4) |
| 땅 속으로 | 조명희 | 한국문학번역원 | [땅 속으로](https://ko.wikisource.org/wiki/%EB%95%85_%EC%86%8D%EC%9C%BC%EB%A1%9C) |
| 땡볕 | 김유정 | 한국문학번역원 | [땡볕](https://ko.wikisource.org/wiki/%EB%95%A1%EB%B3%95) |
| 만무방 | 김유정 | 한국문학번역원 | [만무방](https://ko.wikisource.org/wiki/%EB%A7%8C%EB%AC%B4%EB%B0%A9) |
| 명문 | 김동인 | 한국문학번역원 | [명문](https://ko.wikisource.org/wiki/%EB%AA%85%EB%AC%B8) |
| 모자 | 강경애 | 한국문학번역원 | [모자](https://ko.wikisource.org/wiki/%EB%AA%A8%EC%9E%90) |
| 물레방아 | 나도향 | 한국문학번역원 | [물레방아](https://ko.wikisource.org/wiki/%EB%AC%BC%EB%A0%88%EB%B0%A9%EC%95%84) |
| 민족의 죄인 | 채만식 | 한국문학번역원 | [민족의 죄인](https://ko.wikisource.org/wiki/%EB%AF%BC%EC%A1%B1%EC%9D%98_%EC%A3%84%EC%9D%B8) |
| 발가락이 닮았다 | 김동인 | 한국문학번역원 | [발가락이 닮았다](https://ko.wikisource.org/wiki/%EB%B0%9C%EA%B0%80%EB%9D%BD%EC%9D%B4_%EB%8B%AE%EC%95%98%EB%8B%A4) |
| 별을 헨다 | 계용묵 | 한국문학번역원 | [별을 헨다](https://ko.wikisource.org/wiki/%EB%B3%84%EC%9D%84_%ED%97%A8%EB%8B%A4) |
| 병풍에 그린 닭이 | 계용묵 | 한국문학번역원 | [병풍(屛風)에 그린 닭이](https://ko.wikisource.org/wiki/%EB%B3%91%ED%92%8D%EC%97%90_%EA%B7%B8%EB%A6%B0_%EB%8B%AD%EC%9D%B4) |
| 분녀 | 이효석 | 한국문학번역원 | [분녀](https://ko.wikisource.org/wiki/%EB%B6%84%EB%85%80) |
| 빈처 | 현진건 | 한국문학번역원 | [빈처](https://ko.wikisource.org/wiki/%EB%B9%88%EC%B2%98) |
| 뽕 | 나도향 | 한국문학번역원 | [뽕](https://ko.wikisource.org/wiki/%EB%BD%95) |
| 석류 | 이효석 | 한국문학번역원 | [석류](https://ko.wikisource.org/wiki/%EC%84%9D%EB%A5%98) |
| 세길로 | 채만식 | 한국문학번역원 | [세 길로](https://ko.wikisource.org/wiki/%EC%84%B8%EA%B8%B8%EB%A1%9C) |
| 소낙비 | 김유정 | 한국문학번역원 | [소낙비](https://ko.wikisource.org/wiki/%EC%86%8C%EB%82%99%EB%B9%84) |
| 쑥국새 | 채만식 | 한국문학번역원 | [쑥국새](https://ko.wikisource.org/wiki/%EC%91%A5%EA%B5%AD%EC%83%88) |
| 여수 | 정인택 | 한국문학번역원 | [여수](https://ko.wikisource.org/wiki/%EC%97%AC%EC%88%98_%28%EC%A0%95%EC%9D%B8%ED%83%9D%29) |
| 유치장에서 만난 사나이 | 김사량 | 한국문학번역원 | [유치장에서 만난 사나이](https://ko.wikisource.org/wiki/%EC%9C%A0%EC%B9%98%EC%9E%A5%EC%97%90%EC%84%9C_%EB%A7%8C%EB%82%9C_%EC%82%AC%EB%82%98%EC%9D%B4) |
| 인두지주 | 계용묵 | 한국문학번역원 | [인두지주](https://ko.wikisource.org/wiki/%EC%9D%B8%EB%91%90%EC%A7%80%EC%A3%BC) |
| 장미 병들다 | 이효석 | 한국문학번역원 | [장미 병들다](https://ko.wikisource.org/wiki/%EC%9E%A5%EB%AF%B8_%EB%B3%91%EB%93%A4%EB%8B%A4) |
| 저기압 | 조명희 | 한국문학번역원 | [저기압](https://ko.wikisource.org/wiki/%EC%A0%80%EA%B8%B0%EC%95%95) |
| 적빈 | 백신애 | 한국문학번역원 | [적빈](https://ko.wikisource.org/wiki/%EC%A0%81%EB%B9%88) |
| 제1과 제1장 | 이무영 | 한국문학번역원 | [제1과 제1장](https://ko.wikisource.org/wiki/%EC%A0%9C1%EA%B3%BC_%EC%A0%9C1%EC%9E%A5) |
| 종생기 | 이상 | 한국문학번역원 | [종생기](https://ko.wikisource.org/wiki/%EC%A2%85%EC%83%9D%EA%B8%B0) |
| 지도의 암실 | 이상 | 한국문학번역원 | [지도의 암실](https://ko.wikisource.org/wiki/%EC%A7%80%EB%8F%84%EC%9D%98_%EC%95%94%EC%8B%A4) |
| 쫓기어가는 이들 | 이익상 | 한국문학번역원 | [쫓기어가는 이들](https://ko.wikisource.org/wiki/%EC%AB%93%EA%B8%B0%EC%96%B4_%EA%B0%80%EB%8A%94_%EC%9D%B4%EB%93%A4) |
| 처를 때리고 | 김남천 | 한국문학번역원 | [처를 때리고](https://ko.wikisource.org/wiki/%EC%B2%98%EB%A5%BC_%EB%95%8C%EB%A6%AC%EA%B3%A0) |
