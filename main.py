"""Fortune 1000 Dataset Builder - CLI Entry Point."""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

from clients.llm import LLMClient
from clients.searxng import SearXNGClient
from config import (
    COMBINED_DIR,
    DATA_DIR,
    EVENTS_DIR,
    NEWS_DIR,
    PROFILES_DIR,
    SEARXNG_CONCURRENCY,
)
from orchestrator.batch_processor import BatchProcessor
from orchestrator.progress import ProgressTracker
from pipelines.company_events import fetch_company_events
from pipelines.company_list import build_company_list, load_companies
from pipelines.company_news import fetch_company_news
from pipelines.company_profiles import enrich_company_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def run_monthly_pipeline(limit: int | None = None):
    """Run the monthly pipeline: build company list + enrich profiles."""
    logger.info("=== Monthly Pipeline: Company List + Profiles ===")

    # Step 1: Build company list
    companies = build_company_list(limit)
    logger.info(f"Company list: {len(companies)} companies")

    # Step 2: Enrich profiles
    searxng = SearXNGClient()
    llm = LLMClient()

    run_id = f"monthly-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    progress = ProgressTracker(run_id, "monthly_profiles", len(companies))
    processor = BatchProcessor(concurrency=SEARXNG_CONCURRENCY, name="profiles")

    async def process_one(company):
        return await enrich_company_profile(company, searxng, llm)

    await processor.process_batch(companies, process_one, progress)

    await searxng.close()
    await llm.close()

    # Combine
    combine_all()
    logger.info("=== Monthly Pipeline Complete ===")


async def run_news_pipeline(limit: int | None = None):
    """Run the news pipeline for all companies."""
    logger.info("=== News Pipeline ===")
    companies = load_companies(limit)

    searxng = SearXNGClient()
    llm = LLMClient()

    run_id = f"news-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    progress = ProgressTracker(run_id, "news", len(companies))
    processor = BatchProcessor(concurrency=15, name="news")

    async def process_one(company):
        return await fetch_company_news(company, searxng, llm)

    await processor.process_batch(companies, process_one, progress)

    await searxng.close()
    await llm.close()
    logger.info("=== News Pipeline Complete ===")


async def run_events_pipeline(limit: int | None = None):
    """Run the events pipeline for all companies."""
    logger.info("=== Events Pipeline ===")
    companies = load_companies(limit)

    searxng = SearXNGClient()
    llm = LLMClient()

    run_id = f"events-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    progress = ProgressTracker(run_id, "events", len(companies))
    processor = BatchProcessor(concurrency=15, name="events")

    async def process_one(company):
        return await fetch_company_events(company, searxng, llm)

    await processor.process_batch(companies, process_one, progress)

    await searxng.close()
    await llm.close()
    logger.info("=== Events Pipeline Complete ===")


async def run_biweekly_pipeline(limit: int | None = None):
    """Run both news and events pipelines."""
    await run_news_pipeline(limit)
    await run_events_pipeline(limit)
    combine_all()


def combine_all():
    """Merge all per-company files into a single fortune1000.json."""
    logger.info("Combining all data into fortune1000.json...")
    companies_path = DATA_DIR / "companies.json"
    if not companies_path.exists():
        logger.error("No companies.json found. Run monthly pipeline first.")
        return

    with open(companies_path) as f:
        company_list = json.load(f)["companies"]

    combined = []
    for company in company_list:
        slug = company["slug"]
        entry = {**company}

        # Load profile
        profile_path = PROFILES_DIR / f"{slug}.json"
        if profile_path.exists():
            with open(profile_path) as f:
                profile = json.load(f)
            entry.update({
                "description": profile.get("description", ""),
                "market_cap": profile.get("market_cap"),
                "market_cap_raw": profile.get("market_cap_raw"),
                "employees": profile.get("employees"),
                "headquarters": profile.get("headquarters", {}),
                "logo_url": profile.get("logo_url", ""),
            })

        # Load news (categorized)
        news_path = NEWS_DIR / f"{slug}.json"
        if news_path.exists():
            with open(news_path) as f:
                news_data = json.load(f)
            entry["news_categories"] = news_data.get("categories", {})
            entry["news_updated"] = news_data.get("last_updated", "")
        else:
            entry["news_categories"] = {}
            entry["news_updated"] = ""

        # Load events (categorized)
        events_path = EVENTS_DIR / f"{slug}.json"
        if events_path.exists():
            with open(events_path) as f:
                events_data = json.load(f)
            entry["events_categories"] = events_data.get("categories", {})
            entry["events_updated"] = events_data.get("last_updated", "")
        else:
            entry["events_categories"] = {}
            entry["events_updated"] = ""

        combined.append(entry)

    output = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(combined),
        },
        "companies": combined,
    }

    COMBINED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = COMBINED_DIR / "fortune1000.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Combined data saved to {out_path} ({len(combined)} companies)")


def main():
    parser = argparse.ArgumentParser(description="Fortune 1000 Dataset Builder")
    parser.add_argument(
        "command",
        choices=["monthly", "news", "events", "biweekly", "combine"],
        help="Pipeline to run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N companies (for testing)",
    )
    args = parser.parse_args()

    if args.command == "monthly":
        asyncio.run(run_monthly_pipeline(args.limit))
    elif args.command == "news":
        asyncio.run(run_news_pipeline(args.limit))
    elif args.command == "events":
        asyncio.run(run_events_pipeline(args.limit))
    elif args.command == "biweekly":
        asyncio.run(run_biweekly_pipeline(args.limit))
    elif args.command == "combine":
        combine_all()


if __name__ == "__main__":
    main()
