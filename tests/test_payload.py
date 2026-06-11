"""Tests del contrato de payload JSON (Fase 0 — ver docs/SAAS-PLAN.md).

Golden test: si un cambio intencional altera el payload, regenerar el golden:
    python - <<'EOF'   (ver tests/golden/README dentro del propio JSON: summary,
    quality, claves de analyses y conteos se regeneran con build_payload())
    EOF
o simplemente correr: python tests/regen_golden.py
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "reports"))

from report_generator import (  # noqa: E402
    PAYLOAD_SCHEMA_VERSION,
    ReportConfig,
    ReportGenerator,
    to_jsonable,
)

FIXTURE_CSV = REPO / "reports" / "fixtures" / "test_data_with_margins_normalized.csv"
GOLDEN_FILE = Path(__file__).parent / "golden" / "sales_report_golden.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    gen = ReportGenerator(str(FIXTURE_CSV), ReportConfig())
    return gen.build_payload()


def test_payload_is_strict_json(payload):
    # allow_nan=False revienta si quedó algún NaN/inf sin convertir
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    assert json.loads(text) is not None


def test_top_level_structure(payload):
    assert set(payload) == {"meta", "summary", "quality", "analyses", "insights", "recommendations"}
    meta = payload["meta"]
    assert meta["schema_version"] == PAYLOAD_SCHEMA_VERSION
    assert meta["report_type"] == "sales_report"
    assert meta["currency"] == "COP"
    assert isinstance(meta["config"], dict)


def test_golden_snapshot(payload):
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    # generated_at varía; summary/quality/estructura deben ser estables
    assert payload["summary"] == golden["summary"]
    assert payload["quality"] == golden["quality"]
    assert sorted(payload["analyses"].keys()) == golden["analyses_keys"]
    assert len(payload["insights"]) == golden["n_insights"]
    assert len(payload["recommendations"]) == golden["n_recommendations"]


def test_summary_has_iso_dates(payload):
    s = payload["summary"]
    assert s["date_min_iso"] and len(s["date_min_iso"]) == 10
    assert s["date_max_iso"] >= s["date_min_iso"]


def test_insights_are_plain_dicts(payload):
    for ins in payload["insights"]:
        assert set(ins) >= {"title", "body", "category", "severity", "priority"}
        assert isinstance(ins["priority"], int)


def test_to_jsonable_scalars():
    assert to_jsonable(np.int64(5)) == 5
    assert to_jsonable(np.float64(2.5)) == 2.5
    assert to_jsonable(float("nan")) is None
    assert to_jsonable(np.float64("inf")) is None
    assert to_jsonable(pd.NaT) is None
    assert to_jsonable(pd.Timestamp("2026-01-02 13:00")) == "2026-01-02T13:00:00"
    assert to_jsonable({("a", 1): np.bool_(True)}) == {"('a', 1)": True}


def test_to_jsonable_dataframe_records():
    df = pd.DataFrame({"x": [1, np.nan], "f": pd.to_datetime(["2026-01-01", None])})
    out = to_jsonable(df)
    assert out == [
        {"x": 1.0, "f": "2026-01-01T00:00:00"},
        {"x": None, "f": None},
    ]


def test_config_from_dict_aliases_and_unknown_keys(caplog):
    cfg = ReportConfig.from_dict({
        "store_name": "Tenant X",
        "currency": "MXN",
        "columns": {"date": "Date", "order_id": "Ticket"},
        "campo_inventado": 1,
    })
    assert cfg.store_name == "Tenant X"
    assert cfg.currency == "MXN"
    assert cfg.col_date == "Date"
    assert cfg.col_order_id == "Ticket"
    # los desconocidos no rompen, solo avisan
    assert cfg.pareto_threshold == 80.0


def test_worker_fallback_without_product_map():
    sys.path.insert(0, str(REPO / "worker"))
    import run_job

    frames = [pd.read_csv(REPO / "reports" / "input_data" / "sales_carts_sample.csv", dtype=str)[
        ["Fecha", "Hora", "Código venta", "Producto", "Cantidad", "Individual", "Total"]
    ]]
    out = run_job._normalize(frames, None)
    assert len(out) > 0
    assert (out["Categoria Real"] == "Otros").all()
    assert (out["Nombre Corregido"] == out["Producto"]).all()
