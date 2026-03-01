import os

# --- Goal ---
TARGET_DATE = '2032-05-27'
START_DATE  = '2026-03-01'
GOAL_DAYS   = 2279   # 2026-03-01 → 2032-05-27 (6.2 years)

# --- News Section Limits ---
SECTION_LIMITS = {
    'Finance':               15,
    'World News':            15,
    'Tech':                  15,
    'Automotive/Motorcycle': 15,
    'Portugal':              15,
}

# Minimum unique RSS URLs that must be attempted per section before
# the top-15 are selected. Build will log a warning if a section
# can only reach fewer sources than this threshold.
DIVERSITY_THRESHOLD = 8

# Portugal source priority (60% of 15 = 9 slots reserved)
# Verified working as of 2026-03-01; Lusa/Público require auth so excluded.
PORTUGAL_PRIORITY_SOURCES = [
    'https://eco.pt/feed/',
    'https://www.jornaldenegocios.pt/rss/',
    'https://observador.pt/feed/',
    'https://www.cmjornal.pt/rss/',
    'https://www.dinheirovivo.pt/feed/',
    'https://www.dn.pt/feed/',
]

# --- Gemini ---
GEMINI_MODEL   = 'gemini-2.5-flash'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
