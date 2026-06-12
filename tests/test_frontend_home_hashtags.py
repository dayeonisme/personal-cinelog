from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_grid_renders_entry_hashtags():
    script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    render_home_start = script.index("function renderHomeGrid()")
    render_home_end = script.index("// ══════════════════════════════════════════════════════════════", render_home_start)
    render_home_grid = script[render_home_start:render_home_end]

    assert "const hashtagsHtml = buildHashtagsHtml(entry.hashtags);" in render_home_grid
    assert "${hashtagsHtml}" in render_home_grid
