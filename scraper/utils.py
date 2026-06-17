"""Shared helper functions for Selenium job scrapers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

load_dotenv()
logger = logging.getLogger(__name__)


def get_driver(headless: bool = True) -> Any:
    """Create a configured undetected Chrome WebDriver.

    Args:
        headless: Whether Chrome should run headlessly.

    Returns:
        Configured Selenium-compatible Chrome driver.
    """

    browser_path = os.getenv("CHROME_BINARY") or _detect_browser_executable_path()
    version_main = os.getenv("CHROME_VERSION_MAIN") or _detect_chrome_major_version(browser_path)
    last_error: Exception | None = None
    for attempt in range(2):
        options = _build_chrome_options(headless, browser_path)
        try:
            chrome_kwargs: dict[str, Any] = {"options": options}
            if version_main:
                chrome_kwargs["version_main"] = int(version_main)
            if browser_path:
                chrome_kwargs["browser_executable_path"] = browser_path
            driver = uc.Chrome(**chrome_kwargs)
            driver.set_page_load_timeout(45)
            return driver
        except Exception as exc:
            last_error = exc
            logger.exception("Failed to create Chrome driver on attempt %s", attempt + 1)
            if attempt == 0 and _is_chromedriver_cache_collision(exc):
                _remove_stale_undetected_chromedriver()
                time.sleep(1)
                continue
            if attempt == 0 and _is_chrome_startup_race(exc):
                time.sleep(2)
                continue
            break
    raise RuntimeError(f"Unable to start Chrome driver: {last_error}") from last_error


def _build_chrome_options(headless: bool, browser_path: str | None = None) -> Any:
    """Build Chrome options for each startup attempt."""

    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=en-US")
    if browser_path:
        options.binary_location = browser_path
    user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    return options


def _is_chromedriver_cache_collision(exc: Exception) -> bool:
    """Detect undetected-chromedriver's Windows cached executable rename race."""

    return getattr(exc, "winerror", None) == 183 or "WinError 183" in str(exc)


def _is_chrome_startup_race(exc: Exception) -> bool:
    """Detect transient Chrome startup failures that often succeed on retry."""

    message = str(exc).lower()
    return "chrome not reachable" in message or "cannot connect to chrome" in message or "session not created" in message


def _remove_stale_undetected_chromedriver() -> None:
    """Remove stale undetected-chromedriver cache files that block Windows renames."""

    cache_dir = Path(os.getenv("APPDATA", "")) / "undetected_chromedriver"
    targets = [
        cache_dir / "undetected_chromedriver.exe",
        cache_dir / "undetected" / "chromedriver-win32" / "chromedriver.exe",
    ]
    for target in targets:
        try:
            if target.exists():
                target.unlink()
                logger.info("Removed stale undetected-chromedriver cache file: %s", target)
        except Exception as exc:
            logger.warning("Could not remove stale undetected-chromedriver cache file %s: %s", target, exc)


def _detect_browser_executable_path() -> str | None:
    """Detect an installed Chrome/Chromium executable path."""

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for browser_path in candidates:
        if os.path.exists(browser_path):
            return browser_path
    return None


def _detect_chrome_major_version(browser_path: str | None = None) -> str | None:
    """Detect installed Chrome, Chromium, or Edge major version.

    Args:
        None.

    Returns:
        Browser major version string when detected, otherwise None.
    """

    candidates = [browser_path] if browser_path else [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for browser_path in candidates:
        if not browser_path or not os.path.exists(browser_path):
            continue
        try:
            completed = subprocess.run(
                [browser_path, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            match = re.search(r"(\d+)\.", completed.stdout or completed.stderr)
            if match:
                major = match.group(1)
                logger.info("Detected browser major version %s from %s", major, browser_path)
                return major
        except Exception as exc:
            logger.debug("Could not detect browser version from %s: %s", browser_path, exc)
    return None


def safe_find(driver: Any, by: By, selector: str, timeout: int = 10) -> WebElement | None:
    """Find an element with WebDriverWait and return None on failure.

    Args:
        driver: Selenium WebDriver instance.
        by: Selenium locator strategy.
        selector: Locator selector.
        timeout: Wait timeout in seconds.

    Returns:
        WebElement if found, otherwise None.
    """

    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        logger.warning("Element not found: %s=%s", by, selector)
        return None


def clean_text(text: str) -> str:
    """Normalize whitespace in scraped text.

    Args:
        text: Raw scraped text.

    Returns:
        Clean text with collapsed whitespace.
    """

    return re.sub(r"\s+", " ", text or "").strip()


def _dedupe_text(value: Any) -> str:
    """Normalize text fields for duplicate comparisons."""

    return re.sub(r"\W+", " ", str(value or "").casefold()).strip()


def _job_content_key(job: dict[str, Any]) -> str:
    """Create a fallback duplicate key from visible job content."""

    title = _dedupe_text(job.get("job_title"))
    company = _dedupe_text(job.get("company"))
    location_text = re.split(r"·|Â·|Â|Ā|\||\b\d+\s+(?:minute|hour|day|week|month)s?\s+ago\b", str(job.get("location") or ""), maxsplit=1)[0]
    location = _dedupe_text(location_text)
    return f"{job.get('source')}::{title}::{company}::{location}"


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate jobs by stable job identity while preserving order.

    Args:
        jobs: Job dictionaries with a url field.

    Returns:
        Deduplicated job list.
    """

    seen: set[str] = set()
    seen_content: set[str] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        source = str(job.get("source") or "").strip().lower()
        job_id = str(job.get("job_id") or "").strip()
        url = str(job.get("url") or "").strip()
        key = f"{source}::{job_id}" if job_id else url
        if not key:
            key = f"{job.get('company')}::{job.get('job_title')}::{job.get('location')}"
        content_key = _job_content_key(job)
        if key in seen or content_key in seen_content:
            continue
        seen.add(key)
        seen_content.add(content_key)
        unique.append(job)
    return unique


def env_headless(default: bool = True) -> bool:
    """Read HEADLESS from the environment.

    Args:
        default: Fallback value when HEADLESS is not set.

    Returns:
        Boolean headless setting.
    """

    value = os.getenv("HEADLESS")
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}
