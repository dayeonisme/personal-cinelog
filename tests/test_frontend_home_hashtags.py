from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_grid_renders_entry_hashtags():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    render_home_start = script.index("function renderHomeGrid()")
    render_home_end = script.index("// ══════════════════════════════════════════════════════════════", render_home_start)
    render_home_grid = script[render_home_start:render_home_end]

    assert "const hashtagsHtml = buildHashtagsHtml(entry.hashtags);" in render_home_grid
    assert "${hashtagsHtml}" in render_home_grid


def test_movie_detail_renders_hashtags_in_movie_metadata_not_entry_sections():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    detail_start = script.index("function renderMovieDetail(data)")
    detail_end = script.index("function buildMovieDetailEntrySection", detail_start)
    render_movie_detail = script[detail_start:detail_end]

    section_start = script.index("function buildMovieDetailEntrySection")
    section_end = script.index("// ══════════════════════════════════════════════════════════════", section_start)
    build_detail_section = script[section_start:section_end]

    assert "const movieHashtags = primaryEntryHashtags(data);" in render_movie_detail
    assert "['러닝타임', fmtRuntime(m.runtime) || null]," in render_movie_detail
    assert "['해시태그', buildHashtagsHtml(movieHashtags)]," in render_movie_detail
    assert render_movie_detail.index("['러닝타임', fmtRuntime(m.runtime) || null],") < render_movie_detail.index(
        "['해시태그', buildHashtagsHtml(movieHashtags)],"
    )
    assert "buildHashtagsHtml(entry.hashtags)" not in build_detail_section


def test_movie_detail_uses_review_hashtags_before_watchlist_hashtags():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    helper_start = script.index("function primaryEntryHashtags(data)")
    helper_end = script.index("function renderMovieDetail(data)", helper_start)
    helper = script[helper_start:helper_end]

    assert "data.review?.hashtags" in helper
    assert "data.watchlist?.hashtags" in helper


def test_static_assets_are_cache_busted():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert '<link rel="stylesheet" href="/static/css/style.css?v=' in template
    assert '<script src="/static/js/app.js?v=' in template


def test_watchlist_default_comment_label_is_reason():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "function defaultCommentNameForType(type)" in script
    assert "type === 'watchlist' ? '보고싶은 이유' : '감상평'" in script
    assert "const name = isDefault ? defaultCommentNameForType(type)" in script
