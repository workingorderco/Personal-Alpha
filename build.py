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
        'https://feeds.content.dowjones.io/public/rss/mw_topstories',  # MarketWatch
        'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',  # CNBC Markets
        'https://feeds.bloomberg.com/markets/news.rss',  # Bloomberg Markets
    ],
    'World News': [
        'http://feeds.bbci.co.uk/news/world/rss.xml',  # BBC World
        'https://www.aljazeera.com/xml/rss/all.xml',  # Al Jazeera
    ],
    'Tech': [
        'https://www.theverge.com/rss/index.xml',  # The Verge
        'https://www.wired.com/feed/rss',  # Wired
        'https://sifted.eu/feed/',  # Sifted (EU startup scene)
        'https://hnrss.org/frontpage',  # Hacker News
    ],
    'Automotive/Motorcycle': [
        'https://www.caranddriver.com/rss/all.xml/',  # Car and Driver
        'https://www.motorcyclenews.com/feed/',  # MCN
        'https://www.visordown.com/feed',  # Visordown
    ],
    'Portugal': [
        'https://www.theportugalnews.com/rss/',  # The Portugal News
        'https://www.theportugalresident.com/feed/',  # Portugal Resident
        'https://www.lusa.pt/rss/ultimas/',  # Lusa (national wire)
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

    return f"""You are a strategic intelligence analyst briefing Alex, a 34-year-old solopreneur based in Portugal.
Alex is on a 6-year mission (2026-2032) to grow from €0 to €35,000 in savings and reach financial independence.
He is building digital skills, exploring solopreneur business models, and tracking global macro trends that affect his journey.

Analyze today's news headlines and extract maximum actionable value for Alex's €0 to €35k wealth journey:

{headlines_block}

Return ONLY valid JSON with NO markdown formatting, NO code blocks, NO extra text. Use exactly this structure:
{{
  "global_theme": "One sentence describing the dominant global narrative today and its relevance to someone building wealth from scratch in Europe.",
  "market_mood": "Short phrase describing overall market sentiment (e.g. Cautiously Bullish, Risk-Off, Tech Rotation).",
  "risk_signal": "The primary macro or financial risk Alex should be aware of right now (short phrase).",
  "opportunity_signal": "The most actionable opportunity today for a solopreneur building toward €35k (short phrase).",
  "key_points": [
    "Insight 1: How today's news affects Alex's €0 to €35k journey. Max 25 words, be specific.",
    "Insight 2: A market or tech trend Alex can learn from or act on. Max 25 words.",
    "Insight 3: A Portugal or EU angle relevant to building income or savings. Max 25 words.",
    "Insight 4: A solopreneur or digital business takeaway from today's headlines. Max 25 words.",
    "Insight 5: A frugality, saving, or low-cost investing angle. Max 25 words.",
    "Insight 6: A tech or AI development that could accelerate Alex's skill-building. Max 25 words.",
    "Insight 7: A global macro signal that affects European cost of living or opportunity. Max 25 words.",
    "Insight 8: A specific industry or niche showing growth Alex could target. Max 25 words.",
    "Insight 9: A mindset or strategy insight from today's stories. Max 25 words.",
    "Insight 10: The single most important thing for Alex to act on today. Max 25 words."
  ],
  "learning_task": "One specific 30-minute skill or concept Alex should study today, directly tied to today's news and his €35k goal.",
  "biz_opportunity": "One concrete solopreneur business gap identified from today's news — include the niche, target customer, and why now."
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
