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


@pytest.mark.playwright
class TestCardGridResponsive:
    """Channel cards use auto-fill grid: multi-column on desktop, single on mobile."""

    VIEW_WIDE = {"width": 1200, "height": 800}
    VIEW_NARROW = {"width": 600, "height": 800}
    VIEW_MOBILE = {"width": 375, "height": 667}

    def _cards_per_row(self, page) -> int:
        """Count how many cards share the same top y-coordinate (same row)."""
        cards = page.locator(".card")
        tops = [cards.nth(i).bounding_box()["y"] for i in range(cards.count())]
        # group by y within 2px tolerance
        rows = 0
        threshold = 2
        sorted_tops = sorted(tops)
        prev = None
        for t in sorted_tops:
            if prev is None or abs(t - prev) > threshold:
                rows += 1
            prev = t
        return rows

    def test_wide_viewport_multi_column(self, page, fake_site_url):
        """At 1200px, cards should fill multiple columns (more rows than if all in one)."""
        page.set_viewport_size(self.VIEW_WIDE)
        page.goto(f"{fake_site_url}/index.html")
        rows = self._cards_per_row(page)
        card_count = page.locator(".card").count()
        # with ~3 channels at 1200px, all should fit in 1 row (or at least fewer rows than cards)
        assert rows < card_count

    def test_mobile_single_column(self, page, fake_site_url):
        """At 375px, cards should stack in a single column."""
        page.set_viewport_size(self.VIEW_MOBILE)
        page.goto(f"{fake_site_url}/index.html")
        rows = self._cards_per_row(page)
        card_count = page.locator(".card").count()
        assert rows == card_count  # each card on its own row

    def test_card_min_width_respected(self, page, fake_site_url):
        """Each card should be at least 280px wide (the grid minmax minimum)."""
        page.set_viewport_size(self.VIEW_WIDE)
        page.goto(f"{fake_site_url}/index.html")
        cards = page.locator(".card")
        for i in range(cards.count()):
            w = cards.nth(i).bounding_box()["width"]
            assert w >= 280, f"card {i} width {w} < 280"

    def test_cards_fill_grid_width(self, page, fake_site_url):
        """At 1200px with sidebar open, cards should span most of the content area."""
        page.set_viewport_size(self.VIEW_WIDE)
        page.goto(f"{fake_site_url}/index.html")
        grid = page.locator(".channel-grid")
        content = page.locator("#content")
        grid_w = grid.bounding_box()["width"]
        content_w = content.bounding_box()["width"]
        # grid should use at least 80% of content width
        assert grid_w >= content_w * 0.8

    def test_narrow_viewport_single_column(self, page, fake_site_url):
        """At 600px (below 768px mobile breakpoint), cards stack single-column."""
        page.set_viewport_size(self.VIEW_NARROW)
        page.goto(f"{fake_site_url}/index.html")
        cols = page.locator(".channel-grid").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns.split(' ').length"
        )
        assert cols == 1

    def test_wide_viewport_multi_column_template(self, page, fake_site_url):
        """At 1200px, grid should have multiple column tracks (auto-fill)."""
        page.set_viewport_size(self.VIEW_WIDE)
        page.goto(f"{fake_site_url}/index.html")
        cols = page.locator(".channel-grid").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns.split(' ').length"
        )
        assert cols > 1

    def test_ultrawide_uses_more_columns(self, page, fake_site_url):
        """At 2560px, grid should tile into more columns than at 1200px."""
        page.set_viewport_size(self.VIEW_WIDE)
        page.goto(f"{fake_site_url}/index.html")
        cols_narrow = page.locator(".channel-grid").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns.split(' ').length"
        )
        page.set_viewport_size({"width": 2560, "height": 800})
        page.goto(f"{fake_site_url}/index.html")
        cols_wide = page.locator(".channel-grid").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns.split(' ').length"
        )
        assert cols_wide > cols_narrow
