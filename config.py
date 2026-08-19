"""
Configuration and constants for the Pixel 10 Pro Google One Gemini Bot.
"""

import os

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ── Device specs – Google Pixel 10 Pro (blazer) ──────────────────────────────
DEVICE_MODEL = "Pixel 10 Pro"
DEVICE_CODENAME = "blazer"
DEVICE_BRAND = "google"
DEVICE_MANUFACTURER = "Google"
ANDROID_VERSION = "17"
ANDROID_SDK = "37"
BUILD_ID = "CP2A.260805.005"
INCREMENTAL = "15828068"
SECURITY_PATCH = "2026-08-05"
DEVICE_FINGERPRINT = "google/blazer/blazer:17/CP2A.260805.005/15828068:user/release-keys"

# Browser Version
CHROME_MAJOR_VERSION = 138
CHROME_VERSION = "138.0.7204.98"

# User-Agent templates
USER_AGENT_TEMPLATES = [
    (
        "Mozilla/5.0 (Linux; Android {android}; {model} Build/{build}; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Version/4.0 Chrome/{chrome} Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android {android}; {model} Build/{build}) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/{chrome} Mobile Safari/537.36"
    ),
]

# ── Google URLs ───────────────────────────────────────────────────────────────
GMAIL_LOGIN_URL = (
    "https://accounts.google.com/ServiceLogin?"
    "service=accountsettings&continue=https://myaccount.google.com/"
)
GOOGLE_ONE_URL = "https://one.google.com/home"
GOOGLE_ONE_OFFERS_URL = "https://one.google.com/benefits"
GOOGLE_ONE_PLANS_URL = "https://one.google.com/about/plans"

# ── Gemini offer detection keywords ──────────────────────────────────────────
GEMINI_OFFER_KEYWORDS = [
    "gemini pro",
    "gemini advanced",
    "ai premium",
    "12 month",
    "12-month",
    "1 year",
    "free trial",
    "activate",
    "claim offer",
    "redeem",
    "get offer",
    "pixel offer",
]

# ── Selenium / WebDriver ──────────────────────────────────────────────────────
WEBDRIVER_TIMEOUT = 30          # seconds – explicit wait
IMPLICIT_WAIT = 5               # seconds
PAGE_LOAD_TIMEOUT = 45          # seconds
HEADLESS = True                 # always headless on Replit
CHROME_BIN = os.environ.get("CHROME_BIN", "")

# ── Session storage ───────────────────────────────────────────────────────────
# In-memory dictionary keyed by Telegram chat_id
SESSION_STORE: dict = {}

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
