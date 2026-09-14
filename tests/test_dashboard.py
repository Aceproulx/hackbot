"""Playwright tests for hackbot-dashboard — all features."""
import re, pytest
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:7878"
EMOJI_RE = re.compile(r'[\U0001F000-\U0001FAFF\u2764\uFE0F\u200D]')

@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])

@pytest.fixture(scope="session")
def browser(pw):
    b = pw.new_context(viewport={"width": 1280, "height": 800}).new_page()
    yield b
    b.context.close()

def nav(page, path):
    page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

def no_emoji(page):
    """Assert no emoji glyphs anywhere in rendered page."""
    text = page.inner_text("body")
    assert not EMOJI_RE.search(text), f"Emoji found: {EMOJI_RE.search(text).group()}"

def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), \
        f"Horizontal overflow: {page.evaluate('document.documentElement.scrollWidth')} > {page.evaluate('document.documentElement.clientWidth')}"

def assert_h1(page, expected_re):
    h1 = page.query_selector("main h1")
    assert h1, "No h1 found"
    text = h1.inner_text()
    assert re.search(expected_re, text, re.I), f"h1 mismatch: {text!r}"

# ── OVERVIEW ────────────────────────────────────────────────────────────────

class TestOverview:
    def test_hero_and_no_overflow(self, browser):
        nav(browser, "/")
        expect(browser.locator("main h1")).to_be_visible()
        assert_h1(browser, r"OVERVIEW")
        no_overflow(browser)
        no_emoji(browser)

    def test_stat_cards(self, browser):
        nav(browser, "/")
        stats = browser.query_selector_all(".stat")
        assert len(stats) == 5, f"Expected 5 stat cards, got {len(stats)}"

    def test_worker_table(self, browser):
        nav(browser, "/")
        rows = browser.query_selector_all("table")[0].query_selector_all("tbody tr")
        assert len(rows) >= 2, f"Expected ≥2 worker rows, got {len(rows)}"

    def test_queue_table(self, browser):
        nav(browser, "/")
        tables = browser.query_selector_all("table")
        assert len(tables) >= 2
        qr = tables[1].query_selector_all("tbody tr")
        assert len(qr) >= 4, f"Expected ≥4 queue rows, got {len(qr)}"

    def test_svg_icons_present(self, browser):
        nav(browser, "/")
        assert browser.query_selector_all("svg.ic-svg").__len__() >= 10

    def test_topbar_elements(self, browser):
        nav(browser, "/")
        assert browser.query_selector(".searchbox input")
        assert browser.query_selector("button.btn")
        assert browser.inner_text("button.btn").strip() == "New Task"

    def test_new_task_modal_opens(self, browser):
        nav(browser, "/")
        modal = browser.query_selector("#taskmodal")
        assert modal
        assert browser.evaluate("getComputedStyle(document.getElementById('taskmodal')).display") == "none"
        browser.click("button.btn")
        browser.wait_for_timeout(300)
        assert browser.evaluate("getComputedStyle(document.getElementById('taskmodal')).display") == "flex"
        content = modal.inner_text()
        assert "hackbot-workers" in content

    def test_new_task_modal_closes(self, browser):
        nav(browser, "/")
        browser.click("button.btn")
        browser.wait_for_timeout(300)
        assert browser.evaluate("getComputedStyle(document.getElementById('taskmodal')).display") == "flex"
        # closes by clicking the dimmed backdrop (target === backdrop)
        bb = browser.query_selector("#taskmodal .modal").bounding_box()
        browser.mouse.click(30, max(60, int(bb["y"]) + int(bb["height"]) + 24))
        browser.wait_for_timeout(300)
        assert browser.evaluate("getComputedStyle(document.getElementById('taskmodal')).display") == "none"

# ── NAVIGATION ──────────────────────────────────────────────────────────────

