"""Export the Fortune 1000 combined dataset to CSV for review.

News and events are organized by functional category.
Each category gets columns for title+summary and a clickable URL.
"""

import csv
import json
from config import COMBINED_DIR, DATA_DIR

CATEGORIES = [
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


def format_news_cell(items: list) -> str:
    """Format news items into a readable string for a cell."""
    if not items:
        return ""
    parts = []
    for item in items:
        date = item.get("published_date", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        source = item.get("source", "")
        parts.append(f"[{date}] {title} ({source})\n{summary}")
    return "\n---\n".join(parts)


def format_news_urls(items: list) -> str:
    """Extract all URLs from news items, one per line."""
    if not items:
        return ""
    return "\n".join(item.get("url", "") for item in items if item.get("url"))


def format_event_cell(items: list) -> str:
    """Format event items into a readable string for a cell."""
    if not items:
        return ""
    parts = []
    for item in items:
        title = item.get("title", "")
        etype = item.get("type", "")
        desc = item.get("description", "")
        dates = item.get("date_range", "")
        loc = item.get("location", "")
        role = item.get("company_role", "")
        parts.append(f"{title} ({etype}) | {role}\n{desc}\nDates: {dates} | Location: {loc}")
    return "\n---\n".join(parts)


def format_event_urls(items: list) -> str:
    """Extract all URLs from event items, one per line."""
    if not items:
        return ""
    return "\n".join(item.get("url", "") for item in items if item.get("url"))


def export():
    with open(COMBINED_DIR / "fortune1000.json") as f:
        data = json.load(f)

    out_path = DATA_DIR / "fortune1000_review.csv"

    # Build header: profile cols + (news detail, news urls) per category + (event detail, event urls) per category
    header = [
        "Rank",
        "Company",
        "Industry",
        "Sector",
        "Description",
        "Market Cap",
        "Employees",
        "Headquarters",
        "Domain",
        "Logo URL",
    ]
    for cat in CATEGORIES:
        header.append(f"News: {cat}")
        header.append(f"News URLs: {cat}")
    for cat in CATEGORIES:
        header.append(f"Events: {cat}")
        header.append(f"Event URLs: {cat}")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for c in data["companies"]:
            hq = c.get("headquarters", {})
            hq_display = hq.get("display", "") if isinstance(hq, dict) else ""

            news_cats = c.get("news_categories", {})
            events_cats = c.get("events_categories", {})

            row = [
                c.get("rank", ""),
                c.get("name", ""),
                c.get("industry", ""),
                c.get("sector", ""),
                c.get("description", ""),
                c.get("market_cap", ""),
                c.get("employees", ""),
                hq_display,
                c.get("domain", ""),
                c.get("logo_url", ""),
            ]

            # News columns — detail + URLs per category
            for cat in CATEGORIES:
                items = news_cats.get(cat, [])
                row.append(format_news_cell(items))
                row.append(format_news_urls(items))

            # Events columns — detail + URLs per category
            for cat in CATEGORIES:
                items = events_cats.get(cat, [])
                row.append(format_event_cell(items))
                row.append(format_event_urls(items))

            writer.writerow(row)

    total_cols = 10 + len(CATEGORIES) * 4
    print(f"Exported {len(data['companies'])} companies to {out_path}")
    print(f"Columns: 10 profile + {len(CATEGORIES)*2} news (detail+urls) + {len(CATEGORIES)*2} events (detail+urls) = {total_cols} total")


if __name__ == "__main__":
    export()
