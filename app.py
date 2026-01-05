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


def derive_bank_rules(bank_rules_full: dict) -> dict:
    """
    Derived from bankRulesFull only (no hardcoding).
    Keep this lightweight map if your engine expects `bankRules` too.
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


def validate_payload(p: dict) -> list[str]:
    issues = []
    required = ["auditedYearsDetected", "historicalData", "companyFacilities", "directorFacilities"]
    for k in required:
        if k not in p:
            issues.append(f"Missing required key: {k}")
    if "auditedYearsDetected" in p and not p.get("auditedYearsDetected"):
        issues.append("auditedYearsDetected is empty (must include at least one audited year).")
    return issues


def build_injection_block(payload: dict) -> str:
    audited_years = payload.get("auditedYearsDetected", [])
    historical = payload.get("historicalData", {})
    company_fac = payload.get("companyFacilities", [])
    director_fac = payload.get("directorFacilities", [])

    # CRITICAL: bankRulesFull must exist for Section H and draft logic
    bank_rules_full = payload.get("bankRulesFull")
    if not bank_rules_full:
        bank_rules_full = load_json(BANKRULES_PATH)

    bank_rules = derive_bank_rules(bank_rules_full)

    def js(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    # IMPORTANT: inject bankRulesFull, then bankRules
    return "\n".join(
        [
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
            "        // Compatibility aliases (safe no-ops if unused by the engine)",
            "        const existingCommitments = companyFacilities;",
            "        const directorsCommitments = directorFacilities;",
            "",
        ]
    )


def assemble_html(payload: dict) -> str:
    shell = load_text(SHELL_PATH)
    engine = load_text(ENGINE_PATH)

    prefix, _suffix = split_shell(shell)
    injection = build_injection_block(payload)

    # Shell ends inside <script>; engine ends before </script>
    return "".join([prefix, injection, "\n", engine, "\n</script></body></html>\n"])


st.set_page_config(page_title="DSCR Dashboard Assembler", layout="wide")
st.title("DSCR Dashboard Assembler")

st.write("Upload or paste a JSON payload and download a deterministically assembled DSCR dashboard HTML.")

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

with st.expander("View parsed payload (for troubleshooting)", expanded=False):
    st.json(payload)
