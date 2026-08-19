"""
Android Pixel 10 Pro device simulator.

Uses authentic production dump values from Google Pixel 10 Pro (blazer).
"""

import random
import string
import uuid
from dataclasses import dataclass, field

import config


# ── Helpers ───────────────────────────────────────────────────────────────────

def _luhn_checksum(number: str) -> int:
    """Return the Luhn check digit for a numeric string."""
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def _generate_imei() -> str:
    """Generate a syntactically valid IMEI with Pixel TAC prefix."""
    tac = random.choice(["350444", "353594", "352864"]) + "".join(random.choices(string.digits, k=2))
    serial = "".join(random.choices(string.digits, k=6))
    partial = tac + serial
    check_digit = (10 - _luhn_checksum(partial + "0")) % 10
    return partial + str(check_digit)


def _generate_android_id() -> str:
    """Generate a 16-character hex Android ID."""
    return "".join(random.choices("0123456789abcdef", k=16))


def _random_chrome_patch() -> str:
    """Return a realistic Chrome version string."""
    major = getattr(config, "CHROME_MAJOR_VERSION", 132)
    minor = 0
    build = random.randint(6834, 6870)
    patch = random.randint(80, 160)
    return f"{major}.{minor}.{build}.{patch}"


# ── Device profile dataclass ──────────────────────────────────────────────────

@dataclass
class DeviceProfile:
    imei: str
    android_id: str
    chrome_version: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Authentic Pixel 10 Pro production dump properties
    model: str = "Pixel 10 Pro"
    codename: str = "blazer"
    brand: str = "google"
    manufacturer: str = "Google"
    android_version: str = "17"
    android_sdk: str = "37"
    build_id: str = "CP2A.260805.005"
    incremental: str = "15828068"
    security_patch: str = "2026-08-05"
    device_fingerprint: str = "google/blazer/blazer:17/CP2A.260805.005/15828068:user/release-keys"

    # Display / Hardware Specs (Pixel 10 Pro: 1280x2856 @ 3x scale)
    screen_width: int = 412
    screen_height: int = 915
    device_scale_factor: float = 3.0

    @property
    def user_agent(self) -> str:
        return (
            f"Mozilla/5.0 (Linux; Android {self.android_version}; {self.model} Build/{self.build_id}; wv) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
            f"Chrome/{self.chrome_version} Mobile Safari/537.36"
        )

    def as_headers(self) -> dict:
        """
        Return modern HTTP headers including User-Agent Client Hints.
        """
        major_v = self.chrome_version.split(".")[0]
        return {
            "User-Agent": self.user_agent,
            "sec-ch-ua": f'"Chromium";v="{major_v}", "Google Chrome";v="{major_v}", "Not=A?Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-ch-ua-platform-version": f'"{self.android_version}.0.0"',
            "sec-ch-ua-model": f'"{self.model}"',
            "sec-ch-ua-arch": '"arm64"',
            "sec-ch-ua-bitness": '"64"',
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
        }

    def emulation_params(self) -> dict:
        """Return parameters for Chrome DevTools Protocol / Playwright / Selenium CDP."""
        return {
            "userAgent": self.user_agent,
            "viewport": {
                "width": self.screen_width,
                "height": self.screen_height,
                "deviceScaleFactor": self.device_scale_factor,
                "isMobile": True,
                "hasTouch": True,
            },
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Chromium", "version": self.chrome_version.split(".")[0]},
                    {"brand": "Google Chrome", "version": self.chrome_version.split(".")[0]},
                    {"brand": "Not=A?Brand", "version": "24"}
                ],
                "fullVersion": self.chrome_version,
                "platform": "Android",
                "platformVersion": f"{self.android_version}.0.0",
                "architecture": "arm64",
                "model": self.model,
                "mobile": True,
                "bitness": "64",
                "wow64": False
            }
        }

    def summary(self) -> str:
        """Human-readable summary for Telegram messages."""
        return (
            f"Device: {self.manufacturer} {self.model} ({self.codename})\n"
            f"Android: {self.android_version} (API {self.android_sdk})\n"
            f"Build: {self.build_id} ({self.security_patch})\n"
            f"Fingerprint: {self.device_fingerprint}\n"
            f"IMEI: {self.imei}\n"
            f"Android ID: {self.android_id}\n"
            f"Chrome: {self.chrome_version}\n"
            f"Session: {self.session_id[:8]}..."
        )


# ── Public factory ────────────────────────────────────────────────────────────

def create_device_profile() -> DeviceProfile:
    """
    Create a fresh Pixel 10 Pro device profile with unique per-session
    identifiers and authentic dump properties.
    """
    chrome_version = _random_chrome_patch()

    return DeviceProfile(
        imei=_generate_imei(),
        android_id=_generate_android_id(),
        chrome_version=chrome_version,
    )
