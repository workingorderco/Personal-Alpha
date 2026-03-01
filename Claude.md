# Daily News Briefing System Spec

## Tech Stack
- Frontend: Vanilla HTML/CSS/JS (Zero dependencies)
- Backend: Python 3.11+
- APIs: Google Gemini 1.5 Flash (Free Tier)
- Automation: GitHub Actions + Python subprocess for Git
- Data: Local JSON files (`content.json`, `summary.json`)

## Build Commands
- Install: `pip install -r requirements.txt`
- Manual Run: `python build.py`

## Style Guidelines
- HTML: Single-file `index.html`, dark premium theme, mobile-first.
- Python: Modular functions, clear logging to `build.log`.
- JSON: Strict adherence to the schema defined in the prompt.

## Verification
- Validate JSON schemas after generation.
- Ensure `index.html` renders even if one JSON file is missing.