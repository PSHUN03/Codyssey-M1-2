# 중복 검토 보고서

> 자동 생성: `python -m scripts.review_duplicates` · 2026-09-24T16:19:18+00:00

| 구분 | 결과 | 처리 |
|---|---|---|
| 위키문헌 내부 — 같은 작품의 여러 판본 (시계열) | 82편 | 날짜 근거가 가장 정확하고 이른 판본 하나만 남김 |
| 위키문헌 내부 — 서재 중복·날짜 있는 판본과 겹침 | 150편 | 날짜 있는 판본을 남기고, 서재 안에서는 본문이 긴 쪽 하나만 |
| KCISA 내부 — 같은 책의 소장본 여러 권 | 712권 | 한 권으로 합치고 `copies`에 권수 기록 |
| KCISA 내부 — 같은 제목·작가, 발행처가 다른 판본 | 197종 | 서로 다른 판본이라 모두 유지 |
| 위키문헌 ↔ KCISA — 같은 작가·같은 제목 | 38건 | 도서 정보에 위키문헌 원문 링크(`wikisource_url`) 연결 |

## 위키문헌 원문과 연결된 참고 도서 (최대 40건)

| 도서 제목 | 저자 | 소장 기관 | 위키문헌 원문 |
|---|---|---|---|
| 광화사 | 김동인 | 한국문학번역원 | [광화사](https://ko.wikisource.org/wiki/%EA%B4%91%ED%99%94%EC%82%AC) |
| 규원 | 나혜석 | 한국문학번역원 | [규원](https://ko.wikisource.org/wiki/%EA%B7%9C%EC%9B%90) |
| 금 따는 콩밭 | 김유정 | 한국문학번역원 | [금 따는 콩밭](https://ko.wikisource.org/wiki/%EA%B8%88_%EB%94%B0%EB%8A%94_%EC%BD%A9%EB%B0%AD) |
| 꿈하늘 | 신채호 | 한국문학번역원 | [꿈하늘](https://ko.wikisource.org/wiki/%EA%BF%88%ED%95%98%EB%8A%98) |
| 냉동어 | 채만식 | 한국문학번역원 | [냉동어](https://ko.wikisource.org/wiki/%EB%83%89%EB%8F%99%EC%96%B4) |
| 동해 | 이상 | 한국문학번역원 | [동해](https://ko.wikisource.org/wiki/%EB%8F%99%ED%95%B4) |
| 땡볕 | 김유정 | 한국문학번역원 | [땡볕](https://ko.wikisource.org/wiki/%EB%95%A1%EB%B3%95) |
| 만무방 | 김유정 | 한국문학번역원 | [만무방](https://ko.wikisource.org/wiki/%EB%A7%8C%EB%AC%B4%EB%B0%A9) |
| 명문 | 김동인 | 한국문학번역원 | [명문](https://ko.wikisource.org/wiki/%EB%AA%85%EB%AC%B8) |
| 모자 | 강경애 | 한국문학번역원 | [모자](https://ko.wikisource.org/wiki/%EB%AA%A8%EC%9E%90) |
| 물레방아 | 나도향 | 한국문학번역원 | [물레방아](https://ko.wikisource.org/wiki/%EB%AC%BC%EB%A0%88%EB%B0%A9%EC%95%84) |
| 민족의 죄인 | 채만식 | 한국문학번역원 | [민족의 죄인](https://ko.wikisource.org/wiki/%EB%AF%BC%EC%A1%B1%EC%9D%98_%EC%A3%84%EC%9D%B8) |
| 별을 헨다 | 계용묵 | 한국문학번역원 | [별을 헨다](https://ko.wikisource.org/wiki/%EB%B3%84%EC%9D%84_%ED%97%A8%EB%8B%A4) |
| 병풍에 그린 닭이 | 계용묵 | 한국문학번역원 | [병풍(屛風)에 그린 닭이](https://ko.wikisource.org/wiki/%EB%B3%91%ED%92%8D%EC%97%90_%EA%B7%B8%EB%A6%B0_%EB%8B%AD%EC%9D%B4) |
| 분녀 | 이효석 | 한국문학번역원 | [분녀](https://ko.wikisource.org/wiki/%EB%B6%84%EB%85%80) |
| 빈처 | 현진건 | 한국문학번역원 | [빈처](https://ko.wikisource.org/wiki/%EB%B9%88%EC%B2%98) |
| 석류 | 이효석 | 한국문학번역원 | [석류](https://ko.wikisource.org/wiki/%EC%84%9D%EB%A5%98) |
| 세길로 | 채만식 | 한국문학번역원 | [세 길로](https://ko.wikisource.org/wiki/%EC%84%B8%EA%B8%B8%EB%A1%9C) |
| 소낙비 | 김유정 | 한국문학번역원 | [소낙비](https://ko.wikisource.org/wiki/%EC%86%8C%EB%82%99%EB%B9%84) |
| 쑥국새 | 채만식 | 한국문학번역원 | [쑥국새](https://ko.wikisource.org/wiki/%EC%91%A5%EA%B5%AD%EC%83%88) |
| 유치장에서 만난 사나이 | 김사량 | 한국문학번역원 | [유치장에서 만난 사나이](https://ko.wikisource.org/wiki/%EC%9C%A0%EC%B9%98%EC%9E%A5%EC%97%90%EC%84%9C_%EB%A7%8C%EB%82%9C_%EC%82%AC%EB%82%98%EC%9D%B4) |
| 장미 병들다 | 이효석 | 한국문학번역원 | [장미 병들다](https://ko.wikisource.org/wiki/%EC%9E%A5%EB%AF%B8_%EB%B3%91%EB%93%A4%EB%8B%A4) |
| 적빈 | 백신애 | 한국문학번역원 | [적빈](https://ko.wikisource.org/wiki/%EC%A0%81%EB%B9%88) |
| 제1과 제1장 | 이무영 | 한국문학번역원 | [제1과 제1장](https://ko.wikisource.org/wiki/%EC%A0%9C1%EA%B3%BC_%EC%A0%9C1%EC%9E%A5) |
| 종생기 | 이상 | 한국문학번역원 | [종생기](https://ko.wikisource.org/wiki/%EC%A2%85%EC%83%9D%EA%B8%B0) |
| 지도의 암실 | 이상 | 한국문학번역원 | [지도의 암실](https://ko.wikisource.org/wiki/%EC%A7%80%EB%8F%84%EC%9D%98_%EC%95%94%EC%8B%A4) |
| 쫓기어가는 이들 | 이익상 | 한국문학번역원 | [쫓기어가는 이들](https://ko.wikisource.org/wiki/%EC%AB%93%EA%B8%B0%EC%96%B4_%EA%B0%80%EB%8A%94_%EC%9D%B4%EB%93%A4) |
| 처를 때리고 | 김남천 | 한국문학번역원 | [처를 때리고](https://ko.wikisource.org/wiki/%EC%B2%98%EB%A5%BC_%EB%95%8C%EB%A6%AC%EA%B3%A0) |
| 태형 | 김동인 | 한국문학번역원 | [태형](https://ko.wikisource.org/wiki/%ED%83%9C%ED%98%95) |
| 파금 | 강경애 | 한국문학번역원 | [파금](https://ko.wikisource.org/wiki/%ED%8C%8C%EA%B8%88) |
| 하얼빈 | 이효석 | 한국문학번역원 | [하얼빈](https://ko.wikisource.org/wiki/%ED%95%98%EC%96%BC%EB%B9%88) |
| 흙의 세례 | 이익상 | 한국문학번역원 | [흙의 세례](https://ko.wikisource.org/wiki/%ED%9D%99%EC%9D%98_%EC%84%B8%EB%A1%80) |
| 규한 | 이광수 | 한국문화예술위원회 | [규한](https://ko.wikisource.org/wiki/%EA%B7%9C%ED%95%9C) |
| 병자삼인 | 조중환 | 한국문화예술위원회 | [병자삼인](https://ko.wikisource.org/wiki/%EB%B3%91%EC%9E%90%EC%82%BC%EC%9D%B8) |
| 사랑의 기적 | 박용철 | 한국문화예술위원회 | [사랑의 기적](https://ko.wikisource.org/wiki/%EB%B0%95%EC%9A%A9%EC%B2%A0_%EC%82%B0%EB%AC%B8%EC%A7%91/%EC%82%AC%EB%9E%91%EC%9D%98_%EA%B8%B0%EC%A0%81) |
| 제석(除夕) | 홍사용 | 한국문화예술위원회 | [제석](https://ko.wikisource.org/wiki/%EC%A0%9C%EC%84%9D) |
| 출가(出家) | 홍사용 | 한국문화예술위원회 | [출가](https://ko.wikisource.org/wiki/%EC%B6%9C%EA%B0%80) |
| 할미꽃 | 홍사용 | 한국문화예술위원회 | [할미꽃](https://ko.wikisource.org/wiki/%ED%95%A0%EB%AF%B8%EA%BD%83) |
