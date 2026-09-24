"""제출용 스크린샷 자동 캡처 (Playwright + 설치된 Edge).

    python docs/capture_screenshots.py <프론트 URL> <백엔드 URL>
    예) python docs/capture_screenshots.py http://localhost:5500 http://localhost:8000

실제 흐름을 그대로 실행한다: AI 질문 → 답변, 기록 추가, 대화 불러오기, 통계, 다크 모드, Swagger.
(AI 호출 1회, 기록 1건 추가가 실제로 일어난다)
"""

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONT = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5500").rstrip("/")
BACK = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True)

QUESTION = "내 데이터 요약을 보고 어떤 장르가 많고 추세가 어떤지 알려줘. 그리고 '고향'을 소재로 시를 쓰려는데 참고할 작품 하나와 주제 후보 3개를 추천해줘."


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("saved", name)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, color_scheme="light",
                              locale="ko-KR")
    page = ctx.new_page()
    page.goto(FRONT, wait_until="networkidle")
    page.wait_for_selector("#server-status[data-state='ok']", timeout=120_000)
    page.wait_for_selector(".sum-grid", timeout=60_000)

    # 1) 데이터 요약이 보이는 채팅 화면 (질문 + 답변)
    page.click(".chip[data-stage='주제 선정']")
    page.select_option("#chat-genre", "시")
    page.fill("#chat-input", QUESTION)
    page.click("#send-btn")
    page.wait_for_selector(".msg.loading", timeout=10_000)
    page.wait_for_selector(".msg.assistant:not(.loading) .bubble", timeout=120_000)
    page.wait_for_timeout(800)
    page.evaluate("document.querySelector('#messages').scrollTop = 0")
    shot(page, "chat")

    # 2) 데이터 관리 화면 (추가 동작) — 이전 캡처 때 만든 데모 기록은 먼저 지운다
    listed = json.loads(urllib.request.urlopen(f"{BACK}/api/data?q=%EA%B0%80%EC%9D%84%20%EC%82%B0%EC%B1%85&mine=true").read())
    for item in listed["items"]:
        urllib.request.urlopen(urllib.request.Request(f"{BACK}/api/data/{item['id']}", method="DELETE"))
    page.click(".tab[data-view='data']")
    page.wait_for_selector("#data-rows tr td.cell-date")
    page.fill("#data-form input[name='title']", "가을 산책")
    page.select_option("#data-form select[name='genre']", "수필")
    page.select_option("#data-form select[name='stage']", "초고")
    page.fill("#data-form textarea[name='memo']", "산책하며 떠올린 장면으로 초고 시작. 도입이 길어서 다음엔 절반으로 줄일 예정.")
    page.click(".counter summary")
    page.fill("#count-source", "낙엽 밟히는 소리가 좋아서 일부러 멀리 돌아서 걸었다. 바람은 차가웠지만 마음은 이상하게 따뜻했다. " * 12)
    page.click("#form-submit")
    page.wait_for_selector("#toast:not([hidden])")
    page.wait_for_selector("#data-rows tr.flash", timeout=60_000)
    page.wait_for_timeout(300)
    shot(page, "data")

    # 3) 대화 기록 화면 (새로고침 → 목록에서 불러오기)
    page.goto(FRONT, wait_until="networkidle")
    page.wait_for_selector("#server-status[data-state='ok']", timeout=120_000)
    page.wait_for_selector(".conv-item")
    items = page.locator(".conv-item")
    items.nth(1 if items.count() > 1 else 0).click()  # 방금 대화가 아닌 이전 대화를 불러온다
    page.wait_for_selector("#messages .msg.assistant")
    page.wait_for_timeout(500)
    page.evaluate("document.querySelector('#messages').scrollTop = 0")
    shot(page, "history")

    # 4) 통계 + 그래프
    page.click(".tab[data-view='insights']")
    page.wait_for_selector("#chart svg")
    page.select_option("#i-group", "decade")
    page.wait_for_timeout(1200)
    shot(page, "insights")

    # 5) 다크 모드
    page.click("#theme-toggle")
    page.click(".tab[data-view='chat']")
    page.wait_for_timeout(500)
    shot(page, "dark")
    page.click("#theme-toggle")

    # 6) Swagger UI
    page.goto(f"{BACK}/docs", wait_until="networkidle")
    page.wait_for_selector(".opblock", timeout=60_000)
    shot(page, "swagger")
    browser.close()
