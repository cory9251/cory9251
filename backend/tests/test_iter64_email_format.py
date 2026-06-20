"""Iter 64 — Email Blast formatting fix.

Verifies the plain-text → HTML normalizer turns the kinds of text admins
actually type into well-formed HTML so emails render properly in Resend
(previously: all newlines collapsed → "jumbled up" email).
"""
from routes.admin_blasts import _normalize_plain_text_to_html as N


def test_empty_input_returns_empty_string():
    assert N("") == ""
    assert N(None or "") == ""


def test_existing_html_is_passed_through_untouched():
    """TipTap output already contains block tags — we MUST NOT re-wrap it
    or we'd end up with <p><p>...</p></p>."""
    html = "<p>Hi <strong>team</strong></p><p>Welcome.</p>"
    assert N(html) == html


def test_multiline_html_is_passed_through_untouched():
    """A real TipTap doc with mixed marks should survive intact."""
    html = '<h2>Heading</h2><p>Hello <em>world</em></p><ul><li>One</li></ul>'
    assert N(html) == html


def test_plain_text_paragraphs_become_p_tags():
    text = "Hey team,\n\nWe have news.\n\nThanks."
    out = N(text)
    assert "<p" in out
    assert out.count("<p ") == 3
    assert "Hey team," in out
    assert "We have news." in out


def test_single_newline_becomes_br_inside_paragraph():
    """Email signatures depend on this: 'Thanks,\\nHCOB' should produce
    a single paragraph with a <br/> between the lines."""
    text = "Thanks,\nHCOB"
    out = N(text)
    assert "<br/>" in out
    assert out.count("<p ") == 1


def test_bullet_list_after_text_is_detected():
    text = "Things to bring:\n- Mop\n- Bucket\n\nThanks."
    out = N(text)
    assert "<ul" in out
    assert out.count("<li") == 2
    assert "Things to bring:" in out  # text line still there as a paragraph
    assert "Thanks." in out


def test_numbered_list_is_detected():
    text = "Steps:\n1. Show up\n2. Sign in\n3. Clean"
    out = N(text)
    assert "<ol" in out
    assert out.count("<li") == 3


def test_html_special_chars_in_plain_text_are_escaped():
    """Admin types '<script>' literally — must not become live HTML."""
    text = "Watch out: <script>alert(1)</script> done."
    out = N(text)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_url_is_auto_linked():
    text = "Visit https://hcobnetwork.com/c/abc today"
    out = N(text)
    assert 'href="https://hcobnetwork.com/c/abc"' in out
    assert "<a " in out


def test_inline_markdown_bold_and_italic():
    text = "This is **bold** and _italic_ text."
    out = N(text)
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out


def test_existing_html_url_not_double_linked():
    """If the body already has an <a href=...>, don't auto-link the URL
    inside it again (would produce nested <a>)."""
    html = '<p>Click <a href="https://example.com">here</a></p>'
    out = N(html)
    # Block-tag passthrough — should be identical to input.
    assert out == html


def test_window_line_endings_normalized():
    """Windows admins (Outlook copy-paste) use \\r\\n — must work."""
    text = "Line one\r\n\r\nLine two"
    out = N(text)
    assert "Line one" in out
    assert "Line two" in out
    assert out.count("<p ") == 2


def test_renders_in_email_layout_with_paragraph_spacing():
    """Verify the produced HTML uses inline styles (Resend strips <style>
    tags in some clients — inline is the safe path)."""
    out = N("First paragraph.\n\nSecond paragraph.")
    assert "margin:0 0 14px" in out


def test_render_body_applies_normalization():
    """Integration: _render_body should merge tags AND normalize."""
    from routes.admin_blasts import _render_body
    body = "Hi {{first_name}},\n\nWelcome!"
    worker = {"name": "Jane Doe", "email": "jane@example.com"}
    out = _render_body(body, worker)
    assert "Hi Jane," in out
    assert "<p " in out
    assert out.count("<p ") == 2


def test_render_body_html_input_passthrough():
    """HTML body from TipTap should preserve structure after merge tags."""
    from routes.admin_blasts import _render_body
    body = "<p>Hi {{first_name}}</p><p>Welcome!</p>"
    worker = {"name": "Jane Doe", "email": "jane@example.com"}
    out = _render_body(body, worker)
    assert out == "<p>Hi Jane</p><p>Welcome!</p>"
