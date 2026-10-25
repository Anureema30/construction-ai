# 🏗️ Multimodal Construction Intelligence Platform

An AI-powered Streamlit decision-support app for construction sites, built with Google Gemini. Skill Wallet Capstone Project.

**Live demo:** https://construction-intel.streamlit.app/

## Features

| Module | What it does |
|---|---|
| 🦺 Site Safety & PPE Audit | Upload a site photo and get a safety score, PPE checklist (helmet, vest, boots, harness), hazards with severity and remedies, and a downloadable JSON report |
| 🧱 Crack Diagnostics | Classifies defects (hairline, settlement, shear, thermal, spalling), estimates crack width, severity and urgency, and suggests repairs |
| 💰 Planning & Valuation | Estimates budget, capex, current asset value in INR (Lakh/Crore), steel and cement needs, milestone progress, and a 3D concept render |
| 🌦️ Site Assistant | Weather-aware safety alerts and a multi-turn construction engineering chatbot |

If no API key is supplied, the app runs in **demonstration mode** with sample outputs.

## Tech Stack

Python 3.9+, Streamlit, Google Gemini (`google-genai`), Pillow, Pollinations AI

## Architecture

```
Image / inputs → Streamlit UI → Prompt + JSON contract → Gemini multimodal model → Validated JSON → UI + export
```

No database is used. State lives only in the browser session.

## Getting Started

```bash
git clone https://github.com/anureema30/construction-ai.git
cd construction-ai
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501.

## API Key

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey), then either:

- paste it into the app sidebar, or
- create `.streamlit/secrets.toml` containing `GOOGLE_API_KEY = "your-key"` (this file is git-ignored)

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io), click **Create app** and choose the repo with `app.py` as the main file.
3. Optional: add `GOOGLE_API_KEY` under Advanced settings → Secrets.

## Disclaimer

Outputs are AI-generated screenings and cost estimates based on indicative rates. They are not a certified safety audit, structural inspection, or professional valuation. Consult qualified engineers before acting on them.

## License

MIT, see [LICENSE](LICENSE).
