# Personal Alpha — Daily Intelligence Briefing

A self-hosted, zero-dependency dashboard that delivers a **personalised daily news briefing** each morning — RSS-scraped, Gemini-analysed, GitHub Pages-hosted.

> Mission: €0 → €35k by 2032-05-27 · Solopreneur · Portugal

---

## What it does

| Step | Tool | What happens |
|------|------|-------------|
| 1 | GitHub Actions (cron 07:05 UTC) | Triggers `build.py` automatically every morning |
| 2 | Python + feedparser | Fetches ≥ 75 articles across 5 sections (Finance, World News, Tech, Automotive, Portugal) |
| 3 | Google Gemini 2.5 Flash | Analyses headlines → JSON insights, sentiment, learning task, biz opportunity |
| 4 | `content.json` + `summary.json` | Written to repo root |
| 5 | `stefanzweifel/git-auto-commit-action` | Pushes updated JSON back to `main` |
| 6 | GitHub Pages | Serves `index.html` — reads JSON at page load, no build step needed |

---

## Project structure

```
Personal-Alpha/
├── index.html          # Single-file frontend (dark theme, mobile-first)
├── build.py            # RSS scraper + Gemini analysis engine
├── config.py           # Feeds, limits, API config constants
├── requirements.txt    # feedparser, google-genai
├── content.json        # Generated — article data (75 items, 5 sections)
├── summary.json        # Generated — Gemini analysis output
├── build.log           # Generated — build run log
└── .github/
    └── workflows/
        └── daily-brief.yml   # GitHub Actions cron workflow
```

---

## First-time setup

### 1. Fork / clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/Personal-Alpha.git
cd Personal-Alpha
```

### 2. Add your Gemini API key as a GitHub Secret

The workflow reads `GEMINI_API_KEY` from your repository secrets at runtime.

1. Go to your repository on GitHub
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `GEMINI_API_KEY`
5. Value: your key from [Google AI Studio](https://aistudio.google.com/app/apikey)
6. Click **Add secret**

> **Free tier is enough.** Gemini 2.5 Flash has a generous free quota.
> The build makes **one API call per day**, well within free limits.

### 3. Enable GitHub Pages

1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `/ (root)`
4. Click **Save**

Your dashboard will be live at:
`https://YOUR_USERNAME.github.io/Personal-Alpha/`

### 4. Run the first build manually

Go to **Actions → Daily News Briefing → Run workflow** to generate your first `content.json` and `summary.json` immediately, without waiting for 07:05 UTC.

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export GEMINI_API_KEY="your_key_here"   # macOS/Linux
set GEMINI_API_KEY=your_key_here        # Windows CMD

# Run a full build
python build.py

# Serve the frontend locally (Python built-in server)
python -m http.server 8080
# Then open http://localhost:8080
```

Build output goes to `build.log`. On success you'll see:

```
Build successful. 75 articles. content.json + summary.json updated.
```

---

## Configuration

All tunable constants live in `config.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `TARGET_DATE` | `2032-05-27` | Goal completion date (drives footer countdown) |
| `START_DATE` | `2026-03-01` | Journey start date |
| `GOAL_DAYS` | `2279` | Total days in the journey |
| `SECTION_LIMITS` | `15` each | Max articles per section |
| `DIVERSITY_THRESHOLD` | `8` | Min RSS sources that must return results per section |
| `PORTUGAL_PRIORITY_SOURCES` | 6 native feeds | Sources that fill the 60% Portugal priority pool |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model ID |

---

## Portugal priority pool

60% of the 15 Portugal slots (= 9 articles) are reserved for native Portuguese sources:

- ECO (`eco.pt`)
- Jornal de Negócios
- Observador
- Correio da Manhã
- Dinheiro Vivo
- Diário de Notícias

These articles are flagged `"is_priority": true` in `content.json` and rendered with a **gold left border** in the UI.

---

## Content schema

### `content.json`

```json
{
  "built_at": "2026-03-01T07:06:12+00:00",
  "sections": {
    "Finance": [
      {
        "title": "Headline text",
        "source": "Source name",
        "published": "Sat, 01 Mar 2026 06:00:00 GMT",
        "url": "https://...",
        "is_priority": false
      }
    ],
    "Portugal": [
      {
        "title": "Notícia portuguesa",
        "source": "ECO",
        "published": "...",
        "url": "https://eco.pt/...",
        "is_priority": true
      }
    ]
  }
}
```

### `summary.json`

```json
{
  "built_at": "...",
  "global_theme": "One-sentence macro narrative",
  "market_mood": "Risk-Off",
  "risk_signal": "Short phrase",
  "opportunity_signal": "Short phrase",
  "finance_sentiment": [
    {"i": 1, "s": "+"},
    {"i": 2, "s": "-"}
  ],
  "insights": {
    "g1": ["Macro/finance bullet 1", "...", "...", "...", "..."],
    "g2": ["Tech/AI/skill bullet 1", "...", "...", "...", "..."],
    "g3": ["Portugal/EU/solopreneur bullet 1", "...", "...", "...", "..."]
  },
  "learning_task": "30-min skill tied to today's news",
  "biz_opportunity": "Niche + target customer + why now"
}
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML + CSS + JS — zero dependencies |
| Backend | Python 3.11+ |
| AI analysis | Google Gemini 2.5 Flash (free tier) |
| Automation | GitHub Actions |
| Hosting | GitHub Pages |
| RSS parsing | `feedparser` |
| AI SDK | `google-genai` |

---

## Troubleshooting

**Build fails with `GEMINI_API_KEY is not set`**
→ Ensure you added the secret in Settings → Secrets → Actions (step 2 above).

**Articles missing titles / showing "News Update from…"**
→ That feed returned entries without a `<title>` element. The fallback chain used summary → description → placeholder. Check `build.log` for `WARNING Empty title for…` lines.

**Diversity warning in build.log**
→ `DIVERSITY WARNING: X/Y URLs returned results (need ≥8)` means fewer than 8 sources in a section responded. This can happen if a feed is temporarily down. The build still succeeds with whatever articles were fetched.

**Page shows old data after build**
→ GitHub Pages can take 1–2 minutes to propagate. Hard-refresh (`Ctrl+Shift+R`) to bypass cache.
