"""LinkedIn job scraper using Selenium with credential-based login."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
import time
from typing import Any
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.utils import clean_text, deduplicate_jobs, env_headless, get_driver, safe_find

load_dotenv()
logger = logging.getLogger(__name__)


def _canonical_linkedin_job_url(raw_url: str | None) -> str | None:
    """Convert LinkedIn card/detail URLs into stable job view URLs."""

    if not raw_url:
        return None
    absolute_url = urljoin("https://www.linkedin.com", raw_url)
    parsed = urlparse(absolute_url)
    path_match = re.search(r"/jobs/view/(?:.*?-)?(\d+)(?:/|$)", parsed.path)
    if path_match:
        return f"https://www.linkedin.com/jobs/view/{path_match.group(1)}/"

    query = parse_qs(parsed.query)
    current_job_id = query.get("currentJobId") or query.get("jobId")
    if current_job_id and current_job_id[0]:
        return f"https://www.linkedin.com/jobs/view/{current_job_id[0]}/"

    return absolute_url.split("?")[0]


def _clean_linkedin_location(text: str) -> str:
    """Keep the actual LinkedIn location and drop card metadata."""

    return re.split(r"·|Â·|Â|Ā|\||\b\d+\s+(?:minute|hour|day|week|month)s?\s+ago\b", clean_text(text), maxsplit=1)[0].strip()


def _collect_search_jobs(driver: Any) -> list[dict[str, Any]]:
    """Extract job records from the current LinkedIn search page."""

    script = """
        const cards = Array.from(document.querySelectorAll(
            ".job-card-container, .jobs-search-results__list-item, [data-job-id], [data-occludable-job-id]"
        ));
        const text = (root, selectors) => {
            for (const selector of selectors) {
                const node = root.querySelector(selector);
                if (node && node.innerText && node.innerText.trim()) return node.innerText.trim();
            }
            return "";
        };
        const attr = (root, selectors, name) => {
            for (const selector of selectors) {
                const node = root.querySelector(selector);
                if (node && node.getAttribute(name)) return node.getAttribute(name);
            }
            return "";
        };
        return cards.map((card) => {
            const href = attr(card, [
                "a[href*='/jobs/view/']",
                "a[href*='currentJobId=']",
                "a.job-card-container__link",
                "a.job-card-list__title--link"
            ], "href");
            const jobId = card.getAttribute("data-job-id") || card.getAttribute("data-occludable-job-id") || "";
            const title = text(card, [
                ".job-card-list__title",
                ".job-card-container__link",
                "a[href*='/jobs/view/']",
                "strong"
            ]);
            const company = text(card, [
                ".artdeco-entity-lockup__subtitle",
                ".job-card-container__company-name",
                ".job-card-container__primary-description",
                "[class*='company']"
            ]);
            const location = text(card, [
                ".artdeco-entity-lockup__caption",
                ".job-card-container__metadata-item",
                "[class*='location']"
            ]);
            const snippet = text(card, [
                ".job-card-container__description",
                ".job-card-list__insight",
                ".job-card-container__metadata-wrapper"
            ]);
            return { href, jobId, title, company, location, snippet };
        }).filter((item) => item.href || item.jobId || item.title);
    """
    raw_jobs = driver.execute_script(script) or []
    jobs: list[dict[str, Any]] = []
    for raw_job in raw_jobs:
        href = str(raw_job.get("href") or "").strip()
        job_id = str(raw_job.get("jobId") or "").strip()
        url = _canonical_linkedin_job_url(href) if href else None
        if not url and job_id:
            url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        title = clean_text(str(raw_job.get("title") or ""))
        company = clean_text(str(raw_job.get("company") or ""))
        location_text = _clean_linkedin_location(str(raw_job.get("location") or ""))
        snippet = clean_text(str(raw_job.get("snippet") or ""))
        if not any((title, company, url)):
            continue

        job = _job_schema()
        job["job_id"] = url.rstrip("/").split("/")[-1] if url else job_id or None
        job["job_title"] = title
        job["company"] = company
        job["location"] = location_text
        job["description"] = clean_text(" ".join(part for part in [title, company, location_text, snippet] if part))
        job["url"] = url
        jobs.append(job)
    return deduplicate_jobs(jobs)


def _job_schema() -> dict[str, Any]:
    """Create a blank LinkedIn job record.

    Args:
        None.

    Returns:
        Empty job schema dictionary.
    """

    return {
        "job_id": None,
        "job_title": None,
        "company": None,
        "location": None,
        "description": None,
        "url": None,
        "date_posted": None,
        "salary": None,
        "source": "linkedin",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def _login(driver: Any, errors: list[str]) -> bool:
    """Log in to LinkedIn using environment credentials.

    Args:
        driver: Selenium WebDriver instance.
        errors: Mutable list receiving descriptive errors.

    Returns:
        True if login flow appears successful.
    """

    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        errors.append("LinkedIn credentials are missing in environment variables.")
        return False

    try:
        driver.get("https://www.linkedin.com/login")
        WebDriverWait(driver, 12).until(
            lambda d: "linkedin.com/feed" in d.current_url
            or "linkedin.com/jobs" in d.current_url
            or d.find_elements(By.ID, "username")
            or d.find_elements(By.CSS_SELECTOR, "input[name='session_key']")
        )
        if "linkedin.com/feed" in driver.current_url or "linkedin.com/jobs" in driver.current_url:
            logger.info("LinkedIn session is already authenticated")
            return True
        email_input = safe_find(driver, By.ID, "username", 8) or safe_find(driver, By.CSS_SELECTOR, "input[name='session_key']", 8)
        password_input = safe_find(driver, By.ID, "password", 8) or safe_find(driver, By.CSS_SELECTOR, "input[name='session_password']", 8)
        if not email_input or not password_input:
            errors.append(
                "LinkedIn login form was not available. "
                f"Current URL: {driver.current_url}. "
                "Try HEADLESS=false and, if prompted, complete LinkedIn verification manually."
            )
            return False
        email_input.clear()
        email_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)
        submit = safe_find(driver, By.CSS_SELECTOR, "button[type='submit']", 10)
        if submit:
            submit.click()
        WebDriverWait(driver, 25).until(
            lambda d: "feed" in d.current_url
            or "jobs" in d.current_url
            or "checkpoint" in d.current_url
            or "challenge" in d.current_url
        )
        if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            errors.append("LinkedIn checkpoint or verification blocked automated login. Use HEADLESS=false and complete verification manually.")
            return False
        return True
    except Exception as exc:
        logger.exception("LinkedIn login failed")
        errors.append(f"LinkedIn login failed: {exc}")
        return False


def scrape_linkedin_jobs(
    job_title: str,
    location: str,
    max_results: int = 20,
    headless: bool | None = None,
    errors: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Scrape LinkedIn jobs after login.

    Args:
        job_title: Search query job title.
        location: Search location.
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
        if not _login(driver, collected_errors):
            return jobs

        page_start = 0
        page_count = 0
        max_pages = max(1, (max_results + 24) // 25 + 2)
        seen_urls: set[str] = set()
        while len(jobs) < max_results and page_count < max_pages:
            page_count += 1
            search_url = (
                "https://www.linkedin.com/jobs/search/"
                f"?keywords={quote_plus(job_title)}&location={quote_plus(location)}&start={page_start}"
            )
            driver.get(search_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".job-card-container, .jobs-search-results__list-item")))
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.8));")
                time.sleep(0.5)
            page_jobs = _collect_search_jobs(driver)
            if not page_jobs:
                break
            for job in page_jobs:
                if len(jobs) >= max_results:
                    break
                job_url = str(job.get("url") or "")
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)
                jobs.append(job)
            page_start += 25
    except Exception as exc:
        logger.exception("LinkedIn scraping failed")
        collected_errors.append(f"LinkedIn scraping failed: {exc}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as exc:
                logger.warning("Failed to close LinkedIn driver: %s", exc)
    return deduplicate_jobs(jobs)[:max_results]
