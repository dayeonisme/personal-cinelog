#!/usr/bin/env python3
"""Mac 에서 실행: 로그인된 .watchapedia-browser 프로필의 세션을 portable JSON 으로 추출.

Chromium 쿠키는 OS 키체인으로 암호화돼 프로필 디렉터리를 그대로 복사하면 다른 OS 에서
복호화되지 않는다. storage_state 는 쿠키를 평문 JSON 으로 내보내므로 Mac→VM 이식이 된다.

사용:
    python tools/dump_watcha_state.py            # watcha_state.json 생성
    python tools/dump_watcha_state.py out.json   # 경로 지정

생성된 JSON 을 VM 의 ~/movie-review/ 로 복사하면 끝(쿠키 만료 시마다 재추출).
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("watcha_state.json")
PROFILE = ".watchapedia-browser"
CHECK_URL = "https://pedia.watcha.com/ko-KR"


def _login_visible(page) -> bool:
    btn = page.locator(
        "button[data-select='header-sign-in'], button:has-text('로그인'), button:has-text('Login')"
    )
    return any(btn.nth(i).is_visible() for i in range(btn.count()))


def main() -> None:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, headless=False, viewport={"width": 1440, "height": 1000}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(CHECK_URL, wait_until="domcontentloaded")
        time.sleep(2)

        if _login_visible(page):
            print("로그인이 안 돼 있습니다. 열린 창에서 왓챠 로그인 후 이 터미널에서 Enter.")
            input()
            page.wait_for_load_state("networkidle")

        ctx.storage_state(path=str(OUT))
        ctx.close()
    print(f"세션 저장 완료: {OUT.resolve()}")
    print("이 파일을 VM ~/movie-review/ 로 복사하세요. (쿠키 평문 포함 — 외부 공유 금지)")


if __name__ == "__main__":
    main()
