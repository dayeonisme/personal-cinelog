import argparse
import csv
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse


CONTENT_ID_RE = re.compile(r"/contents/([^/?#]+)")
MOVIE_CONTENT_ID_RE = re.compile(r"^m[A-Za-z0-9]+$")
RESERVED_CONTENT_IDS = {"movies", "tv_seasons", "books", "webtoons", "ratings", "wishes", "doings"}
RATING_RE = re.compile(r"(?:Rated\s*)?★\s*([0-5](?:\.[05])?)")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
USER_BASE_RE = re.compile(r"^(https://pedia\.watcha\.com/[^/]+/users/[^/?#]+)")


@dataclass(frozen=True)
class ExportedMovie:
    title: str
    year: str
    rating: Optional[float]
    watcha_content_id: str
    watcha_url: str


def parse_content_id(url: str) -> str:
    match = CONTENT_ID_RE.search(url)
    return match.group(1) if match else ""


def is_movie_content_link(href: str, title: str) -> bool:
    if not title or "watcha.com/contents/" in (href or ""):
        return False
    content_id = parse_content_id(href or "")
    if content_id in RESERVED_CONTENT_IDS:
        return False
    return bool(MOVIE_CONTENT_ID_RE.match(content_id))


def derive_collection_url(profile_url: str, collection: str) -> str:
    base = (profile_url or "").split("?", 1)[0].rstrip("/")
    if base.endswith("/ratings") or base.endswith("/wishes") or base.endswith("/doings"):
        base = base.rsplit("/", 1)[0]
    return f"{base}/{collection}"


def derive_user_base_url(profile_url: str) -> str:
    match = USER_BASE_RE.match((profile_url or "").split("?", 1)[0])
    return match.group(1) if match else profile_url


def normalize_watchapedia_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] == "ko-KR":
        parts[0] = "ko"
    path = "/" + "/".join(parts)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def derive_collection_url_from_current_page(page_url: str, collection: str) -> str:
    normalized = normalize_watchapedia_url(page_url).split("?", 1)[0].rstrip("/")
    if normalized.endswith("/ratings") or normalized.endswith("/wishes") or normalized.endswith("/doings"):
        normalized = normalized.rsplit("/", 1)[0]
    if not normalized.endswith("/contents/movies"):
        normalized = normalized.rstrip("/") + "/contents/movies"
    return f"{normalized}/{collection}"


def parse_rating(text: str) -> Optional[float]:
    match = RATING_RE.search(text or "")
    return float(match.group(1)) if match else None


def parse_year(text: str) -> str:
    match = YEAR_RE.search(text or "")
    return match.group(1) if match else ""


def clean_title(anchor_text: str, card_text: str) -> str:
    title = (anchor_text or "").strip()
    if title:
        return " ".join(title.split())

    lines = [line.strip() for line in (card_text or "").splitlines() if line.strip()]
    for line in lines:
        if "★" not in line and not YEAR_RE.fullmatch(line):
            return " ".join(line.split())
    return ""


def unique_movies(movies: Iterable[ExportedMovie]) -> list:
    seen = set()
    unique = []
    for movie in movies:
        key = movie.watcha_content_id or movie.watcha_url
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(movie)
    return unique


def movie_key(movie: ExportedMovie) -> str:
    return movie.watcha_content_id or movie.watcha_url


def write_ratings_csv(path: Path, rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source",
                "title",
                "year",
                "rating",
                "watcha_content_id",
                "watcha_url",
                "imdb_id",
            ],
        )
        writer.writeheader()
        for row in rows:
            if row.rating is None:
                continue
            writer.writerow(
                {
                    "source": "watchapedia",
                    "title": row.title,
                    "year": row.year,
                    "rating": row.rating,
                    "watcha_content_id": row.watcha_content_id,
                    "watcha_url": row.watcha_url,
                    "imdb_id": "",
                }
            )


