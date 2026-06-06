from tools.build_tmdb_review_report import render_report, tmdb_search_url


def test_tmdb_search_url_encodes_korean_title_and_year():
    url = tmdb_search_url("5시부터 7시까지 클레오", "1962")

    assert "query=5%EC%8B%9C%EB%B6%80%ED%84%B0+7%EC%8B%9C%EA%B9%8C%EC%A7%80+%ED%81%B4%EB%A0%88%EC%98%A4" in url
    assert "year=1962" in url


def test_render_report_escapes_html_and_includes_row_count():
    html = render_report(
        [
            {
                "watcha_id": "watcha:m123",
                "title_ko": "곡성 <哭聲>",
                "year": "2016",
                "search_url": "",
                "note": "check & verify",
            }
        ]
    )

    assert "남은 미매칭 영화 1건" in html
    assert "곡성 &lt;哭聲&gt;" in html
    assert "check &amp; verify" in html
    assert "watcha:m123" in html
