#!/usr/bin/env python3
"""Regenera tests/golden/payload_slim_sample.json (muestra para el schema zod).

Genera el payload completo del fixture y lo trunca: cada lista queda en 5
elementos (estructura intacta, ~45 KB en vez de 3.9 MB). Correr tras cualquier
cambio intencional del payload y luego validar con: npm run check:payload
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "reports"))

from report_generator import ReportConfig, ReportGenerator  # noqa: E402

MAX_ITEMS = 5


def slim(obj):
    if isinstance(obj, dict):
        return {k: slim(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [slim(v) for v in obj[:MAX_ITEMS]]
    return obj


gen = ReportGenerator(
    str(REPO / "reports" / "fixtures" / "test_data_with_margins_normalized.csv"),
    ReportConfig(),
)
payload = gen.build_payload()
out = Path(__file__).parent / "golden" / "payload_slim_sample.json"
out.write_text(
    json.dumps(slim(payload), ensure_ascii=False, indent=1), encoding="utf-8"
)
print(f"Muestra regenerada: {out} ({out.stat().st_size} bytes)")
