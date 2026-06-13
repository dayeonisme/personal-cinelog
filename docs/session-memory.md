# Session Memory

## Current App Decisions
- Movie registration starts from the home `+` button. The user chooses `평가` or `보고싶어요` after movie search.
- GNB has no separate home button; clicking the `Cinelog` title navigates home.
- Movie detail order is `보고싶어요 정보` first, then `평가 정보`.
- If a movie only has `보고싶어요`, adding a `평가` entry deletes the watchlist-only entry.
- Movie detail entry sections have `수정` and `삭제`; after deletion on a movie page, reload that movie detail rather than navigating home.

## Rating UI
- Detail/list rating display uses five layered emoji marks, one emoji per point.
- Empty portions use the same emoji shape rendered black.
- Half scores use exact 50% horizontal clipping.
- Custom rating modules use a grouped emoji picker with five columns and vertical scroll.
- Emoji picker groups currently include `기본`, `감정`, `취향`, `장르`, `분위기`, `캐릭터`, `기록`.

## Hashtags
- Hashtags cannot contain spaces; old spaced names were normalized, e.g. `원작 존재` -> `원작존재`.
- `왓챠백업` applies only to Watcha-imported review ratings (`RatingModule.name == "왓챠 별점"`).
- `왓챠백업` was removed from all watchlist entries on 2026-06-13; current expected DB state is review-only.
- New entries automatically check TMDb keywords and add `원작존재` when source-material hints match.
- Existing entries can be backfilled with `tools/migrate_novel_hashtag.py`; `원작존재` means source material exists and includes books, novels, comics, memoir/autobiography, and plays/musicals.

## Operational Notes
- Static asset cache versions are manually maintained in `templates/index.html`.
- Local live app is managed by launchctl service `com.cinelog.app` on port `5001`.
- Use timestamped `movies.db.bak-*` backups before data cleanup scripts.
- Standard verification is `python3 -m pytest -q`, `node --check static/js/app.js`, and `git diff --check`.
