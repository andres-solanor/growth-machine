#!/usr/bin/env python3
"""
worker/run_job.py — entrypoint headless del motor de análisis para la app web.

Lee un "job spec" JSON, normaliza los exports POS del tenant, corre el motor
(reporte de ventas o delta) y escribe artefactos JSON puros. Sin código de
red: el shell que lo invoca (GitHub Actions / CLI local) se encarga del HTTP.

Uso:
    python worker/run_job.py --spec job_spec.json [--out-dir DIR]

Formato del spec (ver docs/SAAS-PLAN.md):
{
  "job_id": "uuid",
  "type": "report" | "delta",
  "input_files": ["ruta/export1.xls", "ruta/export2.csv"],   # exports POS crudos
  "column_mapping": {"date": "FECHA", "product": "Descripción", ...} | ausente,
      # clave canónica del wizard web -> encabezado real del archivo del tenant;
      # si está presente se renombra a columnas POS antes de normalizar
  "tenant_config": { ... campos de ReportConfig / alias "columns" ... },
  "product_map": [ {sistema, precio_post, fecha_desde, nombre,
                    categoria, subcategoria, margen_pct}, ... ] | null,
  "category_margins": {"Panadería": 35, ...} | null,
      # margen % estimado por categoría: fallback para productos sin
      # margen propio en el product_map (editor /productos, nivel 1)
  "delta_config": { ... campos de BuilderConfig (solo type=delta) ... }
}

Artefactos en --out-dir (default: junto al spec):
  payload.json      — payload del reporte (contrato con la app web)
  job_result.json   — resumen: estado, conteos, ruta de artefactos
  discarded.csv     — filas descartadas por normalización (si las hay)

NOTA: el motor vive hoy en reports/ (se importa vía sys.path). El traslado a
worker/engine/ ocurre con el scaffold del monorepo (Fase 1) para mantener
baratos los merges main→saas durante la Fase 0.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "reports"))
sys.path.insert(0, str(REPO_ROOT / "reports" / "delta_builder"))

import normalize_products as npd  # noqa: E402
from report_generator import ReportConfig, ReportGenerator, configure_logging  # noqa: E402
import delta_builder as deltab  # noqa: E402

FALLBACK_CATEGORY = "Otros"

# Mapa clave canónica (wizard web) -> nombre de columna que espera el motor.
# Espejo de src/lib/csv-detect.ts (CANONICAL_FIELDS).
CANONICAL_TO_POS = {
    "date": "Fecha",
    "time": "Hora",
    "order_id": "Código venta",
    "product": "Producto",
    "quantity": "Cantidad",
    "unit_price": "Individual",
    "total": "Total",
}


def _load_spec(spec_path: Path) -> dict:
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    for key in ("job_id", "type", "input_files"):
        if key not in spec:
            raise ValueError(f"job spec sin clave requerida: '{key}'")
    if spec["type"] not in ("report", "delta"):
        raise ValueError(f"type no soportado: {spec['type']!r}")
    if not spec["input_files"]:
        raise ValueError("input_files está vacío")
    return spec


def _apply_column_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Renombra las columnas del tenant a los nombres POS canónicos del motor
    y sintetiza las opcionales ausentes (Hora, Individual)."""
    rename = {
        src: CANONICAL_TO_POS[key]
        for key, src in mapping.items()
        if key in CANONICAL_TO_POS and src in df.columns
    }
    df = df.rename(columns=rename)

    # Hora e Individual son opcionales (se sintetizan); el resto es obligatorio.
    synthesizable = {"Hora", "Individual"}
    missing = [c for c in npd.POS_COLS if c not in df.columns and c not in synthesizable]
    if missing:
        raise ValueError(
            f"faltan columnas tras aplicar el mapeo: {missing} "
            f"(mapeo recibido: {sorted(mapping)})"
        )

    if "Hora" not in df.columns:
        df["Hora"] = "00:00"
    if "Individual" not in df.columns:
        total = pd.to_numeric(df["Total"], errors="coerce")
        qty = pd.to_numeric(df["Cantidad"], errors="coerce")
        df["Individual"] = (total / qty.replace(0, pd.NA)).fillna(total)

    return df[npd.POS_COLS]


def _read_input_frames(
    paths: list[str], base_dir: Path, column_mapping: dict | None = None
) -> list[pd.DataFrame]:
    frames = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"input no encontrado: {p}")
        if column_mapping:
            df = npd.read_raw_file(p)
            if df is None:
                raise ValueError(f"input ilegible: {p.name}")
            df = _apply_column_mapping(df, column_mapping)
        else:
            df = npd._read_file(p)
            if df is None:
                raise ValueError(f"input ilegible o sin columnas POS requeridas: {p.name}")
        frames.append(df)
    return frames


