"""Visual / browser tests using Playwright."""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fake_site_url(tmp_path_factory):
    """Generate fake site once and serve it on localhost."""
    from tests.fake_data import generate_fake_site

    site = tmp_path_factory.mktemp("playsite")
    generate_fake_site(site, copy_css=True)
    return f"file:///{site.as_posix()}"


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.playwright
class TestHomePage:
    def test_title(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/index.html")
        assert "Arborist" in page.title()

    def test_sidebar_visible(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/index.html")
        sidebar = page.locator("#sidebar")
        assert sidebar.is_visible()

    def test_channels_listed(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/index.html")
        text = page.locator("#content").inner_text()
        assert "assets" in text
        assert "tutorials" in text

    def test_toggle_sidebar(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/index.html")
        btn = page.locator("#sidebar-toggle")
        btn.click()
        # after close, sidebar should be hidden
        page.wait_for_timeout(300)
        sidebar = page.locator("#sidebar")
        assert "open" not in (sidebar.get_attribute("class") or "")

    def test_navigate_to_channel(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/index.html")
        page.locator("a.tree-channel-link >> text=assets").first.click()
        page.wait_for_timeout(200)
        assert "# assets" in page.locator("h1").inner_text()


@pytest.mark.playwright
class TestThreadPage:
    def test_messages_render(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/channels/111/10001/index.html")
        msgs = page.locator("article.message")
        assert msgs.count() >= 3

    def test_breadcrumb_present(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/channels/111/10001/index.html")
        bc = page.locator(".breadcrumb")
        assert bc.is_visible()

    def test_active_tree_highlight(self, page, fake_site_url):
        page.goto(f"{fake_site_url}/channels/222/20001/index.html")
        link = page.locator("a.tree-thread.active")
        assert link.is_visible()
