# Architecture

## System Overview

```
                    ┌─────────────────────────────────────────────────┐
                    │                  main.py (CLI)                  │
                    │         monthly | biweekly | combine            │
                    └──────┬──────────┬──────────────┬────────────────┘
                           │          │              │
              ┌────────────▼──┐  ┌────▼────────┐  ┌──▼──────────────┐
              │  company_list │  │ company_news │  │ company_events  │
              │  company_     │  │  (MiniMax)   │  │   (MiniMax)     │
              │  profiles     │  │              │  │                 │
              │  (GPT-4o-mini)│  │              │  │                 │
              └──────┬────────┘  └──────┬───────┘  └────────┬────────┘
                     │                  │                    │
          ┌──────────▼──────────────────▼────────────────────▼────────┐
          │              orchestrator/batch_processor.py               │
          │        concurrency control, retry, resume, progress       │
          └──────────┬──────────────────┬─────────────────────────────┘
                     │                  │
          ┌──────────▼──────┐  ┌────────▼──────────┐
          │ clients/llm.py  │  │ clients/searxng.py │
          │ MiniMax + OpenAI│  │  SearXNG search    │
          │ (with fallback) │  │  (rate limited)    │
          └─────────────────┘  └────────┬───────────┘
                                        │
                                ┌───────▼──────────┐
                                │     SearXNG      │
                                │  (Docker:8080)   │
                                │  100 proxies     │
                                └──────────────────┘
```

## Directory Structure

```
Fortune/
├── main.py                    # CLI entry point & combine logic
├── config.py                  # All configuration constants
├── export_csv.py              # JSON → CSV exporter
├── requirements.txt
│
├── clients/                   # External service clients
│   ├── searxng.py             # SearXNG search with semaphore rate limiting
│   ├── llm.py                 # MiniMax (direct HTTP) + OpenAI (sdk) with fallback
│   └── logo.py                # Logo URL resolver (logo.dev / Google favicon)
│
├── pipelines/                 # Data pipelines
│   ├── company_list.py        # Parse seed CSV → companies.json
│   ├── company_profiles.py    # SearXNG + GPT-4o-mini → profiles/{slug}.json
│   ├── company_news.py        # SearXNG + MiniMax M2.7 → news/{slug}.json (categorized)
│   └── company_events.py      # SearXNG + MiniMax M2.7 → events/{slug}.json (categorized)
│
├── orchestrator/              # Execution engine
│   ├── batch_processor.py     # Async batch with concurrency, retry, resume
│   └── progress.py            # JSON-based progress tracker
│
├── cron/
│   └── setup_cron.sh          # Crontab installer
│
└── data/                      # Output (gitignored)
    ├── seed_github.csv        # Fortune 1000 seed list
    ├── companies.json          # Master company list
    ├── profiles/{slug}.json
    ├── news/{slug}.json
    ├── events/{slug}.json
    ├── combined/fortune1000.json
    ├── fortune1000_review.csv
    └── progress/               # Resume tracking
```

## Data Flow

### Monthly Pipeline

```
seed_github.csv
    │
    ▼
company_list.py ──► data/companies.json (1000 entries)
    │
    ▼ (for each company, 15 concurrent)
SearXNG: "{name} company overview market cap employees headquarters"
    │
    ▼
GPT-4o-mini: extract structured profile (description, market_cap, employees, HQ)
    │
    ▼
logo.py: resolve logo URL
    │
    ▼
data/profiles/{slug}.json
    │
    ▼
combine ──► data/combined/fortune1000.json
```

### Biweekly Pipeline

```
data/companies.json
    │
    ▼ (for each company, 15 concurrent)
SearXNG: 5 parallel queries per company
  ├── "{name}" business news
  ├── "{name}" AI technology announcement
  ├── "{name}" partnership acquisition deal
  ├── "{name}" earnings revenue pricing
  └── "{name}" supply chain operations
    │
    ▼
MiniMax M2.7: categorize into 12 functional areas, score relevance
    │
    ▼ (filter: relevance >= 0.7, empty categories = correct)
data/news/{slug}.json
data/events/{slug}.json
    │
    ▼
combine ──► data/combined/fortune1000.json
export_csv.py ──► data/fortune1000_review.csv (58 columns)
```

## Key Design Decisions

### 1. MiniMax M2.7 for News/Events, GPT-4o-mini for Profiles
- Profiles need accuracy (market cap numbers, employee counts) → GPT-4o-mini
- News/events are summarization from pre-fetched snippets → MiniMax M2.7 (unlimited plan)
- Automatic fallback: if MiniMax fails, OpenAI is used transparently

### 2. MiniMax via Direct HTTP (not OpenAI SDK)
MiniMax's endpoint is `https://api.minimax.io/v1/text/chatcompletion_v2` — not OpenAI-compatible. We use `aiohttp` directly with proper auth headers.

### 3. 12 Functional Categories with Strict Relevance
The LLM prompt explicitly instructs:
- Relevance score >= 0.7 or discard
- Empty arrays are correct and expected
- Never fabricate news — only use search result content
- Post-processing enforces the threshold in Python as a safety net

### 4. Per-Company JSON Files
Individual `{slug}.json` files enable:
- **Resume**: check if file exists, skip completed companies
- **Partial updates**: update one company without rewriting all
- **Debugging**: inspect individual company output
- Combined `fortune1000.json` is regenerated as convenience output

### 5. Parallel Search Within Companies
Each company fires 5 SearXNG queries in parallel (`asyncio.gather`), then feeds all results to a single LLM call. This maximizes search coverage while minimizing LLM calls.

### 6. Conservative Proxy Rotation
SearXNG is configured with 100 Webshare proxies. Outgoing requests to Google/Bing/Brave/DDG are distributed across proxies. SearXNG handles rotation internally.

## Concurrency Model

```
BatchProcessor (15 concurrent companies)
    └── per company:
        ├── asyncio.gather(5 SearXNG searches)  ← SearXNG semaphore (15)
        └── 1 LLM call (MiniMax or OpenAI)       ← ~20-30s per call
```

- **SearXNG**: `asyncio.Semaphore(15)` + 0.2s inter-request delay
- **Batch**: 15 companies processed concurrently
- **Throughput**: ~22 companies/min for news, ~38/min for events

## Error Handling

| Scenario | Behavior |
|---|---|
| SearXNG timeout/error | Return empty results, company gets empty categories |
| MiniMax failure | Fallback to GPT-4o-mini transparently |
| LLM returns invalid JSON | Strip markdown fences, regex extraction, then fail gracefully |
| Relevance < 0.7 | Filtered out in Python post-processing |
| Pipeline crash | Resume from last checkpoint via progress tracker |
| Retry exhausted | Logged as failed, pipeline continues with remaining companies |
