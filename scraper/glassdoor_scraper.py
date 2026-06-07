"""Glassdoor public job scraper using Selenium rendering and BeautifulSoup parsing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.utils import clean_text, deduplicate_jobs, env_headless, get_driver

logger = logging.getLogger(__name__)


def _dismiss_popups(driver: Any, errors: list[str]) -> None:
    """Dismiss cookie banners and modal pop-ups when visible.

    Args:
        driver: Selenium WebDriver instance.
        errors: Mutable list receiving descriptive errors.

    Returns:
        None.
    """

    selectors = [
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "[data-test='modal-close']",
        "#onetrust-accept-btn-handler",
        "button.CloseButton",
        ".modal_closeIcon",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    element.click()
                    break
        except Exception as exc:
            logger.debug("Popup selector failed %s: %s", selector, exc)
            errors.append(f"Glassdoor popup dismissal skipped for {selector}: {exc}")


def _extract_jobs(html: str, max_results: int) -> list[dict[str, Any]]:
    """Extract public job cards from rendered Glassdoor HTML.

    Args:
        html: Rendered page source.
        max_results: Maximum jobs to return.

    Returns:
        List of normalized job dictionaries.
    """

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(
        "[data-test='jobListing'], "
        "li[data-test^='jobListing'], "
        "li.react-job-listing, "
        ".JobsList_jobListItem__JBBUV, "
        "li[class*='job'], "
        "div[class*='JobCard']"
    )
    jobs: list[dict[str, Any]] = []
    for card in cards[:max_results]:
        link = card.select_one("a[href*='/job-listing/'], a[href*='/partner/jobListing.htm'], a[href*='/Job/']")
        title = card.select_one("[data-test='job-title'], a[data-test='job-link'], .JobCard_jobTitle__GLyJ1, a[class*='JobTitle']")
        company = card.select_one("[data-test='employer-name'], .EmployerProfile_compactEmployerName__LE242, div[class*='Employer']")
        location = card.select_one("[data-test='job-location'], .JobCard_location__Ds1fM, div[class*='Location']")
        snippet = card.select_one("[data-test='descSnippet'], .JobCard_jobDescriptionSnippet__yWW8q, div[class*='Description']")
        url = urljoin("https://www.glassdoor.com", link.get("href")) if link and link.get("href") else None
        job = {
            "job_id": url.rstrip("/").split("/")[-1] if url else None,
            "job_title": clean_text(title.get_text(" ") if title else ""),
            "company": clean_text(company.get_text(" ") if company else ""),
            "location": clean_text(location.get_text(" ") if location else ""),
            "description": clean_text(snippet.get_text(" ") if snippet else ""),
            "url": url,
            "date_posted": None,
            "salary": None,
            "source": "glassdoor",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        if any(job.get(field) for field in ("job_title", "company", "url")):
            jobs.append(job)
    return jobs


def scrape_glassdoor_jobs(
    job_title: str,
    location: str,
    max_results: int = 20,
    headless: bool | None = None,
    errors: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Scrape public Glassdoor job listings without login.

    Args:
        job_title: Search query job title.
        location: Search location. Glassdoor public URL support varies by region.
        max_results: Maximum number of jobs to return.
        headless: Optional Chrome headless override.
        errors: Optional mutable list receiving descriptive scraper errors.

    Returns:
        List of normalized job dictionaries.
    """

    collected_errors = errors if errors is not None else []
    jobs: list[dict[str, Any]] = []
    driver = None
    try:
        driver = get_driver(env_headless() if headless is None else headless)
        url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(job_title)}&locT=C"
        if location:
            url = f"{url}&locKeyword={quote_plus(location)}"
        driver.get(url)
        _dismiss_popups(driver, collected_errors)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        _dismiss_popups(driver, collected_errors)
        jobs = _extract_jobs(driver.page_source, max_results)
        if not jobs:
            logger.warning("Glassdoor returned no publicly visible jobs for %s in %s", job_title, location)
    except Exception as exc:
        logger.exception("Glassdoor scraping failed")
        collected_errors.append(f"Glassdoor scraping failed: {exc}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as exc:
                logger.warning("Failed to close Glassdoor driver: %s", exc)
    return deduplicate_jobs(jobs)[:max_results]
