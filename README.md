# DSCR Dashboard Assembler (Streamlit)

This project deterministically assembles a DSCR HTML dashboard by:
1) Loading the immutable HTML shell (`assets/dashboard_shell.html`) up to the marker `// [PART A: DATA INJECTION]`
2) Injecting data variables (from a JSON payload)
3) Appending the immutable JS engine (`assets/dashboard_engine.txt`) verbatim
4) Closing HTML tags and offering the assembled HTML for download

## Repo structure
- app.py
- requirements.txt
- assets/dashboard_shell.html
- assets/dashboard_engine.txt
- rules/bankRules.json
- samples/sample_payload.json

## Run locally
pip install -r requirements.txt
streamlit run app.py

## Deploy on Streamlit Cloud
- Push the repo to GitHub
- In Streamlit Cloud: New app -> select repo/branch -> main file: app.py

## Input payload
Paste JSON from your Custom GPT (DSCR JSON Extractor) or upload a JSON file.
