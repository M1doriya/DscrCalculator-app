import json
from pathlib import Path
import streamlit as st

ASSETS_DIR = Path("assets")
RULES_DIR = Path("rules")

SHELL_PATH = ASSETS_DIR / "dashboard_shell.html"
ENGINE_PATH = ASSETS_DIR / "dashboard_engine.txt"
BANKRULES_FULL_PATH = RULES_DIR / "bankRules.json"

INJECTION_MARKER = "// [PART A: DATA INJECTION]"

APP_BUILD = "BUILD_001"  # change this each commit so you can confirm Streamlit deployed latest code


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return s


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_json(path: Path) -> dict:
    return json.loads(load_text(path))


def split_shell(shell_html: str) -> tuple[str, str]:
    idx = shell_html.find(INJECTION_MARKER)
    if idx == -1:
        raise ValueError(f"Injection marker not found: {INJECTION_MARKER}")
    prefix = shell_html[: idx + len(INJECTION_MARKER)]
    suffix = shell_html[idx + len(INJECTION_MARKER) :]
    return prefix, suffix


def validate_payload(p: dict) -> list[str]:
    issues = []
    required = ["auditedYearsDetected", "historicalData", "companyFacilities", "directorFacilities"]
    for k in required:
        if k not in p:
            issues.append(f"Missing required key: {k}")
    if "auditedYearsDetected" in p and not p.get("auditedYearsDetected"):
        issues.append("auditedYearsDetected is empty (must include at least one audited year).")
    return issues


def derive_bank_rules_from_full(bank_rules_full: dict) -> dict:
    """
    Convert bankRulesFull (authoritative) into dscr_fixed_v3-style bankRules:

      bankRules = {
        "Bank": {
          "allowFinancial": bool,
          "allowNonFinancial": bool,
          "minFinancial": number|null,
          "minNonFinancial": number|null,
          "turnoverMultiplier": 1.2 (optional),
          "adjustment": "excludeOtherIncome" (optional)
        }
      }

    - No hardcoded bank list (derived from keys).
    - Optional fields derived from the *rule text*, not bank names.
    """
    out = {}
    banks = (bank_rules_full or {}).get("banks") or {}

    for bank_name, bank_obj in banks.items():
        models = (bank_obj or {}).get("models") or {}
        fin = models.get("financial") or {}
        non = models.get("non_financial") or {}

        entry = {
            "allowFinancial": bool(fin.get("enabled")),
            "allowNonFinancial": bool(non.get("enabled")),
            "minFinancial": fin.get("min_dscr"),
            "minNonFinancial": non.get("min_dscr"),
        }

        # Derived adjustment: excludeOtherIncome (if mentioned)
        fin_text = (fin.get("formula_text") or "") + "\n" + (bank_obj.get("eligibility_notes") or "")
        fin_text_l = fin_text.lower()
        if "exclude" in fin_text_l and "other income" in fin_text_l:
            entry["adjustment"] = "excludeOtherIncome"

        # Derived turnoverMultiplier = 1.2 if rule mentions 20% note
        non_text = (non.get("formula_text") or "") + "\n" + (bank_obj.get("eligibility_notes") or "")
        non_text_l = non_text.lower()
        if "20%" in non_text_l or "20 %" in non_text_l:
            entry["turnoverMultiplier"] = 1.2

        out[bank_name] = entry

    return out


