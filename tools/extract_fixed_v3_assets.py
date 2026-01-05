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
        raise SystemExit(f"Missing template: {SRC}")

    html = SRC.read_text(encoding="utf-8", errors="ignore")

    # Start at auditedYearsDetected
    m_start = re.search(r"\n\s*const\s+auditedYearsDetected\s*=", html)
    if not m_start:
        raise SystemExit("Cannot find: const auditedYearsDetected = ...")

    data_start = m_start.start()

    # End after directorFacilities (dscr_fixed_v3 data block includes:
    # auditedYearsDetected, historicalData, bankRules, companyFacilities, directorFacilities)
    m_end = re.search(
        r"\n\s*const\s+directorFacilities\s*=\s*.*?;\s*\n",
        html[data_start:],
        flags=re.S,
    )
    if not m_end:
        raise SystemExit("Cannot find: const directorFacilities = ...; after auditedYearsDetected")

    data_end = data_start + m_end.end()

    shell = html[:data_start].rstrip() + "\n\n  " + MARKER + "\n"
    engine = html[data_end:]  # keep everything else verbatim, including closing tags

    OUT_SHELL.write_text(shell, encoding="utf-8")
    OUT_ENGINE.write_text(engine, encoding="utf-8")

    print("Generated:")
    print(" -", OUT_SHELL)
    print(" -", OUT_ENGINE)


if __name__ == "__main__":
    main()
