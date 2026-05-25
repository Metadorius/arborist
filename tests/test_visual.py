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


@pytest.mark.playwright
class TestSidebarResponsive:
    """Desktop: sidebar open beside content.  Mobile: sidebar closed, overlays."""

    VIEW_DESKTOP = {"width": 1024, "height": 768}
    VIEW_MOBILE = {"width": 375, "height": 667}

    def test_desktop_sidebar_open_by_default(self, page, fake_site_url):
        page.set_viewport_size(self.VIEW_DESKTOP)
        page.goto(f"{fake_site_url}/index.html")
        sidebar = page.locator("#sidebar")
        assert sidebar.is_visible()
        assert "open" in (sidebar.get_attribute("class") or "")

    def test_desktop_sidebar_beside_content(self, page, fake_site_url):
        """Sidebar sits left of content, content doesn't start at x=0."""
        page.set_viewport_size(self.VIEW_DESKTOP)
        page.goto(f"{fake_site_url}/index.html")
        content_box = page.locator("#content").bounding_box()
        # on desktop content should be offset > sidebar width-ish
        assert content_box["x"] > 200  # sidebar is 260px

    def test_mobile_sidebar_closed_by_default(self, page, fake_site_url):
        page.set_viewport_size(self.VIEW_MOBILE)
        page.goto(f"{fake_site_url}/index.html")
        sidebar = page.locator("#sidebar")
        assert "open" not in (sidebar.get_attribute("class") or "")

    def test_mobile_sidebar_overlays_content(self, page, fake_site_url):
        """Open sidebar covers content (content x stays at 0)."""
        page.set_viewport_size(self.VIEW_MOBILE)
        page.goto(f"{fake_site_url}/index.html")
        content_x_closed = page.locator("#content").bounding_box()["x"]
        # open sidebar
        page.locator("#sidebar-toggle").click()
        page.wait_for_timeout(300)
        sidebar = page.locator("#sidebar")
        assert "open" in (sidebar.get_attribute("class") or "")
        # content should still be at same x position (overlay, not pushed)
        content_x_open = page.locator("#content").bounding_box()["x"]
        assert content_x_open == content_x_closed

    def test_mobile_toggle_opens_and_closes(self, page, fake_site_url):
        page.set_viewport_size(self.VIEW_MOBILE)
        page.goto(f"{fake_site_url}/index.html")
        btn = page.locator("#sidebar-toggle")
        sidebar = page.locator("#sidebar")
        # open
        btn.click()
        page.wait_for_timeout(300)
        assert "open" in (sidebar.get_attribute("class") or "")
        # close
        btn.click()
        page.wait_for_timeout(300)
        assert "open" not in (sidebar.get_attribute("class") or "")

    def test_desktop_toggle_pushes_content_back(self, page, fake_site_url):
        """Closing sidebar on desktop shifts content left."""
        page.set_viewport_size(self.VIEW_DESKTOP)
        page.goto(f"{fake_site_url}/index.html")
        content_x_open = page.locator("#content").bounding_box()["x"]
        page.locator("#sidebar-toggle").click()
        page.wait_for_timeout(300)
        content_x_closed = page.locator("#content").bounding_box()["x"]
        assert content_x_closed < content_x_open