VIEW_PATHS = [
    ("/v/overview",           r"OVERVIEW"),
    ("/v/hunts",              r"HUNTS"),
    ("/v/history",            r"HISTORY"),
    ("/v/monitors",           r"MONITORS"),
    ("/v/topology",           r"TOPOLOGY"),
    ("/v/knowledge",          r"KNOWLEDGE"),
    ("/v/memory",             r"MEMORY"),
    ("/v/assets",             r"ASSETS"),
    ("/v/skills",             r"SKILLS"),
    ("/v/workspaces",         r"WORKSPACES"),
    ("/v/desktops",           r"DESKTOPS"),
    ("/v/registrations",      r"REGISTRATIONS"),
    ("/v/usage",              r"USAGE"),
    ("/v/settings",           r"SETTINGS"),
    ("/console",              None),  # console has custom title
    ("/v/hunts?name=ably.com", None),
    ("/v/hunts?name=intel-20260914", None),
]

class TestNavigation:
    @pytest.mark.parametrize("path,_", VIEW_PATHS, ids=[p for p,_ in VIEW_PATHS])
    def test_view_renders(self, browser, path, _):
        nav(browser, path)
        no_overflow(browser)
        assert len(browser.query_selector_all("svg.ic-svg")) >= 1, f"No SVG icons on {path}"

    @pytest.mark.parametrize("path,_", VIEW_PATHS, ids=[p for p,_ in VIEW_PATHS])
    def test_no_emoji(self, browser, path, _):
        nav(browser, path)
        no_emoji(browser)

# ── SEARCH FILTER ───────────────────────────────────────────────────────────

class TestSearchFilter:
    def test_filter_hunts_by_name(self, browser):
        nav(browser, "/v/hunts")
        total_cards = len(browser.query_selector_all(".filter-item"))
        assert total_cards >= 4
        browser.fill("#globalsearch", "intel")
        browser.wait_for_timeout(300)
        visible = browser.evaluate("""
            [...document.querySelectorAll('.filter-item')]
                .filter(e => e.style.display !== 'none')
                .length
        """)
        assert visible >= 1, f"Filter didn't narrow from {total_cards}"
        assert visible < total_cards
        browser.fill("#globalsearch", "")
        browser.wait_for_timeout(200)

    def test_filter_shows_nothing_for_bogus(self, browser):
        nav(browser, "/v/hunts")
        browser.fill("#globalsearch", "zzznonexistent999")
        browser.wait_for_timeout(300)
        visible = browser.evaluate("""
            [...document.querySelectorAll('.filter-item')]
                .filter(e => e.style.display !== 'none')
                .length
        """)
        assert visible == 0

# ── HUNT DETAIL ─────────────────────────────────────────────────────────────

class TestHuntDetail:
    def test_session_hunt_detail(self, browser):
        nav(browser, "/hunts?name=ably.com")
        no_overflow(browser)
        h1 = browser.query_selector("main h1").inner_text()
        assert "ABLY" in h1.upper()
        assert browser.query_selector("main h1 span.mono"), "No mono span in hero"
        tabs = browser.query_selector_all("[data-tabbtn='hunt']")
        assert len(tabs) == 7, f"Expected 7 tabs, got {len(tabs)}"
        labels = [t.inner_text().strip() for t in tabs]
        assert "Overview" in labels
        assert "Features" in labels
        assert "Reports" in labels

    def test_run_hunt_detail(self, browser):
        nav(browser, "/hunts?name=intel-20260914")
        no_overflow(browser)
        h1 = browser.query_selector("main h1").inner_text()
        assert "INTEL" in h1.upper()
        tabs = browser.query_selector_all("[data-tabbtn='hunt']")
        assert len(tabs) == 7

    def test_tab_switching(self, browser):
        nav(browser, "/hunts?name=ably.com")
        browser.click("[data-tabbtn='hunt'][data-target='t-reports']")
        browser.wait_for_timeout(300)
        visible_panels = browser.evaluate("""
            [...document.querySelectorAll('[data-tabgroup=hunt]')]
                .filter(p => p.style.display !== 'none')
                .map(p => p.id)
        """)
        assert visible_panels == ["t-reports"], f"Unexpected panels: {visible_panels}"
        active_tabs = browser.evaluate("""
            [...document.querySelectorAll('[data-tabbtn=hunt]')]
                .filter(t => t.classList.contains('active'))
                .map(t => t.innerText.trim())
        """)
        assert "Reports" in active_tabs

    def test_overview_tab_default(self, browser):
        nav(browser, "/hunts?name=ably.com")
        visible = browser.evaluate("""
            [...document.querySelectorAll('[data-tabgroup=hunt]')]
                .filter(p => p.style.display !== 'none')
                .map(p => p.id)
        """)
        assert visible == ["t-overview"]

