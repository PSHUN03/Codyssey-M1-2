"""KCISA 기관별 도서정보(API_LIB_051) 원자료에서 문학 자료만 골라 data/kcisa_books.json 을 만든다.

선별 규칙 (제목·자료 묶음 기준, 본문이 없어 제목으로만 판단한다)
  - 한국문학번역원 자료는 모두 문학 작품
  - 음반·영상·공연 프로그램·도면·악보 같은 비문학 형식([CD] [DVD] [VHS] …)은 제외
  - 제목에 문학 형식을 나타내는 말이 있으면 해당 장르로 분류
    ('도시집합주택'처럼 단어 일부가 겹치는 오판을 막으려고 앞뒤 글자를 함께 본다)
  - 같은 책(제목·저자·발행처가 같은 소장본 여러 권)은 하나로 합친다

발행일(ISSUED_DATE)은 대부분 원작 발표일이 아니라 기관의 등록·디지털 발행일이라
시계열로 쓰지 않고 '참고 도서 목록'으로만 쓴다.
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "kcisa_books.json"

NON_LITERARY_FORMATS = {"CD", "DVD", "VHS", "LP", "DVCAM", "공연프로그램", "전시팜플렛", "무대도면", "무대스케치",
                        "스케치", "도면", "악보", "공연리플렛", "리플렛", "포스터", "사진", "비디오", "카세트",
                        "BETACAM", "HDCAM", "Blu-ray", "MP3", "USB", "슬라이드", "필름", "팜플렛", "브로슈어"}

# (정규식, 장르) — 앞에 있는 규칙이 우선
GENRE_RULES = [
    (re.compile(r"공연대본|희곡"), "희곡"),
    (re.compile(r"(?<![도전감])시집(?![가간갈보])|시선집|시전집|동시집|시조집|(?<![가-힣])시\s*$"), "시"),
    (re.compile(r"장편소설|단편소설|소설집|소설선|(?<![가-힣])소설(?![가-힣])|(?<![가-힣])장편(?![가-힣])|단편집"), "소설"),
    (re.compile(r"수필|산문집|산문선|에세이"), "수필"),
    (re.compile(r"동화"), "동화"),
    (re.compile(r"평론|(?<![설])비평"), "평론"),
    (re.compile(r"문학전집|문학선|작품집|작품선|선집|(?<![가-힣])문학(?![가-힣]*(?:관|사$|과지성))"), "기타"),
]


# 평론·수필·동화·기타로 걸린 자료 중 문학이 아닌 예술 분야(음악 평론, 사진집 등)는 뺀다
OTHER_ARTS = re.compile(r"음악|미술|무용|건축|디자인|영화|사진|비주얼|경제|미디어|과학|춤|댄스|발레|오페라|문학행사")


def clean_title(raw: str) -> tuple[str, list[str]]:
    """'제목 [형식] : 부제' → (형식 표시를 뺀 제목, [형식들]). 형식 표시는 제목 중간에 있을 수도 있다."""
    title = re.sub(r"<br\s*/?>", " / ", raw or "").strip()
    formats = [f.strip() for f in re.findall(r"\[([^\]]+)\]", title)]
    title = re.sub(r"\s*\[[^\]]+\]\s*", " ", title).strip()
    return title, formats


def classify(item: dict) -> tuple[str, str, str] | None:
    """문학 자료면 (장르, 제목, 저자) 를, 아니면 None."""
    title, formats = clean_title(item.get("TITLE") or "")
    author = (item.get("AUTHOR") or "").strip()
    if item.get("CNTC_INSTT_NM") == "한국문학번역원":
        # '양건식 - 슬픈 모순 / Yang Geon-sik / Sad Contradiction'
        head = title.split(" / ")[0]
        if " - " in head:
            author, title = [x.strip() for x in head.split(" - ", 1)]
        return "기타", title, author
    for fmt in formats:
        if fmt != "공연대본" and (fmt in NON_LITERARY_FORMATS or any(f in fmt for f in ("CD", "DVD", "VHS", "LP"))):
            return None
    probe = f"{title} {' '.join(formats)}"
    for pattern, genre in GENRE_RULES:
        if pattern.search(probe):
            if genre in ("평론", "수필", "동화", "기타") and OTHER_ARTS.search(probe):
                return None
            return genre, title, author
    return None


def build(items: list[dict]) -> None:
    books: dict[tuple, dict] = {}
    for it in items:
        hit = classify(it)
        if not hit:
            continue
        genre, title, author = hit
        if not title.strip():
            continue  # 제목이 빈 항목은 확인할 수 없어 제외
        publisher = (it.get("PUBLISHER") or "").strip()
        key = (re.sub(r"\s", "", title), author, publisher)
        if key in books:
            books[key]["copies"] += 1
            continue
        issued = (it.get("ISSUED_DATE") or "")[:10].replace(".", "-")
        if re.fullmatch(r"\d{8}", issued):
            issued = f"{issued[:4]}-{issued[4:6]}-{issued[6:]}"
        books[key] = {
            "title": title[:150],
            "author": author[:80] or None,
            "publisher": publisher[:80] or None,
            "genre": genre,
            "issued_date": issued or None,   # 기관 등록·디지털 발행일 (원작 발표일 아님)
            "institution": it.get("CNTC_INSTT_NM"),
            "collection": it.get("CNTC_RESRCE_NM"),
            "url": it.get("URL"),
            "local_id": it.get("LOCAL_ID"),
            "copies": 1,
        }
    rows = sorted(books.values(), key=lambda b: (b["genre"], b["title"]))
    OUT.write_text(json.dumps({
        "source": "한국문화정보원 문화 공공데이터광장 — 문화체육관광부 외_기관별 도서정보 (API_LIB_051)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scanned": len(items),
        "count": len(rows),
        "books": rows,
    }, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"원자료 {len(items):,}건 → 문학 자료 {len(rows):,}건 (중복 소장본 합침) → {OUT}")
    print("장르:", Counter(b["genre"] for b in rows).most_common())
    print("기관·묶음:", Counter((b["institution"], b["collection"]) for b in rows).most_common(10))
