import os

# --- Goal ---
TARGET_DATE = '2032-03-01'

# --- News Section Limits ---
SECTION_LIMITS = {
    'Finance': 5,
    'World News': 5,
    'Tech': 10,
    'Automotive/Motorcycle': 5,
    'Portugal': 5,
}

# --- Gemini ---
GEMINI_MODEL = 'gemini-2.5-flash'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