# ── CONSOLE ─────────────────────────────────────────────────────────────────

class TestConsole:
    def test_console_renders(self, browser):
        nav(browser, "/console")
        assert browser.query_selector(".terminal")
        assert browser.query_selector("select")

    def test_log_selector_options_unique(self, browser):
        nav(browser, "/console")
        opts = browser.evaluate("""
            [...document.querySelectorAll('select option')]
                .map(o => o.value)
        """)
        assert len(opts) >= 10
        assert len(opts) == len(set(opts)), "Duplicate option values in console selector"

    def test_worker_log_via_param(self, browser):
        nav(browser, "/console?w=worker-2-nvidiapublicbugbounty")
        pre = browser.inner_text(".terminal")
        assert "NVIDIA" in pre.upper() or "nvidia" in pre.lower() or "worker-2" in pre

    def test_session_log_via_param(self, browser):
        browser.goto(f"{BASE}/console?l=sessions%2Fintel%2Fsession.log", wait_until="domcontentloaded")
        browser.wait_for_load_state("networkidle")
        pre = browser.inner_text(".terminal")
        assert "Intel hunt session log" in pre

    def test_worker_pool_log(self, browser):
        nav(browser, "/console?l=worker-pool%2Fpool.log")
        pre = browser.inner_text(".terminal")
        assert len(pre) > 10, "Pool log seems empty"

# ── EVIDENCE ────────────────────────────────────────────────────────────────

class TestEvidence:
    def test_evidence_view(self, browser):
        nav(browser, "/evidence/ably.com")
        no_overflow(browser)
        rows = browser.query_selector_all("table tbody tr")
        assert len(rows) >= 1

    def test_404_for_nonexistent(self, browser):
        resp = browser.goto(f"{BASE}/report/ably.com/fake.md", wait_until="domcontentloaded")
        text = browser.inner_text("body")
        assert "404" in text or "report not found" in text

# ── SKILLS ──────────────────────────────────────────────────────────────────

class TestSkills:
    def test_library_tab(self, browser):
        nav(browser, "/v/skills?view=library")
        cards = browser.query_selector_all("a.filter-item")
        assert len(cards) >= 10, f"Expected ≥10 skill cards, got {len(cards)}"

    def test_activations_tab_empty_state(self, browser):
        nav(browser, "/v/skills?view=activations")
        empty = browser.query_selector(".empty")
        assert empty, "Activations should show empty state"

    def test_filter_skills(self, browser):
        nav(browser, "/v/skills?view=library")
        total = len(browser.query_selector_all(".filter-item"))
        browser.fill("#globalsearch", "xss")
        browser.wait_for_timeout(300)
        visible = browser.evaluate("""
            [...document.querySelectorAll('.filter-item')]
                .filter(e => e.style.display !== 'none').length
        """)
        assert visible >= 1
        assert visible < total
        browser.fill("#globalsearch", "")

# ── TOPOLOGY ────────────────────────────────────────────────────────────────

