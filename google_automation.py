"""
Google One automation using Selenium with CDP Stealth & Pixel 10 Pro Emulation.

Logs into a Gmail account, navigates to Google One, detects the
12-month free Gemini Pro / AI Premium offer, and returns the activation link.
"""

import logging
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from device_simulator import DeviceProfile

logger = logging.getLogger(__name__)


# ── Driver factory ────────────────────────────────────────────────────────────

def _build_driver(profile: DeviceProfile) -> webdriver.Chrome:
    """Return a hardened, stealth-patched Chrome WebDriver for Pixel 10 Pro."""
    options = Options()

    if getattr(config, "HEADLESS", True):
        options.add_argument("--headless=new")

    # Cloud / Replit stability arguments
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=412,915")
    options.add_argument(f"--user-agent={profile.user_agent}")

    # Replit / Linux binary support
    chrome_bin = os.environ.get("CHROME_BIN") or getattr(config, "CHROME_BIN", None)
    if chrome_bin and os.path.exists(chrome_bin):
        options.binary_location = chrome_bin

    # Anti-bot detection switches
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)

    # ── CDP Stealth & Client Hints Injection ──────────────────────────────────
    # 1. Enable Network and inject Pixel 10 Pro Client Hints
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setUserAgentOverride", profile.emulation_params())

    # 2. Patch navigator to evade "This browser or app may not be secure"
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 5
                });
            """
        },
    )

    driver.implicitly_wait(getattr(config, "IMPLICIT_WAIT", 5))
    driver.set_page_load_timeout(getattr(config, "PAGE_LOAD_TIMEOUT", 30))
    return driver


# ── Login helper ──────────────────────────────────────────────────────────────

def _wait_for(driver: webdriver.Chrome, by: str, value: str, timeout: int = 15) -> object:
    """Return element after waiting for it to become visible and clickable."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def _gmail_login(driver: webdriver.Chrome, email: str, password: str) -> bool:
    """
    Perform Google account login with stealth and 2FA detection.
    """
    login_url = getattr(
        config,
        "GMAIL_LOGIN_URL",
        "https://accounts.google.com/ServiceLogin?service=accountsettings&continue=https://myaccount.google.com/",
    )

    try:
        logger.info("Opening Google login page...")
        driver.get(login_url)
        time.sleep(2)

        # ── Email Step ────────────────────────────────────────────────────────
        email_field = _wait_for(driver, By.CSS_SELECTOR, 'input[type="email"]')
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(1)

        next_btn = _wait_for(driver, By.ID, "identifierNext")
        next_btn.click()
        time.sleep(3)

        # ── Password Step ─────────────────────────────────────────────────────
        password_field = _wait_for(
            driver, By.CSS_SELECTOR, 'input[type="password"], input[name="Passwd"]'
        )
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)

        pw_next = _wait_for(driver, By.ID, "passwordNext")
        pw_next.click()
        time.sleep(4)

        # ── Check for 2FA / Verification Challenge ───────────────────────────
        # Wait up to 30s in case Google prompts the user to tap "Yes" on phone
        start_wait = time.time()
        while time.time() - start_wait < 30:
            current_url = driver.current_url
            parsed = urlparse(current_url)
            hostname = parsed.hostname or ""
            path = parsed.path or ""

            # Logged in successfully
            if (
                hostname == "myaccount.google.com"
                or (hostname.endswith(".google.com") and "/u/" in path)
                or "one.google.com" in hostname
            ):
                logger.info("Login succeeded for %s", email)
                return True

            # If user is on a challenge screen, log and wait for approval
            if "challenge" in path or "signin/v2/challenge" in current_url:
                logger.info("2FA / Security challenge detected. Waiting for approval on user's device...")
                time.sleep(3)
                continue

            # Check for explicit error message
            try:
                error_el = driver.find_element(
                    By.CSS_SELECTOR, '[jsname="B34EJ"], [aria-live="assertive"], .o6cuMc'
                )
                if error_el.text:
                    logger.warning("Google login rejected: %s", error_el.text)
                    return False
            except NoSuchElementException:
                pass

            # If redirected away from signin flow, consider logged in
            if not (hostname == "accounts.google.com" and path.startswith("/signin")):
                return True

            time.sleep(2)

        return False

    except TimeoutException as exc:
        logger.error("Timeout during Google login: %s", exc)
        return False
    except WebDriverException as exc:
        logger.error("WebDriver error during login: %s", exc)
        return False


