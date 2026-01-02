import json
from pathlib import Path
import streamlit as st

ASSETS_DIR = Path("assets")
RULES_DIR = Path("rules")

SHELL_PATH = ASSETS_DIR / "dashboard_shell.html"
ENGINE_PATH = ASSETS_DIR / "dashboard_engine.txt"
BANKRULES_PATH = RULES_DIR / "bankRules.json"

INJECTION_MARKER = "// [PART A: DATA INJECTION]"


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return s


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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

    # dscr_fixed_v3 engine expects bankRules (it exists in the original template)
    # We can inject bankRules derived from bankRulesFull or from rules/bankRules.json,
    # but best fidelity is to include bankRules in payload.
    if "bankRules" not in p and "bankRulesFull" not in p and not BANKRULES_PATH.exists():
        issues.append(
            "Missing bankRules/bankRulesFull and rules/bankRules.json not found. "
            "Provide bank rules or commit rules/bankRules.json."
        )
    return issues


def derive_bank_rules_minimal(bank_rules_full: dict) -> dict:
    """
    Minimal fallback only.
    IMPORTANT: dscr_fixed_v3 may use extra keys (turnoverMultiplier, adjustment, etc.)
    If you want exact dscr_fixed_v3 behavior, include `bankRules` in payload.
    """
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

    # dscr_fixed_v3 uses bankRules. Prefer payload.bankRules if provided.
    bank_rules = payload.get("bankRules")

    # bankRulesFull can come from payload, or repo file
    bank_rules_full = payload.get("bankRulesFull")
    if bank_rules_full is None and BANKRULES_PATH.exists():
        bank_rules_full = load_json(BANKRULES_PATH)

    # If bankRules isn't provided, derive a minimal fallback from bankRulesFull
    if bank_rules is None:
        bank_rules = derive_bank_rules_minimal(bank_rules_full or {})

    def js(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    # IMPORTANT: define the same constants dscr_fixed_v3 expects.
    # We also define bankRulesFull for your newer workflows (harmless if unused).
    return "\n".join(
        [
            "",
            "  // =============================================",
            "  // [INJECTED BY STREAMLIT ASSEMBLER]",
            "  // =============================================",
            f"  const auditedYearsDetected = {js(audited_years)};",
            f"  const historicalData = {js(historical)};",
            f"  const bankRules = {js(bank_rules)};",
            f"  const companyFacilities = {js(company_fac)};",
            f"  const directorFacilities = {js(director_fac)};",
            f"  const bankRulesFull = {js(bank_rules_full or {})};",
            "",
        ]
    )


def assemble_html(payload: dict) -> str:
    if not SHELL_PATH.exists():
        raise FileNotFoundError(f"Missing shell: {SHELL_PATH}")
    if not ENGINE_PATH.exists():
        raise FileNotFoundError(f"Missing engine: {ENGINE_PATH}")

    shell = load_text(SHELL_PATH)
    engine = load_text(ENGINE_PATH)

    prefix, suffix = split_shell(shell)
    injection = build_injection_block(payload)

    # CRITICAL FIX:
    # - keep suffix (do NOT drop it)
    # - do NOT append hardcoded </script></body></html>
    # because engine extracted from dscr_fixed_v3 already includes the proper closings.
    return "".join([prefix, injection, suffix, engine])


st.set_page_config(page_title="DSCR Dashboard Assembler", layout="wide")
st.title("DSCR Dashboard Assembler")

st.write(
    "Upload or paste a JSON payload (from your Custom GPT) and download a deterministically assembled HTML dashboard."
)

with st.expander("Debug help", expanded=False):
    st.markdown(
        """
Common issues:
- JSON wrapped in ``` fences: this app strips them automatically.
- Missing keys: must include auditedYearsDetected, historicalData, companyFacilities, directorFacilities.
- If you want dscr_fixed_v3 bank logic 100% identical, include `bankRules` in the payload (same shape as dscr_fixed_v3).
- Template files missing: ensure assets/ and rules/ are committed to GitHub exactly as named.
"""
    )

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

with st.expander("View parsed payload (for troubleshooting)", expanded=False):
    st.json(payload)
