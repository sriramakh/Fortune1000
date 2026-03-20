"""Build the master Fortune 1000 company list from seed CSV."""

import csv
import json
import logging
import re
from urllib.parse import urlparse

from config import DATA_DIR

logger = logging.getLogger(__name__)

SEED_CSV = DATA_DIR / "seed_github.csv"


def domain_from_url(url: str) -> str:
    """Extract clean domain from a URL."""
    if not url:
        return ""
    url = url.strip().strip('"')
    if not url.startswith("http"):
        url = "http://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    domain = domain.lower().removeprefix("www.")
    return domain


def slugify(name: str) -> str:
    """Convert company name to a URL-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def build_company_list(limit: int | None = None) -> list[dict]:
    """Build and save the master company list from seed CSV."""
    if not SEED_CSV.exists():
        raise FileNotFoundError(f"Seed CSV not found at {SEED_CSV}")

    companies = []
    with open(SEED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append({
                "rank": int(row.get("rank", 0)),
                "name": row["name"].strip().strip('"'),
                "industry": row.get("industry", "").strip().strip('"'),
                "sector": row.get("sector", "").strip().strip('"'),
                "domain": domain_from_url(row.get("website", "")),
                "slug": slugify(row["name"].strip().strip('"')),
            })

    # Sort by rank
    companies.sort(key=lambda c: c["rank"])

    if limit:
        companies = companies[:limit]

    output = {
        "metadata": {
            "source": "fortune1000-seed-csv",
            "count": len(companies),
        },
        "companies": companies,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "companies.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Saved {len(companies)} companies to {out_path}")
    return companies


def load_companies(limit: int | None = None) -> list[dict]:
    """Load the company list from disk."""
    path = DATA_DIR / "companies.json"
    if not path.exists():
        logger.info("No companies.json found, building from seed...")
        return build_company_list(limit)

    with open(path) as f:
        data = json.load(f)

    companies = data["companies"]
    if limit:
        companies = companies[:limit]
    return companies
