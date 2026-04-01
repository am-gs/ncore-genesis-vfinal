"""NCore Genesis — Camoufox Stealth Browser Automation v7.5

C++-level Firefox anti-detect via Camoufox with Playwright API.
Falls back to vanilla Playwright with stealth injections if Camoufox
is not installed.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any

import structlog

log = structlog.get_logger()

# ── Detect Camoufox availability ─────────────────────────────────────────────
try:
    from camoufox.asyncio import AsyncCamoufox

    _HAS_CAMOUFOX = True
except ImportError:
    _HAS_CAMOUFOX = False

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = {runtime: {}};
"""

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


class StealthBrowser:
    """Anti-detect browser automation with human-like interaction patterns."""

    def __init__(self, proxy: str | None = None, headless: bool = True):
        self.proxy = proxy
        self.headless = headless
        self._browser = None
        self._context = None
        self._camoufox_cm = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        t0 = time.monotonic()
        if _HAS_CAMOUFOX:
            log.info("browser.start", engine="camoufox", headless=self.headless)
            proxy_cfg = {"server": self.proxy} if self.proxy else None
            self._camoufox_cm = AsyncCamoufox(
                headless=self.headless,
                proxy=proxy_cfg,
            )
            self._browser = await self._camoufox_cm.__aenter__()
        else:
            log.warning("browser.start", engine="playwright_fallback",
                        reason="camoufox not installed")
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
            launch_args = {"headless": self.headless}
            if self.proxy:
                launch_args["proxy"] = {"server": self.proxy}
            self._browser = await self._pw.firefox.launch(**launch_args)
        self._context = await self._browser.new_context(
            user_agent=random.choice(_USER_AGENTS) if not _HAS_CAMOUFOX else None,
        )
        if not _HAS_CAMOUFOX:
            await self._context.add_init_script(_STEALTH_JS)
        elapsed = time.monotonic() - t0
        log.info("browser.ready", elapsed_s=round(elapsed, 2))

    async def stop(self):
        t0 = time.monotonic()
        if self._context:
            await self._context.close()
            self._context = None
        if _HAS_CAMOUFOX and self._camoufox_cm:
            await self._camoufox_cm.__aexit__(None, None, None)
            self._camoufox_cm = None
        elif self._browser:
            await self._browser.close()
            if hasattr(self, "_pw"):
                await self._pw.stop()
        self._browser = None
        log.info("browser.stopped", elapsed_s=round(time.monotonic() - t0, 2))

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    # ── Navigation ────────────────────────────────────────────────────────────

    async def navigate(self, url: str, wait_for: str = "load",
                       timeout: int = 30000) -> Any:
        t0 = time.monotonic()
        page = await self._context.new_page()
        await page.goto(url, wait_until=wait_for, timeout=timeout)
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)
        elapsed = time.monotonic() - t0
        log.info("browser.navigate", url=url, elapsed_s=round(elapsed, 2),
                 human_delay_s=round(delay, 2))
        return page

    # ── Form interaction ──────────────────────────────────────────────────────

    async def fill_form(self, page: Any, fields: dict) -> None:
        t0 = time.monotonic()
        for selector, value in fields.items():
            await page.click(selector)
            await page.fill(selector, "")  # clear
            for char in value:
                await page.type(selector, char, delay=random.randint(50, 200))
            await asyncio.sleep(random.uniform(0.2, 0.6))
        log.info("browser.fill_form", field_count=len(fields),
                 elapsed_s=round(time.monotonic() - t0, 2))

    async def click_element(self, page: Any, selector: str,
                            wait_after: bool = True) -> None:
        t0 = time.monotonic()
        element = await page.query_selector(selector)
        if not element:
            log.warning("browser.click_element", selector=selector, error="not found")
            return
        box = await element.bounding_box()
        if box:
            x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
            y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)
            await page.mouse.move(x, y, steps=random.randint(5, 15))
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.click(x, y)
        else:
            await element.click()
        if wait_after:
            await asyncio.sleep(random.uniform(0.5, 1.5))
        log.info("browser.click", selector=selector,
                 elapsed_s=round(time.monotonic() - t0, 2))

    # ── Data extraction ───────────────────────────────────────────────────────

    async def extract_data(self, page: Any, selectors: dict) -> dict:
        t0 = time.monotonic()
        results = {}
        for field_name, selector in selectors.items():
            el = await page.query_selector(selector)
            results[field_name] = await el.inner_text() if el else None
        log.info("browser.extract", field_count=len(selectors),
                 elapsed_s=round(time.monotonic() - t0, 2))
        return results

    async def screenshot(self, page: Any, path: str | None = None) -> bytes:
        t0 = time.monotonic()
        opts: dict[str, Any] = {"full_page": True}
        if path:
            opts["path"] = path
        data = await page.screenshot(**opts)
        log.info("browser.screenshot", path=path, size_kb=round(len(data) / 1024, 1),
                 elapsed_s=round(time.monotonic() - t0, 2))
        return data

    # ── High-level workflows ──────────────────────────────────────────────────

    async def create_account(self, url: str, fields: dict,
                             submit_selector: str) -> dict:
        """Navigate to URL, fill registration form, submit, return result."""
        t0 = time.monotonic()
        log.info("browser.create_account", url=url)
        page = await self.navigate(url)
        await self.fill_form(page, fields)
        await self.click_element(page, submit_selector)
        await asyncio.sleep(random.uniform(2.0, 4.0))  # wait for redirect/response

        result = {
            "url": page.url,
            "title": await page.title(),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }

        # CAPTCHA detection — placeholder for 2captcha/capsolver integration
        content = await page.content()
        if "captcha" in content.lower():
            log.warning("browser.captcha_detected", url=page.url)
            result["captcha_detected"] = True
            # TODO: integrate 2captcha/capsolver API
            # api_key = os.environ.get("CAPTCHA_API_KEY")
            # if api_key: result.update(await _solve_captcha(page, api_key))

        log.info("browser.create_account.done", **result)
        await page.close()
        return result

    async def scrape_page(self, url: str, selectors: dict) -> dict:
        """Navigate to URL, extract data from selectors, return dict."""
        t0 = time.monotonic()
        log.info("browser.scrape", url=url)
        page = await self.navigate(url)
        data = await self.extract_data(page, selectors)
        data["_url"] = url
        data["_elapsed_s"] = round(time.monotonic() - t0, 2)
        log.info("browser.scrape.done", url=url, fields=len(selectors),
                 elapsed_s=data["_elapsed_s"])
        await page.close()
        return data
