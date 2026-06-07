"""LinkedIn job scraper using Selenium with credential-based login."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any
from urllib.parse import quote_plus

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.utils import clean_text, deduplicate_jobs, env_headless, get_driver, safe_find

load_dotenv()
logger = logging.getLogger(__name__)


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
        while len(jobs) < max_results:
            search_url = (
                "https://www.linkedin.com/jobs/search/"
                f"?keywords={quote_plus(job_title)}&location={quote_plus(location)}&start={page_start}"
            )
            driver.get(search_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".job-card-container, .jobs-search-results__list-item")))
            cards = driver.find_elements(By.CSS_SELECTOR, ".job-card-container, .jobs-search-results__list-item")
            if not cards:
                break
            for card in cards:
                if len(jobs) >= max_results:
                    break
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    card.click()
                    WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-unified-top-card__job-title, h1")))
                    job = _job_schema()
                    title_el = safe_find(driver, By.CSS_SELECTOR, ".jobs-unified-top-card__job-title, h1", 8)
                    company_el = safe_find(driver, By.CSS_SELECTOR, ".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name", 8)
                    location_el = safe_find(driver, By.CSS_SELECTOR, ".jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__primary-description-container span", 8)
                    desc_el = safe_find(driver, By.CSS_SELECTOR, ".jobs-description__content, .jobs-box__html-content", 10)
                    date_el = safe_find(driver, By.CSS_SELECTOR, "time, .jobs-unified-top-card__posted-date", 4)
                    job["job_title"] = clean_text(title_el.text if title_el else "")
                    job["company"] = clean_text(company_el.text if company_el else "")
                    job["location"] = clean_text(location_el.text if location_el else "")
                    job["description"] = clean_text(desc_el.text if desc_el else "")
                    job["date_posted"] = clean_text(date_el.text if date_el else "")
                    job["url"] = driver.current_url.split("?")[0]
                    job["job_id"] = job["url"].rstrip("/").split("/")[-1] if job["url"] else None
                    jobs.append(job)
                except Exception as exc:
                    logger.exception("Failed to scrape LinkedIn job card")
                    collected_errors.append(f"LinkedIn job card failed: {exc}")
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
