import argparse
import csv
import re
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

        page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 0.85))")
        page.mouse.wheel(0, 1800)
        time.sleep(pause_seconds)

    return list(collected.values())


def extract_visible_movies(page) -> list:
    anchors = page.locator("a[title][href*='/contents/']")
    movies = []
    for index in range(anchors.count()):
        anchor = anchors.nth(index)
        href = anchor.get_attribute("href") or ""
        anchor_title = anchor.get_attribute("title") or ""
        if not is_movie_content_link(href, anchor_title):
            continue

        watcha_url = urljoin(page.url, href)
        watcha_content_id = parse_content_id(watcha_url)

        anchor_text = anchor_title or anchor.inner_text(timeout=1000)
        card_text = anchor.locator("xpath=ancestor::*[self::li or self::article or self::div][1]").inner_text(timeout=1000)
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
    wait_for_manual_login(page)
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


def collect_page_movies(page, url: str, pause_seconds: float, stable_rounds: int) -> list:
    print(f"Opening {url}")
    page.goto(url, wait_until="domcontentloaded")
    wait_for_manual_login(page)
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
    parser.add_argument("--pause-seconds", type=float, default=1.25)
    parser.add_argument("--stable-rounds", type=int, default=3)
    args = parser.parse_args()

    if not (args.profile_url or args.ratings_url or args.watchlist_url):
        parser.error("provide --profile-url, --ratings-url, or --watchlist-url")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            ".watchapedia-browser",
            headless=False,
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
