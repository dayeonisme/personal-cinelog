import argparse
import csv
import html
from pathlib import Path
from urllib.parse import quote_plus


def tmdb_search_url(title: str, year: str = "") -> str:
    query = quote_plus(title or "")
    url = f"https://www.themoviedb.org/search/movie?query={query}"
    if year:
        url += f"&year={quote_plus(str(year))}"
    return url


def load_rows(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def render_report(rows: list) -> str:
    table_rows = []
    for index, row in enumerate(rows, start=1):
        title = row.get("title_ko") or ""
        year = row.get("year") or ""
        watcha_id = row.get("watcha_id") or ""
        search_url = row.get("search_url") or tmdb_search_url(title, year)
        if year and "year=" not in search_url:
            search_url = tmdb_search_url(title, year)

        table_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(watcha_id)}</code></td>"
            f"<td>{html.escape(title)}</td>"
            f"<td>{html.escape(str(year))}</td>"
            f'<td><a href="{html.escape(search_url, quote=True)}" target="_blank" rel="noreferrer">TMDb search</a></td>'
            f"<td>{html.escape(row.get('note') or '')}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TMDb 수동 매칭 검토</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #f7f8fa;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 26px;
      line-height: 1.25;
    }}
    p {{
      margin: 0 0 20px;
      color: #52606d;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid #d9e2ec;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e4e7eb;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f1f5f8;
      color: #334e68;
      font-weight: 700;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    a {{
      color: #0b69a3;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <main>
    <h1>TMDb 수동 매칭 검토</h1>
    <p>남은 미매칭 영화 {len(rows)}건입니다. TMDb에서 확인한 ID를 CSV의 <code>tmdb_id</code> 칸에 채운 뒤 enrichment를 다시 실행하세요.</p>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Watcha ID</th>
          <th>영화명</th>
          <th>연도</th>
          <th>검색</th>
          <th>메모</th>
        </tr>
      </thead>
      <tbody>
        {''.join(table_rows)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def write_report(input_path: Path, out_path: Path) -> int:
    rows = load_rows(input_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(rows), encoding="utf-8")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an HTML review report for remaining TMDb manual matches.")
    parser.add_argument("--input", type=Path, default=Path("data/tmdb_manual_matches_remaining.csv"))
    parser.add_argument("--out", type=Path, default=Path("data/tmdb_manual_review.html"))
    args = parser.parse_args()

    count = write_report(args.input, args.out)
    print(f"Wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