def write_watchlist_csv(path: Path, rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source",
                "title",
                "year",
                "watcha_content_id",
                "watcha_url",
                "imdb_id",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source": "watchapedia",
                    "title": row.title,
                    "year": row.year,
                    "watcha_content_id": row.watcha_content_id,
                    "watcha_url": row.watcha_url,
                    "imdb_id": "",
                }
            )


def wait_for_manual_login(page) -> None:
    while is_login_visible(page):
        print("WatchaPedia login appears to be required.")
        print("Log in in the opened Chromium window, wait until the header login button disappears, then press Enter here.")
        input()
        page.wait_for_load_state("networkidle")
        time.sleep(1)

    print("Login check passed.")


def is_login_visible(page) -> bool:
    login_button = page.locator(
        "button[data-select='header-sign-in'], button:has-text('로그인'), button:has-text('Login')"
    )
    for index in range(login_button.count()):
        if login_button.nth(index).is_visible():
            return True
    return False


# ── 자동 로그인 (cron/headless 대비) ──────────────────────────────────────────
# main() 에서 채운다. 쿠키 세션(.watchapedia-browser)을 항상 우선하고,
# 만료됐을 때만 저장된 자격증명으로 1회 로그인 시도한다.
_HEADLESS = False
_EMAIL = None
_PASSWORD = None

# 왓챠 DOM 변경/언어 차이에 대비한 다중 fallback 셀렉터
_EMAIL_SELECTORS = (
    "input[name='email']",
    "input[type='email']",
    "input[placeholder*='이메일']",
    "input[placeholder*='Email']",
    "input[autocomplete='username']",
)
_PASSWORD_SELECTORS = (
    "input[name='password']",
    "input[type='password']",
    "input[placeholder*='비밀번호']",
    "input[placeholder*='Password']",
    "input[autocomplete='current-password']",
)
_SUBMIT_SELECTORS = (
    "button[data-select='sign-in']",
    "form button[type='submit']",
    "button[type='submit']",
    "button:has-text('로그인')",
    "button:has-text('Sign in')",
)


def _first_visible(page, selectors):
    for sel in selectors:
        loc = page.locator(sel)
        for i in range(min(loc.count(), 5)):
            cand = loc.nth(i)
            try:
                if cand.is_visible():
                    return cand
            except Exception:
                continue
    return None


def attempt_login(page, email: str, password: str) -> bool:
    """저장된 이메일/비번으로 자동 로그인 시도. 성공 여부 반환. CAPTCHA/2FA 면 실패."""
    opener = _first_visible(
        page,
        (
            "button[data-select='header-sign-in']",
            "button:has-text('로그인')",
            "button:has-text('Login')",
        ),
    )
    if opener is not None:
        try:
            opener.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
        except Exception:
            pass

    email_input = _first_visible(page, _EMAIL_SELECTORS)
    password_input = _first_visible(page, _PASSWORD_SELECTORS)
    if email_input is None or password_input is None:
        print("auto-login: 로그인 입력칸을 못 찾음 (DOM 변경 또는 CAPTCHA 가능).")
        return False
    try:
        email_input.fill(email)
        password_input.fill(password)
    except Exception as exc:
        print(f"auto-login: 입력 실패 {exc}")
        return False

    submit = _first_visible(page, _SUBMIT_SELECTORS)
    try:
        if submit is not None:
            submit.click()
        else:
            password_input.press("Enter")
    except Exception as exc:
        print(f"auto-login: 제출 실패 {exc}")
        return False

    page.wait_for_load_state("networkidle")
    time.sleep(2)
    return not is_login_visible(page)


