"""Fetch recent events, workshops, and conferences, categorized by functional area."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from clients.llm import LLMClient
from clients.searxng import SearXNGClient
from config import EVENTS_DIR, NEWS_LLM_PROVIDER

logger = logging.getLogger(__name__)

FUNCTIONAL_CATEGORIES = [
    "AI & Technology",
    "Supply Chain & Operations",
    "Marketing & Brand",
    "Finance & Earnings",
    "CRM & Customer Experience",
    "Pricing & Revenue Strategy",
    "Partnerships & M&A",
    "Leadership & Workforce",
    "Legal & Regulatory",
    "Sustainability & ESG",
    "Product & Innovation",
    "General Business",
]

EVENTS_SYSTEM_PROMPT = """You are a strict, factual events extraction assistant for a B2B sales intelligence platform.

Given search results, extract events, conferences, workshops, summits, webinars, or trade shows that the company is clearly participating in, hosting, or sponsoring. Categorize each event into one of these functional areas:
- AI & Technology
- Supply Chain & Operations
- Marketing & Brand
- Finance & Earnings
- CRM & Customer Experience
- Pricing & Revenue Strategy
- Partnerships & M&A
- Leadership & Workforce
- Legal & Regulatory
- Sustainability & ESG
- Product & Innovation
- General Business

CRITICAL RULES:
1. ONLY extract events where the company is DIRECTLY involved (hosting, sponsoring, presenting, exhibiting). Do NOT include events just because the company's industry is mentioned.
2. Each event MUST have a relevance_score between 0.0 and 1.0. DISCARD anything below 0.7.
3. NEVER fabricate, invent, or hallucinate events. If a search result is vague or not clearly an event, SKIP IT.
4. If NO relevant events exist for a category, leave it as an empty array. Most categories being empty is expected and correct.
5. Only use information present in the provided search results. Do not add details from your training data.

Return ONLY a JSON object with this structure:
{
  "AI & Technology": [
    {
      "title": "Event name",
      "type": "conference|workshop|summit|tradeshow|webinar|hackathon",
      "description": "One factual sentence about the event and the company's role",
      "date_range": "March 15-17, 2026",
      "location": "City, Country or Virtual",
      "url": "URL from search results",
      "company_role": "host|sponsor|keynote speaker|exhibitor|participant|organizer",
      "relevance_score": 0.85
    }
  ],
  "Supply Chain & Operations": [],
  "Marketing & Brand": [],
  "Finance & Earnings": [],
  "CRM & Customer Experience": [],
  "Pricing & Revenue Strategy": [],
  "Partnerships & M&A": [],
  "Leadership & Workforce": [],
  "Legal & Regulatory": [],
  "Sustainability & ESG": [],
  "Product & Innovation": [],
  "General Business": []
}

Empty arrays are the correct output when no relevant events are found. Do NOT pad or fill categories.
Return valid JSON only."""


async def fetch_company_events(
    company: dict,
    searxng: SearXNGClient,
    llm: LLMClient,
) -> dict:
    """Fetch and structure recent events by functional category."""
    name = company["name"]

    results = []
    seen_urls = set()

    queries = [
        (f'"{name}" conference summit event 2026', None, "month"),
        (f'"{name}" hosting sponsoring workshop webinar 2026', None, "month"),
    ]

    # Run all searches in parallel
    search_tasks = [
        searxng.search(q, categories=cat or "general", time_range=tr, max_results=10)
        for q, cat, tr in queries
    ]
    all_hits = await asyncio.gather(*search_tasks)

    for hits in all_hits:
        for r in hits:
            if r["url"] not in seen_urls and r["snippet"]:
                results.append(r)
                seen_urls.add(r["url"])

    if not results:
        logger.warning(f"No event results for {name}")
        return _save_events(company, _empty_categories())

    # Format for LLM
    snippets = "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nDate: {r['date']}\nSnippet: {r['snippet']}"
        for r in results
    )

    user_prompt = f"Company: {name}\nIndustry: {company.get('industry', '')}\n\nSearch results:\n{snippets}"

    try:
        complete_fn = (
            llm.complete_openai_json
            if NEWS_LLM_PROVIDER == "openai"
            else llm.complete_minimax_json
        )
        categorized = await complete_fn(EVENTS_SYSTEM_PROMPT, user_prompt)

        if not isinstance(categorized, dict):
            logger.warning(f"Unexpected LLM output type for {name}: {type(categorized)}")
            categorized = _empty_categories()

        # Enforce relevance threshold
        categorized = _filter_by_relevance(categorized, threshold=0.7)

    except Exception as e:
        logger.error(f"LLM events extraction failed for {name}: {e}")
        categorized = _empty_categories()

    return _save_events(company, categorized)


def _empty_categories() -> dict:
    return {cat: [] for cat in FUNCTIONAL_CATEGORIES}


def _filter_by_relevance(categorized: dict, threshold: float) -> dict:
    """Remove events below the relevance threshold."""
    filtered = {}
    for cat in FUNCTIONAL_CATEGORIES:
        items = categorized.get(cat, [])
        if not isinstance(items, list):
            filtered[cat] = []
            continue
        filtered[cat] = [
            item for item in items
            if isinstance(item, dict) and item.get("relevance_score", 0) >= threshold
        ]
    return filtered


def _save_events(company: dict, categorized: dict) -> dict:
    total = sum(len(v) for v in categorized.values())

    output = {
        "slug": company["slug"],
        "name": company["name"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_events": total,
        "categories": categorized,
    }

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVENTS_DIR / f"{company['slug']}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    return output
