"""Enrich each company with profile data: description, market cap, employees, HQ, logo."""

import json
import logging
from datetime import datetime, timezone

from clients.llm import LLMClient
from clients.logo import get_logo_url
from clients.searxng import SearXNGClient
from config import PROFILES_DIR

logger = logging.getLogger(__name__)

PROFILE_SYSTEM_PROMPT = """You are a data extraction assistant. Given search results about a company, extract structured information.

Return ONLY a JSON object with these fields:
{
  "description": "A concise 2-line description of what the company does",
  "market_cap": "Market capitalization as a human-readable string like '625.4B' or '12.3T'",
  "market_cap_raw": 625400000000,
  "employees": 2100000,
  "headquarters": {
    "city": "City name",
    "state": "State/Province",
    "country": "Country code like US, UK, etc.",
    "display": "City, State"
  }
}

If you cannot find a specific field, use null for that field. Return valid JSON only."""


async def enrich_company_profile(
    company: dict,
    searxng: SearXNGClient,
    llm: LLMClient,
) -> dict:
    """Fetch and structure profile data for a single company."""
    name = company["name"]
    domain = company["domain"]

    # Search for company info
    query = f"{name} company overview market cap number of employees headquarters 2026"
    results = await searxng.search(query, max_results=8)

    if not results:
        logger.warning(f"No search results for {name}")
        return _empty_profile(company)

    # Format search results for LLM
    snippets = "\n\n".join(
        f"Source: {r['title']}\n{r['snippet']}" for r in results if r["snippet"]
    )

    user_prompt = f"Company: {name}\nDomain: {domain}\n\nSearch results:\n{snippets}"

    # Extract structured data via GPT-4o-mini
    try:
        profile_data = await llm.complete_openai_json(
            PROFILE_SYSTEM_PROMPT, user_prompt
        )
    except Exception as e:
        logger.error(f"LLM extraction failed for {name}: {e}")
        profile_data = {}

    # Get logo URL
    logo_url = await get_logo_url(domain)

    # Build full profile
    profile = {
        "slug": company["slug"],
        "name": name,
        "rank": company["rank"],
        "description": profile_data.get("description", ""),
        "industry": company.get("industry", ""),
        "sector": company.get("sector", ""),
        "market_cap": profile_data.get("market_cap"),
        "market_cap_raw": profile_data.get("market_cap_raw"),
        "employees": profile_data.get("employees"),
        "headquarters": profile_data.get("headquarters", {}),
        "logo_url": logo_url,
        "domain": domain,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source_urls": [r["url"] for r in results[:5]],
    }

    # Save to disk
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROFILES_DIR / f"{company['slug']}.json"
    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2)

    return profile


def _empty_profile(company: dict) -> dict:
    return {
        "slug": company["slug"],
        "name": company["name"],
        "rank": company["rank"],
        "description": "",
        "industry": company.get("industry", ""),
        "sector": company.get("sector", ""),
        "market_cap": None,
        "market_cap_raw": None,
        "employees": None,
        "headquarters": {},
        "logo_url": "",
        "domain": company.get("domain", ""),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source_urls": [],
    }
