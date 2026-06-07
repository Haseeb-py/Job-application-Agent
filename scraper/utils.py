"""Shared helper functions for Selenium job scrapers."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any

from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException, WebDriverException
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

    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=en-US")
    user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    version_main = os.getenv("CHROME_VERSION_MAIN") or _detect_chrome_major_version()
    try:
        if version_main:
            driver = uc.Chrome(options=options, version_main=int(version_main))
        else:
            driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(45)
        return driver
    except WebDriverException as exc:
        logger.exception("Failed to create Chrome driver")
        raise RuntimeError(f"Unable to start Chrome driver: {exc}") from exc


def _detect_chrome_major_version() -> str | None:
    """Detect installed Chrome or Edge major version on Windows.

    Args:
        None.

    Returns:
        Browser major version string when detected, otherwise None.
    """

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for browser_path in candidates:
        if not os.path.exists(browser_path):
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


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate jobs by URL while preserving order.

    Args:
        jobs: Job dictionaries with a url field.

    Returns:
        Deduplicated job list.
    """

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        url = str(job.get("url") or "").strip()
        key = url or f"{job.get('company')}::{job.get('job_title')}::{job.get('location')}"
        if key in seen:
            continue
        seen.add(key)
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