class TestTopology:
    def test_renders_nodes(self, browser):
        nav(browser, "/v/topology")
        no_overflow(browser)
        cards = browser.query_selector_all(".card.narrow")
        assert len(cards) >= 6, f"Expected ≥6 topology nodes, got {len(cards)}"

# ── USAGE ───────────────────────────────────────────────────────────────────

class TestUsage:
    def test_stats_render(self, browser):
        nav(browser, "/v/usage")
        stats = browser.query_selector_all(".stat")
        assert len(stats) >= 4
        no_overflow(browser)

# ── SETTINGS ────────────────────────────────────────────────────────────────

class TestSettings:
    def test_cards_render(self, browser):
        nav(browser, "/v/settings")
        cards = browser.query_selector_all(".card")
        assert len(cards) >= 5
        no_overflow(browser)

    def test_config_displayed(self, browser):
        nav(browser, "/v/settings")
        text = browser.inner_text("body")
        assert "opencode (opencode)" in text or "OPENCODE (OPENCODE)" in text.upper()
        assert "enabled" in text
        assert "DeepSeek" in text

# ── REGISTRATIONS ───────────────────────────────────────────────────────────

class TestRegistrations:
    def test_table_renders(self, browser):
        nav(browser, "/v/registrations")
        tables = browser.query_selector_all("table")
        assert len(tables) >= 1
        rows = tables[0].query_selector_all("tbody tr")
        assert len(rows) >= 5
        no_overflow(browser)

# ── HISTORY ─────────────────────────────────────────────────────────────────

class TestHistory:
    def test_table_renders(self, browser):
        nav(browser, "/v/history")
        tables = browser.query_selector_all("table")
        assert len(tables) >= 1
        rows = tables[0].query_selector_all("tbody tr")
        assert len(rows) >= 4
        no_overflow(browser)

# ── MONITORS ────────────────────────────────────────────────────────────────

class TestMonitors:
    def test_renders(self, browser):
        nav(browser, "/v/monitors")
        no_overflow(browser)
        cards = browser.query_selector_all(".card")
        assert len(cards) >= 1

# ── DESKTOPS ────────────────────────────────────────────────────────────────

class TestDesktops:
    def test_empty_state(self, browser):
        nav(browser, "/v/desktops")
        empty = browser.query_selector(".empty")
        assert empty, "Desktops should show honest empty state"

# ── CONSOLE TAB (from other pages) ──────────────────────────────────────────

class TestConsoleTab:
    def test_tab_opens_console(self, browser):
        nav(browser, "/")
        browser.click(".console-tab")
        browser.wait_for_load_state("domcontentloaded")
        assert "/console" in browser.url

# ── RESPONSIVE ──────────────────────────────────────────────────────────────

class TestResponsive:
    def test_narrow_viewport_no_overflow(self, browser):
        browser.set_viewport_size({"width": 800, "height": 600})
        nav(browser, "/")
        no_overflow(browser)
        nav(browser, "/v/hunts")
        no_overflow(browser)
        nav(browser, "/hunts?name=ably.com")
        no_overflow(browser)
        browser.set_viewport_size({"width": 1280, "height": 800})

# ── GLOBAL ──────────────────────────────────────────────────────────────────

class TestGlobal:
    def test_page_title(self, browser):
        nav(browser, "/")
        assert "Hackbot" in browser.title()

    def test_accent_color(self, browser):
        nav(browser, "/")
        accent = browser.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        assert accent == "#8f1618", f"Accent mismatch: {accent}"

    def test_sidebar_width(self, browser):
        nav(browser, "/")
        w = browser.evaluate("getComputedStyle(document.querySelector('.sidebar')).width")
        assert w in ("244px", "240px"), f"Sidebar width: {w}"

    def test_body_bg(self, browser):
        nav(browser, "/")
        bg = browser.evaluate("getComputedStyle(document.body).backgroundColor")
        assert bg == "rgb(247, 244, 238)", f"Body bg: {bg}"
