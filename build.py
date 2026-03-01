"""
Personal Alpha - Daily News Briefing Engine
Fetches RSS feeds, analyzes with Gemini, writes JSON outputs.
"""

import os
import re
import html
import json
import logging
import calendar
from datetime import datetime, timezone

import feedparser
from google import genai

from config import (
    SECTION_LIMITS, GEMINI_MODEL, GEMINI_API_KEY,
    PORTUGAL_PRIORITY_SOURCES, DIVERSITY_THRESHOLD,
)

# ---------------------------------------------------------------------------
# CI Guard — GitHub Actions sets this env var automatically.
# When true the workflow handles git; the script must not run subprocess git.
# ---------------------------------------------------------------------------
IS_CI = os.getenv('GITHUB_ACTIONS') == 'true'

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
# RSS Feed Sources  (≥ DIVERSITY_THRESHOLD = 8 URLs per section)
# Verified-working feeds are listed first; fallbacks at the end.
# Dead URLs removed after build-log analysis on 2026-03-01.
# ---------------------------------------------------------------------------
RSS_FEEDS = {
    # ── Finance (10 URLs, 7 confirmed working) ───────────────────────────
    'Finance': [
        'https://feeds.content.dowjones.io/public/rss/mw_topstories',
            # MarketWatch Top Stories
        'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',
            # CNBC Markets
        'https://feeds.bloomberg.com/markets/news.rss',
            # Bloomberg Markets
        'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',
            # NYT Business
        'https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml',
            # NYT Economy
        'https://www.investing.com/rss/news.rss',
            # Investing.com
        'https://feeds.skynews.com/feeds/rss/business.xml',
            # Sky News Business
        'https://feeds.theguardian.com/theguardian/business/rss',
            # Guardian Business
        'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
            # WSJ Markets
        'https://finance.yahoo.com/news/rssindex',
            # Yahoo Finance
    ],

    # ── World News (9 URLs, 6 confirmed working) ─────────────────────────
    'World News': [
        'http://feeds.bbci.co.uk/news/world/rss.xml',
            # BBC World
        'https://www.aljazeera.com/xml/rss/all.xml',
            # Al Jazeera
        'https://feeds.npr.org/1004/rss.xml',
            # NPR World
        'https://feeds.theguardian.com/theguardian/world/rss',
            # Guardian World
        'https://rss.dw.com/rdf/rss-en-all',
            # Deutsche Welle (EU focus)
        'https://feeds.skynews.com/feeds/rss/world.xml',
            # Sky News World
        'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
            # NYT World
        'https://feeds.theguardian.com/theguardian/international/rss',
            # Guardian International
        'https://www.euronews.com/rss?format=mrss&level=theme&name=news',
            # Euronews (EU angle)
    ],

    # ── Tech (10 URLs, 9 confirmed working) ──────────────────────────────
    'Tech': [
        'https://www.theverge.com/rss/index.xml',
            # The Verge
        'https://www.wired.com/feed/rss',
            # Wired
        'https://sifted.eu/feed/',
            # Sifted EU (startup focus)
        'https://hnrss.org/frontpage',
            # Hacker News
        'https://techcrunch.com/feed/',
            # TechCrunch
        'https://feeds.arstechnica.com/arstechnica/index',
            # Ars Technica
        'https://www.technologyreview.com/feed/',
            # MIT Technology Review
        'https://venturebeat.com/feed/',
            # VentureBeat
        'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
            # NYT Technology
        'https://feeds.theguardian.com/theguardian/technology/rss',
            # Guardian Tech
    ],

    # ── Automotive / Motorcycle (9 URLs) ─────────────────────────────────
    # Note: MCN, Visordown, MotorTrend, Autoblog, RideApart return 0 —
    # replaced with verified alternatives.
    'Automotive/Motorcycle': [
        'https://www.caranddriver.com/rss/all.xml/',
            # Car & Driver ✅
        'https://www.motor1.com/rss/news/all/',
            # Motor1 ✅
        'https://www.roadandtrack.com/rss/all.xml/',
            # Road & Track ✅
        'https://jalopnik.com/rss',
            # Jalopnik
        'https://electrek.co/feed/',
            # Electrek (EV/future mobility)
        'https://insideevs.com/feed/',
            # InsideEVs
        'https://www.autocar.co.uk/rss',
            # Autocar (UK)
        'https://www.autosport.com/rss/feed/all',
            # Autosport (motorsport)
        'https://newatlas.com/feed/',
            # New Atlas (tech/mobility)
    ],

    # ── Portugal (9 URLs — 6 native priority + 3 English/fallback) ───────
    # Lusa & Público require auth headers — replaced with working natives.
    # Priority sources fill 60% (9/15 slots).
    'Portugal': [
        # ── priority / native ────────────────────────────────────────────
        'https://eco.pt/feed/',
            # ECO — economy & business
        'https://www.jornaldenegocios.pt/rss/',
            # Jornal de Negócios ✅
        'https://observador.pt/feed/',
            # Observador ✅
        'https://www.cmjornal.pt/rss/',
            # Correio da Manhã ✅
        'https://www.dinheirovivo.pt/feed/',
            # Dinheiro Vivo (finance-focused)
        'https://www.dn.pt/feed/',
            # Diário de Notícias
        # ── English / fallback ───────────────────────────────────────────
        'https://www.theportugalnews.com/rss/',
            # The Portugal News ✅
        'https://www.theportugalresident.com/feed/',
            # Portugal Resident
        'https://feeds.theguardian.com/theguardian/world/europe/rss',
            # Guardian Europe (includes PT coverage)
        'https://rss.dw.com/rdf/rss-en-eu',
            # DW Europe
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches literal CDATA wrappers that some feeds (e.g. Correio da Manhã)
# double-encode so feedparser passes them through as raw text.
_RE_CDATA   = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
# Any remaining HTML / XML tags
_RE_TAGS    = re.compile(r'<[^>]+>')
# Collapse runs of whitespace (spaces, tabs, newlines)
_RE_WS      = re.compile(r'\s+')


def _strip_text(raw: str) -> str:
    """
    Full sanitization pipeline for any text field from an RSS feed:
      1. HTML-entity unescape  (&amp; → &, &#39; → ', etc.)
      2. Unwrap CDATA literals  (<![CDATA[ ... ]]> → inner text)
      3. Strip all HTML/XML tags
      4. Collapse whitespace and strip leading/trailing space
    """
    if not raw:
        return ''
    text = html.unescape(raw)           # step 1
    text = _RE_CDATA.sub(r'\1', text)   # step 2  — catches CM double-encoding
    text = _RE_TAGS.sub('', text)       # step 3
    text = _RE_WS.sub(' ', text)        # step 4  — collapses \n, \t, spaces
    return text.strip()


def _pub_ts(entry) -> int:
    """Return a UTC unix timestamp for sorting (newest first)."""
    pt = getattr(entry, 'published_parsed', None)
    if pt:
        try:
            return calendar.timegm(pt)
        except Exception:
            pass
    return 0


def _make_article(entry, source_title: str) -> dict | None:
    """
    Build a normalised article dict from a feedparser entry.

    Title fallback chain:
      1. entry.title          (sanitized)
      2. entry.summary        (sanitized, truncated to 80 chars)
      3. entry.description    (sanitized, truncated to 80 chars)
      4. 'News Update from {source_title}'

    Returns None if the entry has no valid URL — those are silently dropped
    so they never appear in content.json or the Gemini prompt.
    """
    link = getattr(entry, 'link', '').strip()
    if not link:
        return None   # no URL → unusable entry, drop it

    # ── Title: try primary field first, then fallbacks ────────────────
    title = _strip_text(getattr(entry, 'title', '') or '')

    if not title:
        # Fallback 1: summary
        summary = _strip_text(getattr(entry, 'summary', '') or '')
        title = summary[:80] + ('…' if len(summary) > 80 else '') if summary else ''

    if not title:
        # Fallback 2: description
        desc = _strip_text(entry.get('description', '') or '')
        title = desc[:80] + ('…' if len(desc) > 80 else '') if desc else ''

    if not title:
        # Last resort placeholder — keeps the article but flags the gap
        title = f'News Update from {source_title}'
        log.warning(f'Empty title for {link} — using placeholder.')

    published = entry.get('published', '') or datetime.now(timezone.utc).isoformat()

    return {
        'title':     title,
        'source':    source_title,
        'published': published,
        'url':       link,
        '_ts':       _pub_ts(entry),
    }


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_section(section_name: str, urls: list, limit: int,
                  priority_urls: list = None) -> list:
    """
    Fetch articles from all `urls`, pool and sort by date (newest first),
    then return the top `limit`.

    Portugal mode: `priority_urls` reserves 60% of slots for native sources.
    Diversity: logs a warning if fewer than DIVERSITY_THRESHOLD URLs yield ≥1 result.
    """
    seen_urls        = set()
    priority_urls    = priority_urls or []
    urls_with_results = 0

    # ── Portugal priority path ──────────────────────────────────────────
    if priority_urls:
        priority_pool = []
        fallback_pool = []

        for url in urls:
            is_prio = url in priority_urls
            try:
                feed = feedparser.parse(url)
                src  = feed.feed.get('title', url)
                added = 0
                for entry in feed.entries:
                    link = getattr(entry, 'link', '').strip()
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    art = _make_article(entry, src)
                    # _make_article returns None if link is empty;
                    # also skip placeholder-only entries for the 60% priority pool
                    if art is None:
                        continue
                    if is_prio and art['title'].startswith('News Update from'):
                        log.debug(f"Skipping placeholder-only entry from priority source: {link}")
                        continue
                    art['is_priority'] = is_prio   # surfaced in content.json → CSS gold border
                    (priority_pool if is_prio else fallback_pool).append(art)
                    added += 1
                if added:
                    urls_with_results += 1
                log.info(f"[{section_name}] {len(feed.entries)} entries from {url} (prio={is_prio})")
            except Exception as exc:
                log.warning(f"[{section_name}] Failed {url}: {exc}")

        # Sort each pool newest first
        priority_pool.sort(key=lambda a: a['_ts'], reverse=True)
        fallback_pool.sort(key=lambda a: a['_ts'], reverse=True)

        prio_slots = round(limit * 0.6)
        articles   = priority_pool[:prio_slots] + fallback_pool[:limit - prio_slots]

    # ── Standard path ───────────────────────────────────────────────────
    else:
        pool = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                src  = feed.feed.get('title', url)
                added = 0
                for entry in feed.entries:
                    link = getattr(entry, 'link', '').strip()
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    art = _make_article(entry, src)
                    if art is None:
                        continue
                    art['is_priority'] = False
                    pool.append(art)
                    added += 1
                if added:
                    urls_with_results += 1
                log.info(f"[{section_name}] {len(feed.entries)} entries from {url}")
            except Exception as exc:
                log.warning(f"[{section_name}] Failed {url}: {exc}")

        # Sort newest first across ALL sources, then take top-limit
        pool.sort(key=lambda a: a['_ts'], reverse=True)
        articles = pool[:limit]

    # ── Diversity check ─────────────────────────────────────────────────
    if urls_with_results < DIVERSITY_THRESHOLD:
        log.warning(
            f"[{section_name}] DIVERSITY WARNING: {urls_with_results}/{len(urls)} "
            f"URLs returned results (need ≥{DIVERSITY_THRESHOLD})."
        )
    else:
        log.info(f"[{section_name}] Diversity OK: {urls_with_results}/{len(urls)} sources active.")

    # Strip internal sort key before returning
    for a in articles:
        a.pop('_ts', None)

    return articles


def fetch_all_news() -> dict:
    """Fetch all sections and return a dict keyed by section name."""
    sections = {}
    for section, urls in RSS_FEEDS.items():
        limit = SECTION_LIMITS.get(section, 15)
        prio  = PORTUGAL_PRIORITY_SOURCES if section == 'Portugal' else None
        arts  = fetch_section(section, urls, limit, priority_urls=prio)
        sections[section] = arts
        # Log unique source names for quick diversity audit
        uniq = sorted(set(a['source'] for a in arts))
        log.info(f"[{section}] {len(arts)} articles from {len(uniq)} source(s): {uniq}")
    return sections


# ---------------------------------------------------------------------------
# Gemini Analysis
# ---------------------------------------------------------------------------

def build_prompt(sections: dict) -> str:
    """
    Compressed prompt.
    - Finance headlines get single-char sentiment (+/-/=) to save tokens.
    - Insights split into 3 thematic groups of 5 bullets.
    """
    lines = []
    for section, articles in sections.items():
        lines.append(f"\n## {section}")
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. {a['title']} [{a['source']}]")
    headlines_block = '\n'.join(lines)

    return f"""You are a strategic analyst briefing Alex, 34-yr solopreneur, Portugal, mission: €0→€35k by 2032-05-27.

HEADLINES:
{headlines_block}

OUTPUT: valid JSON only, no markdown, no extra text.

Schema (ALL fields required, exact keys):
{{
  "global_theme": "<1 sentence: dominant narrative + EU/wealth relevance>",
  "market_mood": "<short phrase, e.g. Risk-Off>",
  "risk_signal": "<short phrase>",
  "opportunity_signal": "<short phrase>",
  "finance_sentiment": [
    {{"i": 1, "s": "+"}},
    {{"i": 2, "s": "-"}},
    {{"i": 3, "s": "="}},
    ...one object per Finance headline, "s" must be +, -, or = only
  ],
  "insights": {{
    "g1": ["<25w>","<25w>","<25w>","<25w>","<25w>"],
    "g2": ["<25w>","<25w>","<25w>","<25w>","<25w>"],
    "g3": ["<25w>","<25w>","<25w>","<25w>","<25w>"]
  }},
  "learning_task": "<30-min skill tied to today's news + €35k goal, 1 sentence>",
  "biz_opportunity": "<niche + target customer + why now, 1 plain sentence, no sub-keys>"
}}

Rules:
- insights g1: macro/finance angles for Alex's €0→€35k journey
- insights g2: tech/AI/skill angles that accelerate Alex's capabilities
- insights g3: Portugal/EU/solopreneur angles for building local income
- finance_sentiment: index matches the Finance section numbered list; score EVERY headline
- biz_opportunity: plain string only, absolutely no nested JSON"""


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

    # Strip markdown code fences if present
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1]
        raw = raw.rsplit('```', 1)[0].strip()

    summary = json.loads(raw)

    # Validate schema
    required = {
        'global_theme', 'market_mood', 'risk_signal', 'opportunity_signal',
        'finance_sentiment', 'insights', 'learning_task', 'biz_opportunity',
    }
    missing = required - set(summary.keys())
    if missing:
        log.warning(f"Gemini response missing keys: {missing}")

    # Enforce biz_opportunity is a plain string
    biz = summary.get('biz_opportunity', '')
    if isinstance(biz, dict):
        summary['biz_opportunity'] = ' · '.join(str(v) for v in biz.values())
        log.warning("biz_opportunity was an object — flattened to string.")

    n_sent = len(summary.get('finance_sentiment', []))
    n_fin  = len(sections.get('Finance', []))
    log.info(f"Finance sentiment: {n_sent}/{n_fin} headlines scored.")
    log.info("Gemini JSON parsed successfully.")
    return summary


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(sections: dict, summary: dict) -> None:
    """Write content.json and summary.json."""
    now = datetime.now(timezone.utc).isoformat()

    content = {'built_at': now, 'sections': sections}
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
    log.info("=" * 60)
    log.info("Build started")
    if IS_CI:
        log.info("Running in GitHub Actions (CI=true) — git commits handled by workflow.")

    sections = fetch_all_news()
    total    = sum(len(v) for v in sections.values())
    log.info(f"Total articles fetched: {total}")

    if total == 0:
        log.error("No articles fetched. Aborting.")
        raise RuntimeError("No articles were fetched from any RSS feed.")

    summary = analyze_with_gemini(sections)
    write_outputs(sections, summary)

    log.info("Build complete.")
    print(f"Build successful. {total} articles. content.json + summary.json updated.")


if __name__ == '__main__':
    main()