def build_injection_block(payload: dict) -> str:
    audited_years = payload.get("auditedYearsDetected", [])
    historical = payload.get("historicalData", {})
    company_fac = payload.get("companyFacilities", [])
    director_fac = payload.get("directorFacilities", [])

    # Prefer payload.bankRules (highest fidelity)
    bank_rules = payload.get("bankRules")

    # Otherwise derive from bankRulesFull (payload or rules/bankRules.json)
    bank_rules_full = payload.get("bankRulesFull")
    if bank_rules is None:
        if bank_rules_full is None and BANKRULES_FULL_PATH.exists():
            bank_rules_full = load_json(BANKRULES_FULL_PATH)
        bank_rules = derive_bank_rules_from_full(bank_rules_full or {})

    def js(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    # IMPORTANT: names MUST match dscr_fixed_v3 constants
    return "\n".join(
        [
            "",
            "        // =============================================",
            "        // [INJECTED BY STREAMLIT ASSEMBLER]",
            "        // =============================================",
            f"        const auditedYearsDetected = {js(audited_years)};",
            f"        const historicalData = {js(historical)};",
            f"        const bankRules = {js(bank_rules)};",
            f"        const companyFacilities = {js(company_fac)};",
            f"        const directorFacilities = {js(director_fac)};",
            "",
        ]
    )


def assemble_html(payload: dict) -> str:
    if not SHELL_PATH.exists():
        raise FileNotFoundError(f"Missing: {SHELL_PATH}")
    if not ENGINE_PATH.exists():
        raise FileNotFoundError(f"Missing: {ENGINE_PATH}")

    shell = load_text(SHELL_PATH)
    engine = load_text(ENGINE_PATH)

    prefix, suffix = split_shell(shell)
    injection = build_injection_block(payload)

    # CRITICAL: keep suffix and do NOT append closing tags manually.
    # Engine (extracted from dscr_fixed_v3) includes correct closing tags.
    return "".join([prefix, injection, suffix, engine])


st.set_page_config(page_title="DSCR Dashboard Assembler", layout="wide")
st.title("DSCR Dashboard Assembler")
st.sidebar.write("BUILD:", APP_BUILD)

st.write("Upload or paste your JSON payload and download the assembled dscr_fixed_v3 HTML dashboard.")

raw = st.text_area("Paste JSON payload", height=260)
up = st.file_uploader("Or upload JSON file", type=["json"])

payload = None
err = None

if up is not None:
    try:
        raw_text = up.read().decode("utf-8", errors="replace")
        raw_text = strip_code_fences(raw_text)
        payload = json.loads(raw_text)
    except Exception as e:
        err = f"Upload JSON parse failed: {e}"
elif raw.strip():
    try:
        raw_text = strip_code_fences(raw)
        payload = json.loads(raw_text)
    except Exception as e:
        err = f"Paste JSON parse failed: {e}"

if err:
    st.error(err)
    st.stop()

if payload is None:
    st.info("Provide a payload to assemble the dashboard.")
    st.stop()

issues = validate_payload(payload)
if issues:
    st.error("Payload validation failed:\n- " + "\n- ".join(issues))
    st.stop()

try:
    html_out = assemble_html(payload)
except Exception as e:
    st.error(f"Assembly failed: {e}")
    st.stop()

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

with st.expander("Debug: what files Streamlit is really using (click to open)", expanded=False):
    shell_txt = load_text(SHELL_PATH)
    engine_txt = load_text(ENGINE_PATH)

    st.write("SHELL exists:", SHELL_PATH.exists(), "path:", str(SHELL_PATH))
    st.write("ENGINE exists:", ENGINE_PATH.exists(), "path:", str(ENGINE_PATH))

    # These help confirm you are on the real dscr_fixed_v3 assets, not a simplified one
    st.write("Shell contains gaugeNeedle:", "gaugeNeedle" in shell_txt)
    st.write('Shell contains id="dscrGauge":', 'id="dscrGauge"' in shell_txt)
    st.write("Engine contains ensureBankDropdown:", "ensureBankDropdown" in engine_txt)
    st.write("Engine contains dscr_dashboard_state:", "dscr_dashboard_state" in engine_txt)

    st.info(
        "If these indicators do not match dscr_fixed_v3, you must regenerate assets locally using: "
        "python tools/extract_fixed_v3_assets.py and commit assets/dashboard_shell.html and assets/dashboard_engine.txt."
    )
