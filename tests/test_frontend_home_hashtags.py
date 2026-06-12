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


def test_movie_detail_renders_watchlist_section_before_review_section():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    detail_start = script.index("function renderMovieDetail(data)")
    detail_end = script.index("function buildMovieDetailEntrySection", detail_start)
    render_movie_detail = script[detail_start:detail_end]

    assert render_movie_detail.index("${watchlistSection}") < render_movie_detail.index("${reviewSection}")


def test_movie_detail_empty_sections_have_add_buttons():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "function buildMovieDetailEmptySection(kind, title, movie)" in script
    assert "function openRegisterForMovie(kind, movie = state.currentMovieDetail?.movie)" in script
    assert "보고싶어요 추가" in script
    assert "평가 추가" in script


def test_registration_entrypoint_is_home_fab_with_type_choice():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert 'id="home-fab"' in template
    assert 'id="review-fab"' not in template
    assert 'id="watchlist-fab"' not in template
    assert 'id="step-type"' in template
    assert 'data-register-type="review"' in template
    assert 'data-register-type="watchlist"' in template
    assert "$('home-fab').onclick = () => openRegisterPage(null);" in script
    assert "function chooseRegisterType(type)" in script


def test_gnb_logo_is_home_entrypoint_without_home_nav_button():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")

    assert 'id="gnb-home-btn"' in template
    assert 'data-page="home"' not in template
    assert "$('gnb-home-btn').onclick = () => navigateTo('home');" in script
    assert ".gnb-btn span" in css
    assert "font-size: 16px;" in css


def test_list_page_titles_are_not_rendered():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert '<h1 class="page-title">홈</h1>' not in template
    assert '<h1 class="page-title">평가</h1>' not in template
    assert '<h1 class="page-title">보고싶어요</h1>' not in template


def test_watcha_pedia_button_renders_below_movie_metadata():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    detail_start = script.index("function renderMovieDetail(data)")
    detail_end = script.index("function buildMovieDetailEmptySection", detail_start)
    render_movie_detail = script[detail_start:detail_end]
    title_row_start = render_movie_detail.index('<div class="movie-detail-title-row">')
    title_row_end = render_movie_detail.index('</div>', title_row_start)
    title_row = render_movie_detail[title_row_start:title_row_end]

    assert "watcha-pedia-btn" in render_movie_detail
    assert "${watchaPediaBtn}" not in title_row
    assert render_movie_detail.index("${metaHtml}") < render_movie_detail.index("movie-detail-actions")


def test_rating_display_uses_module_emoji_and_clipped_half_symbol():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")

    assert "function renderStarsHtml(value, emoji = '⭐', max = 5)" in script
    assert "const safeEmoji = escHtml(emoji || '⭐');" in script
    assert "renderStarsHtml(r.value || 0, emoji)" in script
    assert "star-disp-symbol" in script
    assert ".star-disp-symbol" in css
    assert ".star-disp-half::after" not in css
