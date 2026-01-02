from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "dscr_fixed_v3.html"
OUT_SHELL = ROOT / "assets" / "dashboard_shell.html"
OUT_ENGINE = ROOT / "assets" / "dashboard_engine.txt"

MARKER = "// [PART A: DATA INJECTION]"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source template: {SRC}")

    html = SRC.read_text(encoding="utf-8")

    # Find the beginning of DATA block: auditedYearsDetected
    m_start = re.search(r"\n\s*const\s+auditedYearsDetected\s*=", html)
    if not m_start:
        raise SystemExit("Cannot find 'const auditedYearsDetected =' in dscr_fixed_v3.html")

    data_start = m_start.start()

    # Find the end of DATA block: after "const bankRules = ...;"
    m_end = re.search(r"\n\s*const\s+bankRules\s*=\s*.*?;\s*\n", html[data_start:], flags=re.S)
    if not m_end:
        raise SystemExit("Cannot find 'const bankRules = ...;' after auditedYearsDetected")

    data_end = data_start + m_end.end()

    # Shell = everything BEFORE DATA block + marker inserted.
    shell = html[:data_start].rstrip() + "\n\n  " + MARKER + "\n"

    # Engine = everything AFTER DATA block (includes rest of <script> and closing tags).
    engine = html[data_end:]

    OUT_SHELL.write_text(shell, encoding="utf-8")
    OUT_ENGINE.write_text(engine, encoding="utf-8")

    print("OK - generated:")
    print(f"- {OUT_SHELL}")
    print(f"- {OUT_ENGINE}")


if __name__ == "__main__":
    main()