def ensure_logged_in(page) -> None:
    """쿠키 세션 우선 → 만료 시 자동 로그인 → 그래도 안 되면 cron/headless 에선 즉시 실패(무한대기 금지)."""
    if not is_login_visible(page):
        return  # 쿠키 세션 유효 (정상 경로)

    if _EMAIL and _PASSWORD:
        print("세션 만료 감지 — 저장된 자격증명으로 자동 로그인 시도...")
        if attempt_login(page, _EMAIL, _PASSWORD):
            print("자동 로그인 성공.")
            return
        print("자동 로그인 실패 (CAPTCHA/2FA/셀렉터 변경 가능).")

    if _HEADLESS or not sys.stdin.isatty():
        raise SystemExit(
            "WATCHA_LOGIN_REQUIRED: 세션 만료 + 자동 로그인 불가. "
            "Mac 에서 한 번 재로그인 후 .watchapedia-browser 프로필을 VM 으로 재동기화하세요."
        )

    wait_for_manual_login(page)  # 대화형(사람 있음) — 기존 수동 로그인


def collect_scrolling_movies(page, pause_seconds: float, stable_rounds: int) -> list:
    collected = {}
    stable_count = 0
    round_number = 0

    while stable_count < stable_rounds:
        round_number += 1
        before_count = len(collected)
        for movie in extract_visible_movies(page):
            collected[movie_key(movie)] = movie

        after_count = len(collected)
        new_count = after_count - before_count
        print(f"Scroll round {round_number}: +{new_count}, total {after_count}")

        if new_count == 0:
            stable_count += 1
        else:
            stable_count = 0

        # 마지막 카드를 화면에 보이게 스크롤 → 실제 스크롤 컨테이너(내부 div든 window든)를
        # 끝까지 밀어 다음 배치 로드를 트리거한다. window.scrollBy 는 내부 컨테이너를 못 밀 수 있음.
        anchors = page.locator("a[title][href*='/contents/']")
        anchor_total = anchors.count()
        if anchor_total:
            try:
                last = anchors.nth(anchor_total - 1)
                last.scroll_into_view_if_needed(timeout=3000)
                # 마지막 카드 바로 아래로 한 번 더 밀어 lazy-load 트리거
                last.hover(timeout=1000)
                page.mouse.wheel(0, 2500)
            except Exception:
                pass
        time.sleep(pause_seconds)

    return list(collected.values())


_EXTRACT_JS = """() => {
  const out = [];
  for (const a of document.querySelectorAll("a[title][href*='/contents/']")) {
    const card = a.closest('li, article, div');
    out.push({
      href: a.getAttribute('href') || '',
      title: a.getAttribute('title') || '',
      anchorText: (a.innerText || '').trim(),
      cardText: card ? (card.innerText || '').trim() : '',
    });
  }
  return out;
}"""


def extract_visible_movies(page) -> list:
    # 카드마다 Playwright 왕복(느림/타임아웃) 대신 page.evaluate 한 번으로 전 카드 데이터 수집.
    try:
        cards = page.evaluate(_EXTRACT_JS)
    except Exception:
        return []

    movies = []
    for c in cards:
        href = c.get("href") or ""
        anchor_title = c.get("title") or ""
        if not is_movie_content_link(href, anchor_title):
            continue

        watcha_url = urljoin(page.url, href)
        watcha_content_id = parse_content_id(watcha_url)

        anchor_text = anchor_title or c.get("anchorText") or ""
        card_text = c.get("cardText") or ""
        title = clean_title(anchor_text, card_text)
        if not title:
            continue

        movies.append(
            ExportedMovie(
                title=title,
                year=parse_year(card_text),
                rating=parse_rating(card_text),
                watcha_content_id=watcha_content_id,
                watcha_url=watcha_url,
            )
        )
    return unique_movies(movies)


def click_first_visible_link(page, href_part: str, label: str) -> bool:
    links = page.locator(f"a[href*='{href_part}']")
    for index in range(links.count()):
        link = links.nth(index)
        if link.is_visible():
            print(f"Clicking {label}: {link.get_attribute('href')}")
            link.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            return True
    return False


def click_visible_text(page, labels: list, label: str) -> bool:
    for text in labels:
        locator = page.get_by_text(text, exact=True)
        for index in range(locator.count()):
            candidate = locator.nth(index)
            if candidate.is_visible():
                print(f"Clicking {label} by text: {text}")
                candidate.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                return True
    return False