def _normalize(
    frames: list[pd.DataFrame],
    product_map_rows: list[dict] | None,
    category_margins: dict | None = None,
) -> pd.DataFrame:
    """Normaliza ventas; sin product_map aplica el fallback de onboarding:
    Nombre Corregido = Producto, Categoria Real = "Otros" (sin margen).
    `category_margins` rellena margin_pct por categoría donde el producto
    no tiene margen propio (nivel 1 del editor de productos)."""
    if product_map_rows:
        # Sin dtype=str: convertiría los None de JSON en el string "None";
        # prepare_product_map ya coerciona los campos numéricos/fecha.
        pm = pd.DataFrame(product_map_rows)
        sales = npd.normalize(frames, pm)
        # Productos nuevos que aún no están en el mapa quedan sin categoría:
        # caen a "Otros" en vez de romper el reporte.
        sales["Categoria Real"] = sales["Categoria Real"].fillna(FALLBACK_CATEGORY)
    else:
        sales = npd.consolidate(frames)
        sales["Nombre Corregido"] = sales["Producto"]
        sales["Categoria Real"] = FALLBACK_CATEGORY
        sales["Sub Categoria Real"] = None
        sales["margin_pct"] = None
        npd.add_time_features(sales)
        sales = npd.reorder_columns(sales)

    if category_margins:
        margins = pd.to_numeric(sales["margin_pct"], errors="coerce")
        estimated = sales["Categoria Real"].map(
            {k: float(v) for k, v in category_margins.items()}
        )
        sales["margin_pct"] = margins.fillna(estimated)

    return sales


def _write_normalized_csv(normalized: pd.DataFrame, out_dir: Path) -> Path:
    csv_path = out_dir / "normalized_sales.csv"
    out = normalized.copy()
    out["Fecha"] = out["Fecha"].dt.strftime("%Y-%m-%d")
    out.to_csv(csv_path, index=False)
    return csv_path


def _run_report(spec: dict, normalized_csv: Path, out_dir: Path) -> Path:
    config = ReportConfig.from_dict(spec.get("tenant_config") or {})
    gen = ReportGenerator(str(normalized_csv), config)
    payload_path = out_dir / "payload.json"
    gen.write_payload(str(payload_path))

    discarded = gen.processor.discarded_df
    if discarded is not None and not discarded.empty:
        discarded.to_csv(out_dir / "discarded.csv", index=False, encoding="utf-8-sig")
    return payload_path


def _run_delta(spec: dict, normalized_csv: Path, out_dir: Path) -> Path:
    tenant = spec.get("tenant_config") or {}
    raw = dict(spec.get("delta_config") or {})
    raw["input_csv"] = str(normalized_csv)
    raw.setdefault("store_name", tenant.get("store_name", "Negocio"))
    raw.setdefault("currency", tenant.get("currency", "COP"))
    raw["output_json"] = str(out_dir / "payload.json")
    raw["output_html"] = str(out_dir / "_unused.html")
    raw["output_discarded_csv"] = str(out_dir / "discarded.csv")

    config = deltab.BuilderConfig.from_dict(raw, out_dir)
    _, output_json, _ = deltab.DeltaReportBuilder(config).run(json_only=True)
    return output_json


def run_job(spec_path: Path, out_dir: Path | None = None) -> dict:
    spec = _load_spec(spec_path)
    out_dir = out_dir or spec_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = _read_input_frames(
        spec["input_files"], spec_path.parent, spec.get("column_mapping")
    )
    normalized = _normalize(frames, spec.get("product_map"), spec.get("category_margins"))

    # ReportConfig trae por defecto el category_normalization de La Panettería;
    # mapearía las categorías propias del tenant a NaN → "Otros". Si el tenant
    # no define el suyo, se inyecta el mapeo identidad con SUS categorías.
    tenant_config = dict(spec.get("tenant_config") or {})
    if "category_normalization" not in tenant_config:
        cats = normalized["Categoria Real"].dropna().unique()
        tenant_config["category_normalization"] = {str(c): str(c) for c in cats}
    spec["tenant_config"] = tenant_config

    with tempfile.TemporaryDirectory() as tmp:
        normalized_csv = _write_normalized_csv(normalized, Path(tmp))
        if spec["type"] == "report":
            payload_path = _run_report(spec, normalized_csv, out_dir)
        else:
            payload_path = _run_delta(spec, normalized_csv, out_dir)

    result = {
        "job_id": spec["job_id"],
        "type": spec["type"],
        "status": "succeeded",
        "input_rows": int(sum(len(f) for f in frames)),
        "normalized_rows": int(len(normalized)),
        "payload_path": str(payload_path),
        "discarded_path": str(out_dir / "discarded.csv") if (out_dir / "discarded.csv").exists() else None,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless analysis job runner")
    parser.add_argument("--spec", required=True, help="Ruta al job spec JSON")
    parser.add_argument("--out-dir", default=None, help="Directorio de artefactos (default: junto al spec)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    configure_logging(args.verbose)
    spec_path = Path(args.spec).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else spec_path.parent

    try:
        result = run_job(spec_path, out_dir)
    except Exception as exc:  # el shell decide reintentos; aquí solo reportamos
        result = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=5),
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "job_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[worker] FAILED: {result['error']}", file=sys.stderr)
        return 1

    with open(out_dir / "job_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # ASCII puro: consolas Windows cp1252 revientan con caracteres como '→'
    print(f"[worker] OK: {result['normalized_rows']:,} filas -> {result['payload_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
