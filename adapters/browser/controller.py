"""
adapters/browser/controller.py
Browser automation adapter using Playwright (primary) with Selenium fallback.
Provides: navigation, element interaction, form fill, screenshot, scraping.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


class BrowserError(Exception):
    """Raised on browser automation failures."""


class BrowserController:
    """
    Asynchronous browser automation using Microsoft Playwright.

    Install:
        pip install playwright
        playwright install chromium

    Usage (sync wrapper):
        browser = BrowserController()
        browser.start()
        browser.navigate("https://google.com")
        browser.type_text("#search", "ORIGAMI robot")
        browser.press("Enter")
        title = browser.get_title()
        browser.stop()

    Or as context manager:
        with BrowserController() as browser:
            browser.navigate("https://example.com")
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        timeout_ms: int = 30_000,
        user_data_dir: Optional[Path] = None,
    ) -> None:
        """
        Args:
            headless: Run browser without a visible window.
            browser_type: 'chromium', 'firefox', or 'webkit'.
            timeout_ms: Default timeout for all wait operations in ms.
            user_data_dir: Persistent profile directory (keeps cookies/session).
        """
        self.headless = headless
        self.browser_type = browser_type
        self.timeout_ms = timeout_ms
        self.user_data_dir = user_data_dir

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the browser. Must be called before any other method."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise BrowserError(
                "Playwright not installed. Run: pip install playwright && playwright install"
            )

        self._playwright = sync_playwright().start()
        driver = getattr(self._playwright, self.browser_type)

        launch_kwargs: dict[str, Any] = {"headless": self.headless}

        if self.user_data_dir:
            # Persistent context preserves cookies and local storage
            self._context = driver.launch_persistent_context(
                str(self.user_data_dir), **launch_kwargs
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            self._browser = driver.launch(**launch_kwargs)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()

        self._page.set_default_timeout(self.timeout_ms)
        logger.info("Browser started (%s, headless=%s).", self.browser_type, self.headless)

    def stop(self) -> None:
        """Close browser and release resources."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.warning("Error during browser shutdown: %s", exc)
        finally:
            self._page = self._context = self._browser = self._playwright = None
        logger.info("Browser stopped.")

    def __enter__(self) -> "BrowserController":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def _ensure_started(self) -> None:
        if self._page is None:
            raise BrowserError("Browser not started. Call .start() first.")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """
        Navigate to a URL.

        Args:
            url: Target URL.
            wait_until: 'load', 'domcontentloaded', 'networkidle', or 'commit'.
        """
        self._ensure_started()
        self._page.goto(url, wait_until=wait_until)
        logger.info("Navigated to: %s", url)

    def go_back(self) -> None:
        """Navigate to the previous page in history."""
        self._ensure_started()
        self._page.go_back()

    def go_forward(self) -> None:
        """Navigate forward in history."""
        self._ensure_started()
        self._page.go_forward()

    def reload(self) -> None:
        """Reload the current page."""
        self._ensure_started()
        self._page.reload()

    def get_url(self) -> str:
        """Return the current page URL."""
        self._ensure_started()
        return self._page.url

    def get_title(self) -> str:
        """Return the current page title."""
        self._ensure_started()
        return self._page.title()

    # ------------------------------------------------------------------
    # Element Interaction
    # ------------------------------------------------------------------

    def click(self, selector: str) -> None:
        """Click an element matching the CSS/XPath selector."""
        self._ensure_started()
        self._page.click(selector)
        logger.debug("Clicked: %s", selector)

    def type_text(self, selector: str, text: str, clear: bool = True) -> None:
        """
        Type text into an input field.

        Args:
            selector: CSS or XPath selector for the input.
            text: Text to type.
            clear: If True, clears existing text first.
        """
        self._ensure_started()
        if clear:
            self._page.fill(selector, "")
        self._page.type(selector, text)
        logger.debug("Typed into %s.", selector)

    def fill(self, selector: str, value: str) -> None:
        """Set an input field's value directly (faster than type_text)."""
        self._ensure_started()
        self._page.fill(selector, value)

    def press(self, key: str) -> None:
        """Simulate a keyboard key press on the focused element."""
        self._ensure_started()
        self._page.keyboard.press(key)

    def select_option(self, selector: str, value: str) -> None:
        """Select a dropdown option by value."""
        self._ensure_started()
        self._page.select_option(selector, value)

    def check(self, selector: str) -> None:
        """Check a checkbox."""
        self._ensure_started()
        self._page.check(selector)

    def hover(self, selector: str) -> None:
        """Hover the mouse over an element."""
        self._ensure_started()
        self._page.hover(selector)

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None) -> None:
        """Wait until an element matching selector appears in the DOM."""
        self._ensure_started()
        self._page.wait_for_selector(selector, timeout=timeout_ms or self.timeout_ms)

    def wait_for_navigation(self, timeout_ms: Optional[int] = None) -> None:
        """Wait for the page to finish navigation."""
        self._ensure_started()
        self._page.wait_for_load_state("networkidle", timeout=timeout_ms or self.timeout_ms)

    def wait_for_text(self, text: str, timeout_ms: Optional[int] = None) -> None:
        """Wait until the given text appears anywhere on the page."""
        self._ensure_started()
        self._page.wait_for_selector(
            f"text={text}", timeout=timeout_ms or self.timeout_ms
        )

    # ------------------------------------------------------------------
    # Content Extraction
    # ------------------------------------------------------------------

    def get_text(self, selector: str) -> str:
        """Return the inner text of an element."""
        self._ensure_started()
        return self._page.inner_text(selector)

    def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Return an attribute value of an element."""
        self._ensure_started()
        return self._page.get_attribute(selector, attribute)

    def get_all_text(self, selector: str) -> list[str]:
        """Return inner text from all elements matching the selector."""
        self._ensure_started()
        elements = self._page.query_selector_all(selector)
        return [el.inner_text() for el in elements]

    def get_page_source(self) -> str:
        """Return the full HTML source of the current page."""
        self._ensure_started()
        return self._page.content()

    def evaluate(self, js_expression: str) -> Any:
        """Execute JavaScript in the page context and return the result."""
        self._ensure_started()
        return self._page.evaluate(js_expression)

    # ------------------------------------------------------------------
    # Forms
    # ------------------------------------------------------------------

    def fill_form(self, field_map: dict[str, str]) -> None:
        """
        Fill multiple form fields at once.

        Args:
            field_map: Dict mapping CSS selectors → values.
        """
        for selector, value in field_map.items():
            self.fill(selector, value)
        logger.info("Filled form with %d fields.", len(field_map))

    def submit_form(self, submit_selector: str = "button[type=submit]") -> None:
        """Click a form's submit button."""
        self.click(submit_selector)
        logger.info("Form submitted.")

    # ------------------------------------------------------------------
    # Screenshots / Files
    # ------------------------------------------------------------------

    def screenshot(self, path: Optional[Path] = None, full_page: bool = True) -> Path:
        """
        Capture a screenshot of the current page.

        Args:
            path: Output file path (.png). Defaults to ~/Desktop/browser_shot.png.
            full_page: If True, captures the entire scrollable page.
        """
        self._ensure_started()
        if path is None:
            path = Path.home() / "Desktop" / "browser_screenshot.png"
        self._page.screenshot(path=str(path), full_page=full_page)
        logger.info("Browser screenshot saved to %s.", path)
        return path

    def download_file(self, trigger_selector: str, save_dir: Path) -> Path:
        """
        Click a download link and save the file.

        Args:
            trigger_selector: CSS selector for the download link/button.
            save_dir: Directory to save the downloaded file.
        """
        self._ensure_started()
        save_dir.mkdir(parents=True, exist_ok=True)
        with self._page.expect_download() as download_info:
            self.click(trigger_selector)
        download = download_info.value
        dest = save_dir / download.suggested_filename
        download.save_as(str(dest))
        logger.info("File downloaded to %s.", dest)
        return dest

    # ------------------------------------------------------------------
    # Tabs / Pages
    # ------------------------------------------------------------------

    def new_tab(self, url: Optional[str] = None) -> None:
        """Open a new tab and optionally navigate to a URL."""
        self._ensure_started()
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        if url:
            self.navigate(url)

    def close_tab(self) -> None:
        """Close the current tab."""
        self._ensure_started()
        self._page.close()
        pages = self._context.pages
        self._page = pages[-1] if pages else None

    # ------------------------------------------------------------------
    # Cookies
    # ------------------------------------------------------------------

    def get_cookies(self) -> list[dict]:
        """Return all cookies for the current context."""
        self._ensure_started()
        return self._context.cookies()

    def add_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        """Add a cookie to the browser context."""
        self._ensure_started()
        self._context.add_cookies([{
            "name": name, "value": value, "domain": domain, "path": path
        }])

    def clear_cookies(self) -> None:
        """Delete all cookies from the context."""
        self._ensure_started()
        self._context.clear_cookies()