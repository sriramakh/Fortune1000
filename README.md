# Fortune 1000 Dataset Builder

Automated pipeline that builds and maintains a comprehensive dataset of Fortune 1000 companies with company profiles, categorized business news, and events/conferences — designed for B2B sales intelligence.

## What It Does

1. **Company Profiles** (monthly refresh): Name, description, industry, market cap, employees, headquarters, logo for all 1000 companies
2. **Categorized News** (every 2 days): Recent business news sorted into 12 functional areas (AI & Technology, Supply Chain, Finance, Partnerships, etc.)
3. **Categorized Events** (every 2 days): Conferences, summits, webinars the company is hosting/sponsoring/attending

All news and events are filtered with a **relevance threshold of 0.7** — empty categories are preferred over hallucinated content.

## Functional Categories

| Category | Use Case |
|---|---|
| AI & Technology | Track AI adoption, tech investments |
| Supply Chain & Operations | Monitor operational changes |
| Marketing & Brand | Brand strategy shifts |
| Finance & Earnings | Revenue, earnings, fundraising |
| CRM & Customer Experience | Customer-facing initiatives |
| Pricing & Revenue Strategy | Pricing model changes |
| Partnerships & M&A | Deals, acquisitions, alliances |
| Leadership & Workforce | C-suite changes, hiring |
| Legal & Regulatory | Compliance, lawsuits, regulation |
| Sustainability & ESG | ESG initiatives |
| Product & Innovation | New products, R&D |
| General Business | Other business news |

## Tech Stack

- **Python 3.12+** with async/await
- **SearXNG** (self-hosted) for web search via 100 rotating proxies
- **MiniMax M2.7** for news/events extraction (with GPT-4o-mini fallback)
- **GPT-4o-mini** for company profile enrichment
- **JSON files** for storage, CSV export for review

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and MINIMAX_API_TOKEN
```

### Prerequisites

- SearXNG instance running at `localhost:8080` (Docker recommended)
- OpenAI API key
- MiniMax API key (optional — falls back to OpenAI)

## Usage

```bash
# Build company list + enrich profiles (run monthly)
python main.py monthly

# Refresh news + events (run every 2 days)
python main.py biweekly

# Run only news or events
python main.py news
python main.py events

# Combine all data into single JSON
python main.py combine

# Export to CSV for review
python export_csv.py

# Test with subset
python main.py monthly --limit 10
python main.py biweekly --limit 10
```

## Output

- `data/combined/fortune1000.json` — single merged file
- `data/fortune1000_review.csv` — spreadsheet with 58 columns (10 profile + 24 news + 24 events)
- `data/profiles/{slug}.json` — individual company profiles
- `data/news/{slug}.json` — categorized news per company
- `data/events/{slug}.json` — categorized events per company

## Scheduling (Cron)

```bash
bash cron/setup_cron.sh
```

This installs:
- Monthly profile refresh: 1st of each month at 2 AM
- Bi-daily news+events refresh: every 2 days at 3 AM

## Resume Support

If a pipeline crashes mid-run, restart it — already-completed companies are skipped automatically. Progress is tracked in `data/progress/`.
