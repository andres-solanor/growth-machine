#!/usr/bin/env python3
"""Regenera tests/golden/sales_report_golden.json tras un cambio intencional
del payload. Revisar el diff del golden antes de commitear."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "reports"))

from report_generator import ReportConfig, ReportGenerator  # noqa: E402

gen = ReportGenerator(
    str(REPO / "reports" / "fixtures" / "test_data_with_margins_normalized.csv"),
    ReportConfig(),
)
payload = gen.build_payload()
golden = {
    "summary": payload["summary"],
    "quality": payload["quality"],
    "analyses_keys": sorted(payload["analyses"].keys()),
    "n_insights": len(payload["insights"]),
    "n_recommendations": len(payload["recommendations"]),
}
out = Path(__file__).parent / "golden" / "sales_report_golden.json"
out.write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
print(f"Golden regenerado: {out}")
