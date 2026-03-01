"""
Personal Alpha - Daily News Briefing Engine
Fetches RSS feeds, analyzes with Gemini, writes JSON outputs.
"""

import os
import json
import logging
from datetime import datetime, timezone

import feedparser
from google import genai

from config import SECTION_LIMITS, GEMINI_MODEL, GEMINI_API_KEY

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    filename='build.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RSS Feed Sources
# ---------------------------------------------------------------------------
RSS_FEEDS = {
    'Finance': [
        'https://feeds.content.dowjones.io/public/rss/mw_topstories',
        'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',
    ],
    'World News': [
        'http://feeds.bbci.co.uk/news/world/rss.xml',
        'https://feeds.npr.org/1004/rss.xml',
    ],
    'Tech': [
        'https://www.theverge.com/rss/index.xml',
        'https://www.wired.com/feed/rss',
        'https://hnrss.org/frontpage',
    ],
    'Automotive/Motorcycle': [
        'https://www.caranddriver.com/rss/all.xml/',
        'https://www.motorcyclenews.com/feed/',
        'https://www.visordown.com/feed',
    ],
    'Portugal': [
        'https://www.theportugalnews.com/rss/',
        'https://www.theportugalresident.com/feed/',
    ],
}

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_section(section_name: str, urls: list, limit: int) -> list:
    """Fetch articles from a list of RSS URLs, deduplicate by URL."""
    seen_urls = set()
    articles = []

    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_title = feed.feed.get('title', url)

            for entry in feed.entries:
                link = getattr(entry, 'link', '').strip()
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                # Normalise the published date
                published = entry.get('published', '')
                if not published:
                    published = datetime.now(timezone.utc).isoformat()

                articles.append({
                    'title': entry.get('title', 'No Title').strip(),
                    'source': source_title,
                    'published': published,
                    'url': link,
                })

                if len(articles) >= limit:
                    log.info(f"[{section_name}] Reached limit of {limit} from {url}")
                    return articles

            log.info(f"[{section_name}] Fetched {len(feed.entries)} entries from {url}")

        except Exception as exc:
            log.warning(f"[{section_name}] Failed to fetch {url}: {exc}")

    return articles[:limit]


def fetch_all_news() -> dict:
    """Fetch all sections and return a dict keyed by section name."""
    sections = {}
    for section, urls in RSS_FEEDS.items():
        limit = SECTION_LIMITS.get(section, 5)
        articles = fetch_section(section, urls, limit)
        sections[section] = articles
        log.info(f"[{section}] Total: {len(articles)} articles collected.")
    return sections

# ---------------------------------------------------------------------------
# Gemini Analysis
# ---------------------------------------------------------------------------

def build_prompt(sections: dict) -> str:
    """Assemble the headlines into a Gemini prompt."""
    lines = []
    for section, articles in sections.items():
        lines.append(f"\n## {section}")
        for article in articles:
            lines.append(f"- {article['title']} ({article['source']})")
    headlines_block = '\n'.join(lines)

    return f"""You are a strategic intelligence analyst briefing a 34-year-old entrepreneur who is starting from €0 capital and building toward financial independence over 6 years.

Analyze these today's news headlines and extract maximum actionable value:

{headlines_block}

Return ONLY valid JSON with NO markdown formatting, NO code blocks, NO extra text. Use exactly this structure:
{{
  "global_theme": "One sentence describing the dominant global narrative today.",
  "market_mood": "Short phrase describing the overall market sentiment (e.g. Cautiously Bullish).",
  "risk_signal": "The primary risk to watch right now (short phrase).",
  "opportunity_signal": "The most actionable opportunity visible today (short phrase).",
  "key_points": [
    "Strategic insight 1 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 2 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 3 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 4 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 5 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 6 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 7 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 8 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 9 relevant to the entrepreneur, max 25 words.",
    "Strategic insight 10 relevant to the entrepreneur, max 25 words."
  ],
  "learning_task": "One specific 30-minute tech skill or concept to study today, directly inspired by today's news.",
  "biz_opportunity": "One specific solopreneur business gap or niche identified from today's news, with a concrete angle."
}}"""


def analyze_with_gemini(sections: dict) -> dict:
    """Send headlines to Gemini and parse the JSON response."""
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = build_prompt(sections)
    log.info("Sending request to Gemini...")

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = response.text.strip()
    log.info(f"Gemini responded ({len(raw)} chars).")

    # Strip markdown code fences if Gemini wraps in ```json ... ```
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1]
        raw = raw.rsplit('```', 1)[0].strip()

    summary = json.loads(raw)
    log.info("Gemini JSON parsed successfully.")
    return summary

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(sections: dict, summary: dict) -> None:
    """Write content.json and summary.json."""
    now = datetime.now(timezone.utc).isoformat()

    content = {
        'built_at': now,
        'sections': sections,
    }
    with open('content.json', 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    log.info("Wrote content.json")

    summary['built_at'] = now
    with open('summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log.info("Wrote summary.json")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 50)
    log.info("Build started")

    sections = fetch_all_news()

    total_articles = sum(len(v) for v in sections.values())
    log.info(f"Total articles fetched: {total_articles}")

    if total_articles == 0:
        log.error("No articles fetched. Aborting Gemini call.")
        raise RuntimeError("No articles were fetched from any RSS feed.")

    summary = analyze_with_gemini(sections)
    write_outputs(sections, summary)

    log.info("Build complete.")
    print("Build successful. content.json and summary.json updated.")


if __name__ == '__main__':
    main()
