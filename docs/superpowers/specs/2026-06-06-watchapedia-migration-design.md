# WatchaPedia Migration Design

## Goal

Move the user's own WatchaPedia movie ratings and watchlist into the local Cinelog SQLite database so the records are visible in the existing Cinelog local web app.

The migration has two stages:

1. Export the user's WatchaPedia movie lists to CSV.
2. Import those CSV files into Cinelog's existing `Movie`, `Entry`, and `RatingModule` tables.

Comments are out of scope because the user does not need them.

## Constraints

- WatchaPedia does not expose a confirmed public CSV export feature in public docs.
- The exporter must use the user's own authenticated browser session and only read the user's own lists.
- The exporter must avoid aggressive crawling: no parallel fetching, no broad site traversal, and a delay between paginated or scroll-driven reads.
- Login credentials must not be stored in code, files, logs, or environment variables.
- Existing user changes in `templates/index.html` and `static/css/style.css` are unrelated and must not be reverted.
- The existing Cinelog UI should remain unchanged for this first version.

## Architecture

### `tools/export_watchapedia.py`

A Playwright-based local exporter.

- Opens a persistent browser profile under a local ignored directory.
- Lets the user log in manually if no session exists.
- Visits the user's WatchaPedia movie list pages.
- Scrolls or follows loaded API responses slowly until all visible records are collected.
- Writes normalized CSV files:
  - `data/watchapedia_ratings.csv`
  - `data/watchapedia_watchlist.csv`

The exporter should prefer structured page/network data if available. If only DOM data is available, it should parse visible cards conservatively and keep source URLs for later review.

### `tools/import_watcha_csv.py`

A Cinelog importer for the generated CSV files.

- Reads ratings and watchlist CSVs.
- Upserts `Movie` rows by `imdb_id` when present, otherwise by normalized `title + year`.
- Creates `Entry(entry_type="review", watch_status="completed")` for ratings.
- Adds one default `RatingModule` per review with `name="왓챠 별점"`, `emoji="⭐"`, and the WatchaPedia rating value.
- Creates `Entry(entry_type="watchlist")` for watchlist items.
- Skips duplicates by default.
- Supports a dry run mode that reports planned inserts, skipped duplicates, and invalid rows without changing the DB.

## CSV Format

Both CSV files should be UTF-8 with headers.

Ratings:

```csv
source,title,year,rating,watcha_content_id,watcha_url,imdb_id
watchapedia,헤어질 결심,2022,4.5,md...,https://pedia.watcha.com/...,tt...
```

Watchlist:

```csv
source,title,year,watcha_content_id,watcha_url,imdb_id
watchapedia,괴물,2006,md...,https://pedia.watcha.com/...,tt...
```

`imdb_id` may be blank during export. The importer may optionally enrich it later through OMDb, but enrichment is not required for the first working migration.

## Duplicate Rules

- If an imported rating matches an existing review for the same `imdb_id`, skip it.
- If no `imdb_id` exists, match by normalized `title + year`.
- If an imported watchlist item matches an existing review, skip the watchlist item because the movie is already recorded as watched.
- If an imported watchlist item matches an existing watchlist entry, skip it.

## Error Handling

- Export should write partial progress only after successful parsing of rows.
- Export should log ambiguous or malformed cards to a review CSV rather than failing the whole run.
- Import should validate rating values as numbers from 0.5 to 5.0 in 0.5 steps.
- Import should fail clearly if CSV headers are missing.
- Import dry run should be the default unless `--commit` is supplied.

## Testing

Focused tests should cover:

- CSV parsing for ratings and watchlist rows.
- Rating value validation.
- Duplicate detection by `imdb_id`.
- Duplicate detection by `title + year`.
- Watchlist skipping when a review already exists.
- Correct creation of `Entry` and `RatingModule` rows.

Exporter browser automation is allowed to have a smaller smoke test or be manually verified because it depends on the live WatchaPedia authenticated UI.

## Verification

Implementation is complete when:

- Tests for importer behavior pass.
- A sample CSV dry run reports correct counts.
- A sample CSV commit inserts rows into a temporary SQLite DB.
- Running the local app shows imported review and watchlist entries through the existing pages.
