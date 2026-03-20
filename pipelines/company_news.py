"""Fetch recent business news for each company, categorized by functional area."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from clients.llm import LLMClient
from clients.searxng import SearXNGClient
from config import NEWS_DIR, NEWS_LLM_PROVIDER

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

NEWS_SYSTEM_PROMPT = """You are a strict, factual news extraction assistant for a B2B sales intelligence platform.

Given search results about a company, categorize each genuinely relevant news item into one of these functional areas:
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
1. ONLY extract news that DIRECTLY mentions or clearly involves the company. Do NOT force-fit tangential industry news.
2. Each news item MUST have a relevance_score between 0.0 and 1.0. DISCARD anything below 0.7.
3. NEVER fabricate, invent, or hallucinate news. If a search result is vague, ambiguous, or not clearly about the company, SKIP IT.
4. If NO relevant news exists for a category, leave it as an empty array. It is perfectly fine — even expected — for most categories to be empty.
5. Only use information present in the provided search results. Do not add details from your training data.
6. Prefer specificity: a news item should go in the MOST specific category that fits, not "General Business" unless nothing else applies.

Return ONLY a JSON object with this structure:
{
  "AI & Technology": [
    {
      "title": "Exact headline from search results",
      "summary": "One factual sentence summarizing the news",
      "source": "Name of the news outlet",
      "url": "URL from the search result",
      "published_date": "YYYY-MM-DD",
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

Empty arrays are the correct output when no relevant news is found for a category. Do NOT pad or fill categories just to have content.
Return valid JSON only."""


async def fetch_company_news(
    company: dict,
    searxng: SearXNGClient,
    llm: LLMClient,
) -> dict:
    """Fetch and structure recent news by functional category."""
    name = company["name"]

    # Search recent news from multiple angles
    results = []
    seen_urls = set()

    queries = [
        (f'"{name}" business news', "news", "week"),
        (f'"{name}" AI technology announcement', "news", "week"),
        (f'"{name}" partnership acquisition deal', "news", "week"),
        (f'"{name}" earnings revenue pricing', "news", "week"),
        (f'"{name}" supply chain operations', "news", "month"),
    ]

    # Run all searches in parallel
    search_tasks = [
        searxng.search(q, categories=cat, time_range=tr, max_results=10)
        for q, cat, tr in queries
    ]
    all_hits = await asyncio.gather(*search_tasks)

    for hits in all_hits:
        for r in hits:
            if r["url"] not in seen_urls and r["snippet"]:
                results.append(r)
                seen_urls.add(r["url"])

    if not results:
        logger.warning(f"No news results for {name}")
        return _save_news(company, _empty_categories())

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
        categorized = await complete_fn(NEWS_SYSTEM_PROMPT, user_prompt)

        if not isinstance(categorized, dict):
            logger.warning(f"Unexpected LLM output type for {name}: {type(categorized)}")
            categorized = _empty_categories()

        # Enforce relevance threshold
        categorized = _filter_by_relevance(categorized, threshold=0.7)

    except Exception as e:
        logger.error(f"LLM news extraction failed for {name}: {e}")
        categorized = _empty_categories()

    return _save_news(company, categorized)


def _empty_categories() -> dict:
    return {cat: [] for cat in FUNCTIONAL_CATEGORIES}


def _filter_by_relevance(categorized: dict, threshold: float) -> dict:
    """Remove news items below the relevance threshold."""
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


def _save_news(company: dict, categorized: dict) -> dict:
    # Count total items
    total = sum(len(v) for v in categorized.values())

    output = {
        "slug": company["slug"],
        "name": company["name"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_news_items": total,
        "categories": categorized,
    }

    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = NEWS_DIR / f"{company['slug']}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    return output
