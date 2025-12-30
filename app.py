import json
from pathlib import Path
import streamlit as st

ASSETS_DIR = Path("assets")
RULES_DIR = Path("rules")

SHELL_PATH = ASSETS_DIR / "dashboard_shell.html"
ENGINE_PATH = ASSETS_DIR / "dashboard_engine.txt"
BANKRULES_PATH = RULES_DIR / "bankRules.json"

INJECTION_MARKER = "// [PART A: DATA INJECTION]"

def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def load_json(path: Path) -> dict:
    return json.loads(load_text(path))

def split_shell(shell_html: str) -> tuple[str, str]:
    idx = shell_html.find(INJECTION_MARKER)
    if idx == -1:
        raise ValueError(f"Injection marker not found: {INJECTION_MARKER}")
    prefix = shell_html[:idx + len(INJECTION_MARKER)]
    suffix = shell_html[idx + len(INJECTION_MARKER):]
    return prefix, suffix

def derive_bank_rules(bank_rules_full: dict) -> dict:
    # Derived from bankRulesFull only. No hardcoding.
    out = {}
    banks = bank_rules_full.get("banks") or {}
    for bank_name, bank_obj in banks.items():
        models = bank_obj.get("models") or {}
        fin = models.get("financial") or {}
        non = models.get("non_financial") or {}
        out[bank_name] = {
            "allowFinancial": bool(fin.get("enabled")),
            "allowNonFinancial": bool(non.get("enabled")),
            "minFinancial": fin.get("min_dscr"),
            "minNonFinancial": non.get("min_dscr"),
        }
    return out

def build_injection_block(payload: dict) -> str:
    audited_years = payload.get("auditedYearsDetected", [])
    historical = payload.get("historicalData", {})
    company_fac = payload.get("companyFacilities", [])
    director_fac = payload.get("directorFacilities", [])

    bank_rules_full = payload.get("bankRulesFull")
    if bank_rules_full is None:
        bank_rules_full = load_json(BANKRULES_PATH)

    bank_rules = derive_bank_rules(bank_rules_full)

    def js(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    return "\n".join([
        "",
        "        // =============================================",
        "        // [INJECTED BY STREAMLIT ASSEMBLER]",
        "        // =============================================",
        f"        const auditedYearsDetected = {js(audited_years)};",
        f"        const historicalData = {js(historical)};",
        f"        const companyFacilities = {js(company_fac)};",
        f"        const directorFacilities = {js(director_fac)};",
        f"        const bankRulesFull = {js(bank_rules_full)};",
        "        // Derived from bankRulesFull only (never hardcoded)",
        f"        const bankRules = {js(bank_rules)};",
        "",
    ])

def assemble_html(payload: dict) -> str:
    shell = load_text(SHELL_PATH)
    engine = load_text(ENGINE_PATH)

    prefix, _ = split_shell(shell)
    injection = build_injection_block(payload)

    return "".join([
        prefix,
        injection,
        "\n",
        engine,
        "\n</script></body></html>\n",
    ])

st.set_page_config(page_title="DSCR Dashboard Assembler", layout="wide")
st.title("DSCR Dashboard Assembler (GitHub Deployment)")

st.write("Paste JSON from the DSCR JSON Extractor GPT, or upload a JSON file. The app assembles your dashboard HTML deterministically.")

raw = st.text_area("JSON payload", height=260)
up = st.file_uploader("Or upload JSON", type=["json"])

payload = None
err = None

if up is not None:
    try:
        payload = json.loads(up.read().decode("utf-8"))
    except Exception as e:
        err = f"Upload JSON parse failed: {e}"
elif raw.strip():
    try:
        payload = json.loads(raw)
    except Exception as e:
        err = f"Paste JSON parse failed: {e}"

if err:
    st.error(err)

def validate_minimum(p: dict) -> list[str]:
    issues = []
    for k in ["auditedYearsDetected", "historicalData", "companyFacilities", "directorFacilities"]:
        if k not in p:
            issues.append(f"Missing key: {k}")
    if "auditedYearsDetected" in p and not p["auditedYearsDetected"]:
        issues.append("auditedYearsDetected is empty (Section H needs latest audited year).")
    return issues

if payload:
    issues = validate_minimum(payload)
    if issues:
        st.error("Payload validation failed:\n- " + "\n- ".join(issues))
    else:
        try:
            html_out = assemble_html(payload)
            st.success("HTML assembled successfully.")
            st.download_button(
                "Download DSCR Dashboard HTML",
                data=html_out.encode("utf-8"),
                file_name="dscr_dashboard.html",
                mime="text/html",
            )
            st.download_button(
                "Download Payload JSON (backup)",
                data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="dscr_payload.json",
                mime="application/json",
            )
        except Exception as e:
            st.error(f"Assembly failed: {e}")