def collect_profile_collection(
    page,
    profile_url: str,
    collection: str,
    pause_seconds: float,
    stable_rounds: int,
) -> list:
    user_base_url = derive_user_base_url(profile_url)
    print(f"Opening profile {user_base_url}")
    page.goto(user_base_url, wait_until="domcontentloaded")
    ensure_logged_in(page)
    page.wait_for_load_state("networkidle")

    if not click_first_visible_link(page, "/contents/movies", "archive movie tab"):
        print("Movie archive link was not visible; opening profile movie URL directly.")
        page.goto(normalize_watchapedia_url(profile_url), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
    print(f"Movie archive page: {page.url}")

    collection_href = f"/contents/movies/{collection}"
    clicked_collection = click_first_visible_link(page, collection_href, collection)
    if not clicked_collection and collection == "ratings":
        clicked_collection = click_visible_text(page, ["더보기", "More"], collection)
    if not clicked_collection and collection == "wishes":
        clicked_collection = click_visible_text(page, ["보고싶어요", "WatchList", "Watchlist"], collection)
    if not clicked_collection:
        collection_url = derive_collection_url_from_current_page(page.url, collection)
        print(f"{collection} link was not visible; opening collection URL directly: {collection_url}")
        page.goto(collection_url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

    rows = collect_scrolling_movies(page, pause_seconds=pause_seconds, stable_rounds=stable_rounds)
    print(f"Collected {len(rows)} rows from {page.url}")
    return rows


def _capture_frograms_headers(page, kind: str, collection_url: str) -> dict:
    """페이지를 한 번 열어 앱이 보내는 API 요청의 x-frograms-* / accept 헤더를 캡처한다.
    device-identifier 등이 세션에 묶여 있으므로 하드코딩 대신 런타임 캡처가 안전하다."""
    captured: dict = {}

    def on_req(req):
        u = req.url
        if "/api/users/" in u and f"/{kind}" in u and not captured:
            for k, v in req.headers.items():
                lk = k.lower()
                if lk.startswith("x-frograms") or lk == "accept":
                    captured[k] = v

    page.on("request", on_req)
    page.goto(normalize_watchapedia_url(collection_url), wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    try:
        page.remove_listener("request", on_req)
    except Exception:
        pass
    return captured


def collect_via_api(page, collection_url: str) -> list:
    """Watcha 내부 API(next_uri 페이징)로 전량 수집. 스크롤보다 완전·안정."""
    m = re.search(r"/users/([^/?#]+)/contents/movies/(ratings|wishes|doings)", collection_url)
    if not m:
        return []
    uid, kind = m.group(1), m.group(2)

    headers = _capture_frograms_headers(page, kind, collection_url)
    ensure_logged_in(page)  # 세션 만료면 여기서 fail-fast(헤드리스/cron)
    if not headers:
        print("API 헤더 캡처 실패 — 스크롤로 폴백")
        return []

    base = "https://pedia.watcha.com"
    uri = f"/api/users/{uid}/contents/movies/{kind}?size=100&order=recent"
    raw = []
    while uri:
        resp = page.request.get(base + uri, headers=headers)
        if resp.status != 200:
            print(f"API {kind} status {resp.status} — 중단(수집 {len(raw)})")
            break
        result = (resp.json() or {}).get("result") or {}
        raw.extend(result.get("result") or [])
        uri = result.get("next_uri")

    movies = []
    for it in raw:
        c = it.get("content") or {}
        if c.get("content_type") not in (None, "movies"):
            continue
        code = c.get("code") or ""
        if not code:
            continue
        rating = (it.get("user_content_action") or {}).get("rating")
        movies.append(
            ExportedMovie(
                title=(c.get("title") or "").strip(),
                year=str(c.get("year")) if c.get("year") else "",
                rating=(rating / 2.0) if isinstance(rating, (int, float)) else None,
                watcha_content_id=code,
                watcha_url=f"https://pedia.watcha.com/ko/contents/{code}",
            )
        )
    return unique_movies(movies)


def collect_page_movies(page, url: str, pause_seconds: float, stable_rounds: int) -> list:
    print(f"Opening {url}")
    # API 우선(완전·안정). 실패 시에만 스크롤 폴백.
    try:
        movies = collect_via_api(page, url)
        if movies:
            print(f"API 수집: {len(movies)} rows from {url}")
            return movies
        print("API 결과 없음 — 스크롤 폴백")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"API 수집 예외({exc}) — 스크롤 폴백")
    page.goto(url, wait_until="domcontentloaded")
    ensure_logged_in(page)
    page.wait_for_load_state("networkidle")
    return collect_scrolling_movies(page, pause_seconds=pause_seconds, stable_rounds=stable_rounds)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export your own WatchaPedia movie ratings/watchlist to CSV."
    )
    parser.add_argument("--profile-url", help="Fallback WatchaPedia movie profile URL.")
    parser.add_argument("--ratings-url", help="WatchaPedia URL for rated movies.")
    parser.add_argument("--watchlist-url", help="WatchaPedia URL for watchlist movies.")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    # 추출이 빨라져 다음 배치 로딩 전에 조기 종료되지 않도록 인내심을 키운다.
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    parser.add_argument("--stable-rounds", type=int, default=10)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="브라우저 창 없이 실행 (cron/서버용).",
    )
    parser.add_argument(
        "--storage-state",
        help="portable 세션 JSON 경로(쿠키 평문). 있으면 프로필 대신 이걸로 로그인 상태를 이식(OS 무관).",
    )
    args = parser.parse_args()

    if not (args.profile_url or args.ratings_url or args.watchlist_url):
        parser.error("provide --profile-url, --ratings-url, or --watchlist-url")

    global _HEADLESS, _EMAIL, _PASSWORD
    _HEADLESS = args.headless
    _EMAIL = os.environ.get("WATCHA_EMAIL")
    _PASSWORD = os.environ.get("WATCHA_PASSWORD")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        if args.storage_state and Path(args.storage_state).exists():
            # 포터블 세션 JSON (Mac→VM OS 무관). 쿠키 주입 → 로그인 상태 이식.
            browser = playwright.chromium.launch(headless=args.headless)
            context = browser.new_context(
                storage_state=str(args.storage_state),
                viewport={"width": 1440, "height": 1000},
            )
        else:
            context = playwright.chromium.launch_persistent_context(
                ".watchapedia-browser",
                headless=args.headless,
                viewport={"width": 1440, "height": 1000},
            )
        page = context.new_page()

        ratings_rows = []
        watchlist_rows = []

        if args.ratings_url:
            ratings_rows = [
                row
                for row in collect_page_movies(
                    page, args.ratings_url, args.pause_seconds, args.stable_rounds
                )
                if row.rating is not None
            ]

        if args.watchlist_url:
            watchlist_rows = collect_page_movies(
                page, args.watchlist_url, args.pause_seconds, args.stable_rounds
            )

        if args.profile_url:
            if not ratings_rows:
                ratings_rows = [
                    row
                    for row in collect_profile_collection(
                        page,
                        args.profile_url,
                        "ratings",
                        args.pause_seconds,
                        args.stable_rounds,
                    )
                    if row.rating is not None
                ]
            if not watchlist_rows:
                watchlist_rows = collect_profile_collection(
                    page,
                    args.profile_url,
                    "wishes",
                    args.pause_seconds,
                    args.stable_rounds,
                )

        context.close()

    ratings_path = args.out_dir / "watchapedia_ratings.csv"
    watchlist_path = args.out_dir / "watchapedia_watchlist.csv"
    write_ratings_csv(ratings_path, ratings_rows)
    write_watchlist_csv(watchlist_path, watchlist_rows)

    print(f"Wrote {len(ratings_rows)} ratings to {ratings_path}")
    print(f"Wrote {len(watchlist_rows)} watchlist rows to {watchlist_path}")


if __name__ == "__main__":
    main()
