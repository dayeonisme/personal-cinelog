# Repository Instructions

## Project
- Cinelog is a Flask + SQLite personal movie log app.
- Main app files: `app.py`, `models.py`, `templates/index.html`, `static/js/app.js`, `static/css/style.css`.
- Local database is `movies.db`; create a timestamped backup before running data migrations.

## Common Commands
- Run tests: `python3 -m pytest -q`
- JS syntax check: `node --check static/js/app.js`
- Whitespace check: `git diff --check`
- Restart local live app: `launchctl kickstart -k gui/$(id -u)/com.cinelog.app`
- Local app URL: `http://127.0.0.1:5001/`

## Frontend Rules
- After changing `static/js/app.js` or `static/css/style.css`, bump the query-string asset version in `templates/index.html`.
- Verify important UI changes in the browser when feasible.
- Movie detail layout currently shows `보고싶어요 정보` before `평가 정보`.
- Movie detail entry sections must expose both `수정` and `삭제` actions; deletion reuses the existing confirmation modal.
- Home card hover must not show hashtags; rating hover text is compact, e.g. `⭐ 3.5`.

## Hashtag/Data Rules
- `왓챠백업` is only for imported Watcha review entries where a rating module name is `왓챠 별점`.
- `왓챠백업` must not remain on `watchlist` entries. Use `tools/migrate_watcha_hashtag.py` to sync and remove incorrect tags.
- New entries automatically check TMDb keywords and add `원작존재` when source-material hints match.
- `tools/migrate_novel_hashtag.py` is the backfill script for existing entries.
- `원작존재` means a TMDb keyword matched source-material hints such as `based on novel`, `based on book`, `based on comic`, `based on play or musical`, etc. It includes more than novels.

## Verification Before PR/Merge
- Run `python3 -m pytest -q`.
- Run `node --check static/js/app.js && git diff --check`.
- If local DB data was changed, verify the relevant DB counts/API result explicitly.
