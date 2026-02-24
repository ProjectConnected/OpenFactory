#!/usr/bin/env python3
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "pipeline.mmd"

MERMAID = """flowchart TD
  S0["Stage 0: PREFLIGHT"] --> S1["Stage 1: SPEC"]
  S1 --> S2["Stage 2: ARCH"]
  S2 --> S3["Stage 3: TICKETS"]
  S3 --> S4["Stage 4: IMPLEMENT_LOOP"]
  S4 --> S5["Stage 5: INTEGRATION"]
  S5 --> S6["Stage 6: PR_CI_GATE"]
  S6 -->|tests=success| S7["Stage 7: RELEASE"]
  S6 -->|tests!=success and retries left| S4
  S6 -->|tests!=success and retries exhausted| SF["ci_failed"]
"""

OUT.write_text(MERMAID, encoding="utf-8")
print(f"wrote {OUT}")
