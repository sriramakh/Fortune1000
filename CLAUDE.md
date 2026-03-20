# CLAUDE.md — Instructions for Claude Code

## Project Overview
Fortune 1000 dataset builder for B2B sales intelligence. Builds and maintains company profiles, categorized business news, and events/conferences for all Fortune 1000 companies.

## Quick Start
```bash
cd "/Users/sriram/Desktop/AI Projects/Fortune"  # or wherever cloned
source venv/bin/activate
python main.py monthly --limit 5   # test profiles
python main.py biweekly --limit 5  # test news + events
python export_csv.py               # generate CSV
```

## Architecture Summary
- `main.py` — CLI entry point. Commands: `monthly`, `biweekly`, `news`, `events`, `combine`
- `config.py` — All configuration (API URLs, concurrency, model names, thresholds)
- `clients/searxng.py` — SearXNG search client (localhost:8080, semaphore rate-limited)
- `clients/llm.py` — MiniMax M2.7 (direct HTTP to `https://api.minimax.io/v1/text/chatcompletion_v2`) + OpenAI GPT-4o-mini (via openai SDK). MiniMax auto-falls back to OpenAI on failure.
- `clients/logo.py` — Logo URL resolver (logo.dev or Google favicon fallback)
- `pipelines/company_list.py` — Parses `data/seed_github.csv` → `data/companies.json`
- `pipelines/company_profiles.py` — SearXNG + GPT-4o-mini → profile JSON
- `pipelines/company_news.py` — 5 parallel SearXNG queries + MiniMax M2.7 → categorized news (12 functional areas, relevance >= 0.7)
- `pipelines/company_events.py` — 2 parallel SearXNG queries + MiniMax M2.7 → categorized events
- `orchestrator/batch_processor.py` — Async batch processing (15 concurrent, retry 3x, exponential backoff)
- `orchestrator/progress.py` — JSON-based progress tracker for resume support
- `export_csv.py` — Generates `data/fortune1000_review.csv` (58 columns: 10 profile + 24 news + 24 events)

## Critical Details

### MiniMax API
- **NOT OpenAI-compatible**. Uses direct HTTP POST to `https://api.minimax.io/v1/text/chatcompletion_v2`
- Auth: `Authorization: Bearer {MINIMAX_API_TOKEN}`
- Model: `MiniMax-M2.7` (reasoning model, ~20-30s per call for categorized output)
- Uses `max_completion_tokens` (not `max_tokens`), currently set to 8192
- Do NOT use the `openai` Python SDK for MiniMax — it won't work

### SearXNG
- Runs in Docker (from `/Users/sriram/Desktop/AI Projects/OrgChartArch/docker-compose.yml`)
- Port 8080 must be exposed to host (was added to docker-compose)
- Configured with 100 Webshare rotating proxies in `searxng/settings.yml`
- Rate limited via asyncio.Semaphore(15) + 0.2s delay

### News/Events Categorization
12 functional categories: AI & Technology, Supply Chain & Operations, Marketing & Brand, Finance & Earnings, CRM & Customer Experience, Pricing & Revenue Strategy, Partnerships & M&A, Leadership & Workforce, Legal & Regulatory, Sustainability & ESG, Product & Innovation, General Business.

Rules enforced in both prompt AND Python post-processing:
- relevance_score >= 0.7 or item is discarded
- Empty categories are correct — never hallucinate news
- Each news URL is preserved in a separate CSV column for clickability

### Concurrency Tuning
- Pipeline batch: 15 concurrent companies
- SearXNG semaphore: 15 concurrent searches, 0.2s delay
- Throughput: ~22 companies/min for news, ~38/min for events
- Full run: ~45 min news + ~25 min events = ~70 min total

### Resume Support
Progress tracked in `data/progress/{pipeline}_run.json`. If a run crashes:
- Just re-run the same command
- Completed companies are skipped automatically
- To force re-run, delete the progress file first

## Environment Setup on New Machine
1. Clone repo: `git clone https://github.com/sriramakh/Fortune1000.git`
2. `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in API keys
4. Ensure SearXNG is running on localhost:8080 with proxies configured
5. Download seed CSV: `curl -sL "https://raw.githubusercontent.com/dmarcelinobr/Datasets/master/Fortune1000.csv" -o data/seed_github.csv`
6. Create data dirs: `mkdir -p data/{profiles,news,events,combined,progress}`
7. Test: `python main.py monthly --limit 5`

## Cron
- Monthly profiles: `0 2 1 * *`
- Bi-daily news+events: `0 3 */2 * *`
- Install via: `bash cron/setup_cron.sh`

## Common Issues
- **MiniMax returns empty content**: Token limit too low. Currently 8192, increase in `clients/llm.py` if needed.
- **SearXNG connection refused**: Docker port 8080 not exposed. Check `docker-compose.yml` for `ports: - "8080:8080"` on searxng service.
- **JSON parse failures**: MiniMax M2.7 sometimes wraps JSON in markdown fences or truncates. `parse_llm_json()` in `clients/llm.py` handles this. Fallback to OpenAI is automatic.
- **Slow runs**: Increase concurrency in `main.py` (BatchProcessor) and `config.py` (SEARXNG_CONCURRENCY). With 100 proxies, 15-20 concurrent is safe.
