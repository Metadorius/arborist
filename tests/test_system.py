"""System test: generate a full fake site and verify HTML structure.
Site generated once per session (session-scoped fixture).
"""

import pytest

from .fake_data import generate_fake_site


@pytest.fixture(scope="session")
def fake_site(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fakesite")
    generate_fake_site(tmp_path, copy_css=False)
    return tmp_path


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

class TestHomePage:
    def test_exists(self, fake_site):
        assert (fake_site / "index.html").exists()

    def test_lists_channels(self, fake_site):
        html = (fake_site / "index.html").read_text()
        assert "Arborist" in html
        assert "assets" in html
        assert "tutorials" in html
        assert "show-and-tell" in html

    def test_has_css_link(self, fake_site):
        html = (fake_site / "index.html").read_text()
        assert 'href="styles.css"' in html


# ---------------------------------------------------------------------------
# Channel pages
# ---------------------------------------------------------------------------

class TestChannelPage:
    def test_exists(self, fake_site):
        assert (fake_site / "channels" / "1" / "111" / "index.html").exists()

    def test_lists_threads(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "index.html").read_text()
        assert "Cool Asset Pack v2" in html
        assert "5 messages" in html

    def test_back_link(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "index.html").read_text()
        assert "../index.html" in html


# ---------------------------------------------------------------------------
# Thread pages
# ---------------------------------------------------------------------------

class TestThreadPage:
    def test_exists(self, fake_site):
        assert (fake_site / "channels" / "1" / "111" / "10001" / "index.html").exists()

    def test_sidebar_nav(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'data-path="channels/1/111"' in html
        assert 'data-path="channels/1/111/10001"' in html

    def test_messages_present(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'id="msg-1001"' in html
        assert 'id="msg-1005"' in html

    def test_author_names(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert "Alice" in html
        assert "BobBot" in html
        assert "Charlie" in html

    def test_timestamps(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'datetime="2026-05-20T08:00:00+00:00"' in html

    def test_edited_marker(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert '<span class="edited">(edited)</span>' in html

    def test_reactions(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text(encoding="utf-8")
        assert 'class="reaction"' in html

    def test_mentions(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert '<span class="mention user-mention">@101</span>' in html

    def test_spoiler(self, fake_site):
        html = (fake_site / "channels" / "1" / "222" / "20001" / "index.html").read_text()
        assert '<span class="spoiler">' in html

    def test_strikethrough(self, fake_site):
        html = (fake_site / "channels" / "1" / "222" / "20001" / "index.html").read_text()
        assert "<del>" in html

    def test_code_block(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert '<div class="highlight">' in html
        assert "TextureLoader" in html

    def test_small_text(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert "<small>" in html

    def test_embed(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'class="embed"' in html
        assert "Cool Asset Pack v2" in html

    def test_attachment_images(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert '<img src="' in html
        assert 'preview.png' in html

    def test_attachment_links(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'class="attachment-link"' in html
        assert 'asset-pack-v2.zip' in html

    def test_markdown_files(self, fake_site):
        """Raw .md files should also exist."""
        assert (fake_site / "channels" / "1" / "111" / "10001" / "1001.md").exists()
        assert (fake_site / "channels" / "1" / "111" / "10001" / "1005.md").exists()


# ---------------------------------------------------------------------------
# Footer (all pages)
# ---------------------------------------------------------------------------

class TestFooter:
    def test_home_page_has_footer(self, fake_site):
        html = (fake_site / "index.html").read_text()
        assert 'class="site-footer"' in html
        assert 'href="legal.html"' in html
        assert "Arborist" in html

    def test_channel_page_has_footer(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "index.html").read_text()
        assert 'class="site-footer"' in html
        assert "legal.html" in html

    def test_thread_page_has_footer(self, fake_site):
        html = (fake_site / "channels" / "1" / "111" / "10001" / "index.html").read_text()
        assert 'class="site-footer"' in html
        assert "legal.html" in html

    def test_legal_page_has_footer(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert 'class="site-footer"' in html


# ---------------------------------------------------------------------------
# Static pages (legal)
# ---------------------------------------------------------------------------

class TestStaticPages:
    def test_legal_page_exists(self, fake_site):
        assert (fake_site / "legal.html").exists()

    def test_legal_page_title(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "<title>Legal" in html
        assert "<h1>Legal</h1>" in html

    def test_legal_page_has_licensing(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "Licensing" in html
        assert "CC-BY-NC 4.0" in html
        assert "irrevocable" in html

    def test_legal_page_has_data_processing(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "historical preservation" in html
        assert "2297-VI" in html

    def test_legal_page_has_jurisdiction(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "Ukraine" in html

    def test_legal_page_has_rights_section(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "Your Rights" in html

    def test_legal_page_has_takedown(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "Third-Party Rights" in html

    def test_legal_page_has_non_commercial(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert "non-commercial" in html
        assert "No Commercial Use" in html

    def test_legal_page_not_in_sidebar(self, fake_site):
        """Sidebar should contain channel/thread tree but no legal-specific link."""
        html = (fake_site / "legal.html").read_text()
        # sidebar must have the normal channel tree
        assert 'data-path="channels/1/111"' in html
        # but no data-path entry for the legal page itself
        sidebar_links = [l for l in html.splitlines() if "data-path=" in l]
        for link in sidebar_links:
            assert "legal" not in link

    def test_legal_page_has_static_content_class(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert 'class="static-page-content"' in html

    def test_legal_page_has_css_link(self, fake_site):
        html = (fake_site / "legal.html").read_text()
        assert 'href="styles.css"' in html

    def test_generic_framework(self, fake_site):
        """The static page framework uses page-content-wrapper for layout."""
        html = (fake_site / "legal.html").read_text()
        assert 'class="page-content-wrapper"' in html
