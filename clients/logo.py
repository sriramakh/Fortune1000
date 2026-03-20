import logging

import aiohttp

from config import GOOGLE_FAVICON_URL, LOGO_DEV_TOKEN

logger = logging.getLogger(__name__)


async def get_logo_url(domain: str) -> str:
    """Get a logo URL for a company domain.

    Uses logo.dev if token is available, otherwise Google favicon service.
    """
    if not domain:
        return ""

    # Clean domain
    domain = domain.strip().lower()
    if domain.startswith("http"):
        domain = domain.split("//", 1)[-1].split("/")[0]

    if LOGO_DEV_TOKEN:
        url = f"https://img.logo.dev/{domain}?token={LOGO_DEV_TOKEN}&size=128&format=png"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return url
        except Exception:
            pass

    # Fallback to Google favicon
    return GOOGLE_FAVICON_URL.format(domain=domain)