# ── Offer detection ───────────────────────────────────────────────────────────

def _extract_payment_link(driver: webdriver.Chrome) -> Optional[str]:
    """
    Scan page for Pixel Gemini Pro / AI Premium offer or checkout URLs.
    """
    keywords = getattr(
        config,
        "GEMINI_OFFER_KEYWORDS",
        ["gemini", "gemini advanced", "gemini pro", "ai premium", "12 months", "1 year", "pixel offer", "claim offer"],
    )

    all_links = driver.find_elements(By.TAG_NAME, "a")

    # Strategy 1: Anchor text or aria-label keyword match
    for link in all_links:
        try:
            aria = link.get_attribute("aria-label") or ""
            text = (link.text + " " + aria).lower()
            href = link.get_attribute("href") or ""
            if any(kw in text for kw in keywords) and href and href.startswith("http"):
                logger.info("Found offer link via text/label match: %s", href)
                return href
        except Exception:
            continue

    # Strategy 2: URL pattern match (Google One checkout / redemption URLs)
    url_patterns = re.compile(
        r"(one\.google\.com/promo|one\.google\.com/benefits|one\.google\.com/offer|gemini|ai-premium|redeem|checkout)",
        re.IGNORECASE,
    )
    for link in all_links:
        try:
            href = link.get_attribute("href") or ""
            if url_patterns.search(href) and not href.endswith("/home"):
                logger.info("Found offer link via URL pattern: %s", href)
                return href
        except Exception:
            continue

    # Strategy 3: CTA buttons (Claim / Upgrade button)
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, [role='button']")
    for btn in buttons:
        try:
            text = btn.text.lower()
            if any(kw in text for kw in keywords):
                try:
                    parent_link = btn.find_element(By.XPATH, "ancestor::a")
                    href = parent_link.get_attribute("href") or ""
                    if href:
                        return href
                except NoSuchElementException:
                    pass
                return driver.current_url
        except Exception:
            continue

    return None


def _navigate_google_one(driver: webdriver.Chrome) -> Optional[str]:
    """
    Navigate to Google One endpoints to search for the promotional offer.
    """
    endpoints = [
        getattr(config, "GOOGLE_ONE_OFFERS_URL", "https://one.google.com/benefits"),
        getattr(config, "GOOGLE_ONE_URL", "https://one.google.com/home"),
        "https://one.google.com/about/plans",
    ]

    for url in endpoints:
        try:
            logger.info("Navigating to %s", url)
            driver.get(url)
            time.sleep(4)

            # Dismiss consent banners if present
            for selector in (
                '[aria-label="Accept all"]',
                'button[jsname="higCR"]',
                '[data-action="accept"]',
            ):
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    btn.click()
                    time.sleep(1)
                    break
                except NoSuchElementException:
                    pass

            link = _extract_payment_link(driver)
            if link:
                return link

        except (TimeoutException, WebDriverException) as exc:
            logger.warning("Error accessing %s: %s", url, exc)

    return None


# ── Public API ────────────────────────────────────────────────────────────────

class GoogleAutomationError(Exception):
    """Raised when automation encounters an unrecoverable error."""


def check_gemini_offer(email: str, password: str, device: DeviceProfile) -> Optional[str]:
    """
    Main entry point.

    Logs into Google with the device profile, searches for the Gemini promo,
    and returns the link.
    """
    driver: Optional[webdriver.Chrome] = None
    try:
        logger.info("Starting WebDriver for session %s on model %s", device.session_id, device.model)
        driver = _build_driver(device)

        logged_in = _gmail_login(driver, email, password)
        if not logged_in:
            raise GoogleAutomationError(
                "Login failed. Google may have blocked the sign-in, credentials may be incorrect, or 2FA was not approved in time."
            )

        offer_link = _navigate_google_one(driver)
        return offer_link

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
