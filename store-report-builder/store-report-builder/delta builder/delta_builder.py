from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


class DeltaBuilderError(Exception):
    """Raised when the delta report builder cannot complete its workflow."""


@dataclass(frozen=True)
class ProductGroupConfig:
    """Named product group used for combo or thematic analysis."""

    name: str
    products: tuple[str, ...]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ProductGroupConfig":
        """Build a product group from a JSON-compatible dictionary."""
        name = str(data.get("name", "")).strip()
        raw_products = data.get("products", [])
        if not name:
            raise DeltaBuilderError("Cada grupo debe tener un nombre no vacio.")
        if not isinstance(raw_products, list) or not raw_products:
            raise DeltaBuilderError(f"El grupo '{name}' debe declarar una lista de productos.")
        products = tuple(str(product).strip() for product in raw_products if str(product).strip())
        if not products:
            raise DeltaBuilderError(f"El grupo '{name}' no contiene productos validos.")
        return ProductGroupConfig(name=name, products=products)


@dataclass(frozen=True)
class BuilderConfig:
    """Immutable runtime configuration for the standalone delta builder."""

    input_csv: Path
    output_html: Path
    output_json: Path
    output_discarded_csv: Path
    store_name: str
    report_title: str
    default_event_date: str
    default_window_days: int
    default_products: tuple[str, ...] = field(default_factory=tuple)
    product_groups: tuple[ProductGroupConfig, ...] = field(default_factory=tuple)

    @staticmethod
    def from_dict(data: dict[str, Any], base_dir: Path) -> "BuilderConfig":
        """Parse and validate JSON configuration for the builder."""
        input_csv = _resolve_path(base_dir, data.get("input_csv"), required=True)
        output_html = _resolve_path(base_dir, data.get("output_html", "impact_delta_report.html"))
        output_json = _resolve_path(base_dir, data.get("output_json", "impact_delta_report_data.json"))
        output_discarded_csv = _resolve_path(
            base_dir,
            data.get("output_discarded_csv", "impact_delta_report_discarded_rows.csv"),
        )

        default_window_days = int(data.get("default_window_days", 14))
        if default_window_days not in {7, 14, 30}:
            raise DeltaBuilderError("default_window_days debe ser 7, 14 o 30.")

        raw_groups = data.get("product_groups", [])
        if not isinstance(raw_groups, list):
            raise DeltaBuilderError("product_groups debe ser una lista.")

        default_products = tuple(
            str(product).strip() for product in data.get("default_products", []) if str(product).strip()
        )

        return BuilderConfig(
            input_csv=input_csv,
            output_html=output_html,
            output_json=output_json,
            output_discarded_csv=output_discarded_csv,
            store_name=str(data.get("store_name", "La Panetteria")).strip() or "La Panetteria",
            report_title=str(data.get("report_title", "Impact Delta Analyzer")).strip() or "Impact Delta Analyzer",
            default_event_date=str(data.get("default_event_date", "")).strip(),
            default_window_days=default_window_days,
            default_products=default_products,
            product_groups=tuple(ProductGroupConfig.from_dict(group) for group in raw_groups),
        )


@dataclass(frozen=True)
class DataQualityReport:
    """Summary of validation, coercion and temporal coverage."""

    initial_rows: int
    valid_rows: int
    dropped_rows: int
    dropped_pct: float
    invalid_dates: int
    invalid_numeric: dict[str, int]
    missing_days: int
    date_min: str
    date_max: str


@dataclass(frozen=True)
class LoadedDataset:
    """Validated dataset ready for payload generation."""

    lines: pd.DataFrame
    discarded_rows: pd.DataFrame
    quality: DataQualityReport


CATEGORY_NORMALIZATION: dict[str, str] = {
  "Panaderia": "Panaderia",
  "Panaderia ": "Panaderia",
  "Panadería": "Panaderia",
  "PAN": "Panaderia",
  "PAN TL": "Panaderia",
  "Reposteria": "Reposteria",
  "Repostería": "Reposteria",
  "Bebidas": "Bebidas",
  "Brunch": "Brunch",
  "Pinateria": "Pinateria",
  "Piñateria": "Pinateria",
  "-": "Otros",
}

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Fecha",
    "Codigo venta",
    "Cantidad",
    "Total",
    "Nombre Corregido",
    "Categoria Real",
)

COLUMN_ALIASES: dict[str, str] = {
  "fecha": "Fecha",
  "codigo venta": "Codigo venta",
  "cantidad": "Cantidad",
  "total": "Total",
  "nombre corregido": "Nombre Corregido",
  "categoria real": "Categoria Real",
  "sub categoria real": "Sub Categoria Real",
  "margin pct": "margin_pct",
  "margin_pct": "margin_pct",
}


def _resolve_path(base_dir: Path, raw_path: Any, required: bool = False) -> Path:
    """Resolve relative paths against a configuration directory."""
    value = str(raw_path or "").strip()
    if required and not value:
        raise DeltaBuilderError("Falta una ruta requerida en la configuracion.")
    path = Path(value) if value else Path()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _parse_margin(value: Any) -> float | None:
    """Convert margin values like '57.89%' into numeric percentages."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _canonicalize_column_name(value: str) -> str:
    """Normalize column headers to a stable comparable token."""
    text = str(value).replace("\ufeff", "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _safe_float(value: Any) -> float:
    """Convert scalar-like values to float for JSON serialization."""
    return float(value)


def _safe_string_list(value: Any) -> list[str]:
    """Convert iterable-like aggregates to a list of strings."""
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _pct_change(previous: float, current: float) -> float | None:
    """Return percentage change or None when the base is zero."""
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


class DeltaDatasetLoader:
    """Load, validate and normalize the cart-level CSV input."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path

    def load(self) -> LoadedDataset:
        """Return a normalized dataframe and data-quality metadata."""
        if not self.csv_path.exists():
            raise DeltaBuilderError(f"CSV no encontrado: {self.csv_path}")

        raw_frame = pd.read_csv(self.csv_path)
        normalized_columns = {
            column: COLUMN_ALIASES.get(
                _canonicalize_column_name(column),
                str(column).replace("ó", "o").replace("Ó", "O").strip(),
            )
            for column in raw_frame.columns
        }
        frame = raw_frame.rename(columns=normalized_columns).copy()
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing_columns:
            raise DeltaBuilderError(
                "El CSV no contiene columnas requeridas: " + ", ".join(sorted(missing_columns))
            )

        initial_rows = len(frame)
        frame["Fecha"] = pd.to_datetime(frame["Fecha"], errors="coerce")
        frame["Cantidad"] = pd.to_numeric(frame["Cantidad"], errors="coerce")
        frame["Total"] = pd.to_numeric(frame["Total"], errors="coerce")
        if "margin_pct" in frame.columns:
            frame["margin_pct"] = frame["margin_pct"].map(_parse_margin)
        else:
            frame["margin_pct"] = np.nan

        frame["Nombre Corregido"] = frame["Nombre Corregido"].astype(str).str.strip()
        frame["Categoria Real"] = frame["Categoria Real"].fillna("Otros").astype(str).str.strip()
        if "Sub Categoria Real" in frame.columns:
            frame["Sub Categoria Real"] = frame["Sub Categoria Real"].fillna("").astype(str).str.strip()
        else:
            frame["Sub Categoria Real"] = ""
        frame["Codigo venta"] = frame["Codigo venta"].astype(str).str.strip()

        discard_mask = pd.Series(False, index=frame.index)

        invalid_date_mask = frame["Fecha"].isna()
        discard_mask |= invalid_date_mask

        invalid_numeric_mask = frame["Cantidad"].isna() | frame["Total"].isna()
        discard_mask |= invalid_numeric_mask

        missing_product_mask = frame["Nombre Corregido"].eq("") | frame["Nombre Corregido"].eq("nan")
        discard_mask |= missing_product_mask

        missing_order_mask = frame["Codigo venta"].eq("") | frame["Codigo venta"].eq("nan")
        discard_mask |= missing_order_mask

        discarded_rows = frame.loc[discard_mask].copy()
        if not discarded_rows.empty:
            discarded_rows["discard_reason"] = "Descartada por fila invalida"

        valid_frame = frame.loc[~discard_mask].copy()
        if valid_frame.empty:
            raise DeltaBuilderError("No quedaron filas validas despues del saneamiento del CSV.")

        valid_frame["date"] = valid_frame["Fecha"].dt.normalize()
        valid_frame["date_str"] = valid_frame["date"].dt.strftime("%Y-%m-%d")
        valid_frame["product"] = valid_frame["Nombre Corregido"]
        valid_frame["category"] = valid_frame["Categoria Real"].map(CATEGORY_NORMALIZATION).fillna("Otros")
        valid_frame["subcategory"] = valid_frame["Sub Categoria Real"].replace({"": "Sin subcategoria"})
        valid_frame["order_id"] = valid_frame["Codigo venta"]
        valid_frame["quantity"] = valid_frame["Cantidad"].astype(float)
        valid_frame["revenue"] = valid_frame["Total"].astype(float)
        valid_frame["margin_pct"] = pd.to_numeric(valid_frame["margin_pct"], errors="coerce")

        date_min = valid_frame["date"].min()
        date_max = valid_frame["date"].max()
        full_range = pd.date_range(start=date_min, end=date_max, freq="D")
        observed_days = pd.DatetimeIndex(valid_frame["date"].unique())
        missing_days = int(len(full_range.difference(observed_days)))

        quality = DataQualityReport(
            initial_rows=initial_rows,
            valid_rows=len(valid_frame),
            dropped_rows=int(discard_mask.sum()),
            dropped_pct=round(float(discard_mask.sum()) / float(initial_rows) * 100.0, 2) if initial_rows else 0.0,
            invalid_dates=int(invalid_date_mask.sum()),
            invalid_numeric={
                "Cantidad": int(frame["Cantidad"].isna().sum()),
                "Total": int(frame["Total"].isna().sum()),
            },
            missing_days=missing_days,
            date_min=date_min.strftime("%Y-%m-%d"),
            date_max=date_max.strftime("%Y-%m-%d"),
        )

        return LoadedDataset(lines=valid_frame, discarded_rows=discarded_rows, quality=quality)


class DeltaPayloadBuilder:
    """Transform normalized rows into a browser-ready payload."""

    def __init__(self, config: BuilderConfig, dataset: LoadedDataset):
        self.config = config
        self.dataset = dataset

    def build(self) -> dict[str, Any]:
        """Create the JSON payload consumed by the interactive HTML report."""
        lines = self.dataset.lines.copy()

        order_frame = (
            lines.groupby(["date_str", "order_id"], as_index=False)
            .agg(
                order_revenue=("revenue", "sum"),
                order_units=("quantity", "sum"),
                products=("product", lambda values: sorted({str(value) for value in values})),
                categories=("category", lambda values: sorted({str(value) for value in values})),
            )
            .sort_values(["date_str", "order_id"])
        )

        product_catalog = sorted(lines["product"].dropna().unique().tolist())
        selected_products = tuple(product for product in self.config.default_products if product in product_catalog)

        if self.config.default_event_date:
            event_date = self.config.default_event_date
        else:
            event_date = _default_event_date(lines["date"])

        group_payload = [
            {
                "name": group.name,
                "products": list(group.products),
            }
            for group in self.config.product_groups
        ]

        top_products = (
          lines.groupby("product", as_index=False)
          .agg(revenue=("revenue", "sum"))
          .sort_values(by="revenue", ascending=False)
          .head(12)
        )

        payload = {
            "meta": {
                "storeName": self.config.store_name,
                "reportTitle": self.config.report_title,
                "dateMin": self.dataset.quality.date_min,
                "dateMax": self.dataset.quality.date_max,
                "lineCount": int(len(lines)),
                "orderCount": int(order_frame["order_id"].nunique()),
                "productCount": int(len(product_catalog)),
                "totalRevenue": round(float(lines["revenue"].sum()), 2),
                "totalUnits": round(float(lines["quantity"].sum()), 2),
                "quality": {
                    "initialRows": self.dataset.quality.initial_rows,
                    "validRows": self.dataset.quality.valid_rows,
                    "droppedRows": self.dataset.quality.dropped_rows,
                    "droppedPct": self.dataset.quality.dropped_pct,
                    "invalidDates": self.dataset.quality.invalid_dates,
                    "invalidNumeric": self.dataset.quality.invalid_numeric,
                    "missingDays": self.dataset.quality.missing_days,
                },
            },
            "defaults": {
                "eventDate": event_date,
                "windowDays": self.config.default_window_days,
                "selectedProducts": list(selected_products),
            },
            "catalog": product_catalog,
            "topProducts": top_products.to_dict(orient="records"),
            "productGroups": group_payload,
            "lines": _frame_to_line_records(lines),
            "orders": _frame_to_order_records(order_frame),
        }
        return payload


def _default_event_date(dates: pd.Series) -> str:
  """Choose a default event date using today - 30 days, clamped to data coverage."""
  normalized_dates = sorted(pd.to_datetime(dates).dropna().dt.normalize().unique())
  if not normalized_dates:
    raise DeltaBuilderError("No hay fechas validas para calcular una fecha de evento por defecto.")

  date_min = pd.Timestamp(normalized_dates[0])
  date_max = pd.Timestamp(normalized_dates[-1])
  candidate = (pd.Timestamp.today().normalize() - pd.Timedelta(days=30))

  min_allowed = date_min
  max_allowed = date_max - pd.Timedelta(days=29)
  if max_allowed < min_allowed:
    max_allowed = date_max

  clamped = min(max(candidate, min_allowed), max_allowed)
  return clamped.strftime("%Y-%m-%d")


def _frame_to_line_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert normalized cart rows to JSON-safe dictionaries."""
    payload: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        payload.append(
            {
                "date": row.date_str,
                "orderId": row.order_id,
                "product": row.product,
                "category": row.category,
                "subcategory": row.subcategory,
                "quantity": round(_safe_float(row.quantity), 2),
                "revenue": round(_safe_float(row.revenue), 2),
                "marginPct": round(_safe_float(row.margin_pct), 2) if not pd.isna(row.margin_pct) else None,
            }
        )
    return payload


def _frame_to_order_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert order aggregates to JSON-safe dictionaries."""
    payload: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        payload.append(
            {
                "date": row.date_str,
                "orderId": row.order_id,
                "revenue": round(_safe_float(row.order_revenue), 2),
                "units": round(_safe_float(row.order_units), 2),
                "products": _safe_string_list(row.products),
                "categories": _safe_string_list(row.categories),
            }
        )
    return payload


class DeltaHtmlRenderer:
    """Render the self-contained HTML report with embedded data and JS."""

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def render(self) -> str:
        """Return the full HTML document."""
        payload_json = json.dumps(self.payload, ensure_ascii=False).replace("</", "<\\/")
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{self.payload['meta']['reportTitle']}</title>
  <style>
    :root {{
      --bg: #050816;
      --panel: #0f172a;
      --panel-2: #111b33;
      --stroke: rgba(148, 163, 184, 0.18);
      --text: #edf2ff;
      --muted: #90a2c3;
      --accent: #f59e0b;
      --accent-2: #1fbf87;
      --accent-3: #3b82f6;
      --danger: #ef4444;
      --warning: #fbbf24;
      --card-shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
      --radius: 24px;
      --font-display: 'Segoe UI Semibold', 'Trebuchet MS', sans-serif;
      --font-body: 'Segoe UI', 'Helvetica Neue', sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--font-body);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(30, 64, 175, 0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(245, 158, 11, 0.12), transparent 28%),
        linear-gradient(180deg, #020617 0%, #091122 48%, #060b18 100%);
      min-height: 100vh;
    }}
    .shell {{
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 48px;
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      padding: 8px 0 28px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    }}
    .title-wrap h1 {{
      margin: 0;
      font-family: var(--font-display);
      font-size: clamp(2rem, 3vw, 2.9rem);
      letter-spacing: -0.03em;
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .title-badge {{
      color: var(--accent);
      font-size: 1.2rem;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 10px 0 0;
      max-width: 760px;
      line-height: 1.5;
    }}
    .meta-chip {{
      border: 1px solid rgba(245, 158, 11, 0.24);
      color: #ffd38d;
      background: rgba(245, 158, 11, 0.08);
      padding: 12px 16px;
      border-radius: 999px;
      font-size: 0.86rem;
      white-space: nowrap;
    }}
    .layout {{
      display: grid;
      gap: 18px;
      margin-top: 22px;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(9, 15, 30, 0.98));
      border: 1px solid var(--stroke);
      border-radius: var(--radius);
      box-shadow: var(--card-shadow);
    }}
    .controls {{
      padding: 22px;
      display: grid;
      grid-template-columns: 1.05fr 0.85fr 1.8fr;
      gap: 18px;
      align-items: start;
    }}
    .field label {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: #7f91b2;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 10px;
      font-weight: 700;
    }}
    .field input,
    .selector-button,
    .search-input {{
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(96, 114, 148, 0.35);
      background: rgba(7, 11, 22, 0.88);
      color: var(--text);
      padding: 14px 16px;
      font-size: 0.98rem;
      outline: none;
    }}
    .window-buttons {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}
    .window-button {{
      border: 1px solid rgba(96, 114, 148, 0.35);
      background: rgba(7, 11, 22, 0.88);
      color: var(--text);
      padding: 14px 0;
      border-radius: 16px;
      font-weight: 700;
      cursor: pointer;
      transition: 160ms ease;
    }}
    .window-button.active {{
      background: linear-gradient(135deg, #ffb11c, #f28a08);
      color: #091122;
      border-color: rgba(255, 177, 28, 0.85);
      box-shadow: 0 12px 24px rgba(242, 138, 8, 0.22);
    }}
    .selector {{ position: relative; }}
    .selector-button {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }}
    .selector-panel {{
      position: absolute;
      inset: calc(100% + 10px) 0 auto 0;
      z-index: 30;
      padding: 16px;
      display: none;
      background: linear-gradient(180deg, rgba(14, 21, 38, 0.98), rgba(9, 15, 30, 0.98));
      border: 1px solid rgba(96, 114, 148, 0.35);
      border-radius: 18px;
      box-shadow: var(--card-shadow);
    }}
    .selector-panel.open {{ display: block; }}
    .selector-actions,
    .quick-groups {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .selector-link,
    .group-chip {{
      border: none;
      background: rgba(30, 41, 59, 0.95);
      color: #e2e8f0;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.78rem;
      cursor: pointer;
    }}
    .group-chip {{
      border: 1px solid rgba(245, 158, 11, 0.18);
      color: #ffd38d;
      background: rgba(245, 158, 11, 0.08);
    }}
    .product-list {{
      max-height: 300px;
      overflow: auto;
      margin-top: 12px;
      padding-right: 6px;
      display: grid;
      gap: 6px;
    }}
    .product-option {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(9, 13, 24, 0.75);
      color: var(--muted);
    }}
    .product-option.active {{
      color: var(--text);
      background: rgba(30, 64, 175, 0.12);
      border: 1px solid rgba(59, 130, 246, 0.24);
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }}
    .kpi-card {{
      padding: 22px;
      position: relative;
      overflow: hidden;
    }}
    .kpi-card::after {{
      content: '';
      position: absolute;
      inset: auto -40px -40px auto;
      width: 120px;
      height: 120px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(59, 130, 246, 0.14), transparent 70%);
    }}
    .kpi-card:nth-child(2)::after {{ background: radial-gradient(circle, rgba(31, 191, 135, 0.14), transparent 70%); }}
    .kpi-card:nth-child(3)::after {{ background: radial-gradient(circle, rgba(245, 158, 11, 0.14), transparent 70%); }}
    .kpi-card:nth-child(4)::after {{ background: radial-gradient(circle, rgba(239, 68, 68, 0.12), transparent 70%); }}
    .kpi-label {{
      color: #7f91b2;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      font-weight: 700;
    }}
    .kpi-value {{
      margin-top: 14px;
      font-family: var(--font-display);
      font-size: clamp(1.9rem, 2vw, 2.6rem);
      letter-spacing: -0.04em;
    }}
    .delta-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    .delta-positive {{ background: rgba(31, 191, 135, 0.16); color: #61e3b7; }}
    .delta-negative {{ background: rgba(239, 68, 68, 0.16); color: #fda4af; }}
    .delta-neutral {{ background: rgba(148, 163, 184, 0.16); color: #cbd5e1; }}
    .chart-panel,
    .table-panel,
    .summary-panel {{
      padding: 22px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .section-title {{
      margin: 0;
      color: var(--text);
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-weight: 800;
    }}
    .section-note {{
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .chart-svg {{
      width: 100%;
      height: 320px;
      display: block;
    }}
    .chart-stage {{
      position: relative;
    }}
    .chart-tooltip {{
      position: absolute;
      min-width: 180px;
      max-width: 220px;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid rgba(96, 114, 148, 0.32);
      background: rgba(5, 8, 22, 0.96);
      box-shadow: 0 18px 36px rgba(0, 0, 0, 0.34);
      color: var(--text);
      pointer-events: none;
      opacity: 0;
      transform: translateY(8px);
      transition: opacity 120ms ease, transform 120ms ease;
      z-index: 8;
    }}
    .chart-tooltip.visible {{
      opacity: 1;
      transform: translateY(0);
    }}
    .chart-tooltip-date {{
      color: #f8fafc;
      font-size: 0.84rem;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .chart-tooltip-row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      color: var(--muted);
      font-size: 0.78rem;
      margin-top: 4px;
    }}
    .chart-tooltip-row strong {{
      color: var(--text);
      font-weight: 700;
    }}
    .comparison-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 18px;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }}
    .summary-card {{
      padding: 18px;
      background: rgba(7, 11, 22, 0.66);
      border-radius: 18px;
      border: 1px solid rgba(96, 114, 148, 0.2);
    }}
    .summary-card strong {{ display: block; font-size: 1.05rem; margin-bottom: 6px; }}
    .summary-card span {{ color: var(--muted); font-size: 0.88rem; line-height: 1.45; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      font-size: 0.9rem;
      vertical-align: middle;
    }}
    th {{ color: #90a2c3; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.12em; }}
    td {{ color: #e2e8f0; }}
    .text-muted {{ color: var(--muted); }}
    .status-pill {{
      display: inline-flex;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 700;
    }}
    .status-new {{ background: rgba(31, 191, 135, 0.16); color: #61e3b7; }}
    .status-dropped {{ background: rgba(239, 68, 68, 0.16); color: #fda4af; }}
    .status-stable {{ background: rgba(148, 163, 184, 0.16); color: #cbd5e1; }}
    .conclusion {{
      display: grid;
      grid-template-columns: 78px 1fr;
      gap: 18px;
      align-items: start;
    }}
    .conclusion-icon {{
      width: 78px;
      height: 78px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: rgba(31, 191, 135, 0.14);
      border: 1px solid rgba(31, 191, 135, 0.24);
      color: #61e3b7;
      font-size: 2rem;
    }}
    .conclusion h3 {{ margin: 4px 0 10px; font-size: 1.35rem; }}
    .conclusion p {{ margin: 0; color: #d7def0; line-height: 1.7; }}
    .warning-strip {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(251, 191, 36, 0.28);
      background: rgba(251, 191, 36, 0.08);
      color: #fde68a;
      font-size: 0.88rem;
      display: none;
    }}
    .warning-strip.visible {{ display: block; }}
    .footer-note {{
      color: #7f91b2;
      font-size: 0.8rem;
      margin-top: 18px;
      text-align: right;
    }}
    @media (max-width: 1180px) {{
      .controls, .kpi-grid, .comparison-grid, .mini-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 860px) {{
      .shell {{ width: min(100vw - 20px, 100%); }}
      .hero {{ flex-direction: column; }}
      .controls, .kpi-grid, .comparison-grid, .mini-grid {{ grid-template-columns: 1fr; }}
      .conclusion {{ grid-template-columns: 1fr; }}
      .conclusion-icon {{ width: 60px; height: 60px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="title-wrap">
        <h1><span class="title-badge">↗</span> <span id="hero-title"></span> <span class="text-muted" style="font-size:0.48em; font-weight:500;">v1</span></h1>
        <p class="subtitle" id="hero-subtitle"></p>
      </div>
      <div class="meta-chip" id="meta-chip"></div>
    </section>

    <section class="panel controls">
      <div class="field">
        <label>Fecha del evento</label>
        <input id="event-date" type="date" />
      </div>
      <div class="field">
        <label>Ventana de analisis</label>
        <div class="window-buttons">
          <button class="window-button" data-window="7">7d</button>
          <button class="window-button" data-window="14">14d</button>
          <button class="window-button" data-window="30">30d</button>
        </div>
      </div>
      <div class="field selector">
        <label>Seleccion de productos</label>
        <button id="selector-button" class="selector-button" type="button">
          <span id="selector-label"></span>
          <span id="selector-arrow">▾</span>
        </button>
        <div id="selector-panel" class="selector-panel">
          <input id="product-search" class="search-input" type="text" placeholder="Buscar producto..." />
          <div id="quick-groups" class="quick-groups"></div>
          <div class="product-list" id="product-list"></div>
          <div class="selector-actions">
            <button id="clear-selection" class="selector-link" type="button">Limpiar seleccion</button>
            <button id="select-top-products" class="selector-link" type="button">Top productos</button>
            <button id="close-selector" class="selector-link" type="button">Cerrar</button>
          </div>
        </div>
      </div>
    </section>

    <section class="kpi-grid" id="kpi-grid"></section>

    <section class="panel chart-panel">
      <div class="section-head">
        <div>
          <h2 class="section-title">Tendencia diaria</h2>
          <div class="section-note" id="timeline-note"></div>
        </div>
        <div class="section-note" id="window-scope-note"></div>
      </div>
      <div id="timeline-chart-stage" class="chart-stage">
        <svg id="timeline-chart" class="chart-svg" viewBox="0 0 1080 320" preserveAspectRatio="none"></svg>
        <div id="timeline-tooltip" class="chart-tooltip"></div>
      </div>
    </section>

    <section class="comparison-grid">
      <section class="panel chart-panel">
        <div class="section-head">
          <h2 class="section-title">Comparacion revenue</h2>
          <div class="section-note">Seleccion vs ventana previa</div>
        </div>
        <svg id="revenue-bars" class="chart-svg" viewBox="0 0 600 320" preserveAspectRatio="none"></svg>
      </section>
      <section class="panel chart-panel">
        <div class="section-head">
          <h2 class="section-title">Comparacion unidades</h2>
          <div class="section-note">Volumen fisico en ventana</div>
        </div>
        <svg id="units-bars" class="chart-svg" viewBox="0 0 600 320" preserveAspectRatio="none"></svg>
      </section>
    </section>

    <section class="panel summary-panel">
      <div class="section-head">
        <h2 class="section-title">Lectura ejecutiva</h2>
        <div class="section-note">Drivers del cambio observado</div>
      </div>
      <div class="mini-grid" id="mini-grid"></div>
    </section>

    <section class="panel table-panel">
      <div class="section-head">
        <div>
          <h2 class="section-title">Delta por producto</h2>
          <div class="section-note">Productos nuevos, caidos y aceleradores dentro del alcance seleccionado.</div>
        </div>
      </div>
      <div style="overflow:auto;">
        <table>
          <thead>
            <tr>
              <th>Producto</th>
              <th>Revenue Pre</th>
              <th>Revenue Pos</th>
              <th>Delta</th>
              <th>Unidades</th>
              <th>Margen</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody id="product-table-body"></tbody>
        </table>
      </div>
    </section>

    <section class="comparison-grid">
      <section class="panel table-panel">
        <div class="section-head">
          <h2 class="section-title">Cambio en mix por categoria</h2>
          <div class="section-note">Participacion del revenue en cada ventana</div>
        </div>
        <div style="overflow:auto;">
          <table>
            <thead>
              <tr>
                <th>Categoria</th>
                <th>Revenue Pre</th>
                <th>Revenue Pos</th>
                <th>Mix Pre</th>
                <th>Mix Pos</th>
                <th>Delta Mix</th>
              </tr>
            </thead>
            <tbody id="category-table-body"></tbody>
          </table>
        </div>
      </section>
      <section class="panel table-panel">
        <div class="section-head">
          <h2 class="section-title">Grupos y combos seguidos</h2>
          <div class="section-note">Comparacion automatica para grupos configurados</div>
        </div>
        <div style="overflow:auto;">
          <table>
            <thead>
              <tr>
                <th>Grupo</th>
                <th>Productos</th>
                <th>Revenue Pos</th>
                <th>Ordenes Pos</th>
                <th>Ticket Prom Pos</th>
                <th>Delta Revenue</th>
              </tr>
            </thead>
            <tbody id="group-table-body"></tbody>
          </table>
        </div>
      </section>
    </section>

    <section class="panel summary-panel">
      <div class="conclusion">
        <div class="conclusion-icon" id="conclusion-icon">↗</div>
        <div>
          <h3>Conclusion del analisis</h3>
          <p id="conclusion-text"></p>
          <div id="warning-strip" class="warning-strip"></div>
        </div>
      </div>
      <div class="footer-note" id="footer-note"></div>
    </section>
  </div>

  <script>
    const PAYLOAD = {payload_json};

    const state = {{
      eventDate: PAYLOAD.defaults.eventDate,
      windowDays: PAYLOAD.defaults.windowDays,
      selectedProducts: new Set(PAYLOAD.defaults.selectedProducts || []),
      search: '',
      selectorOpen: false,
    }};

    const refs = {{
      heroTitle: document.getElementById('hero-title'),
      heroSubtitle: document.getElementById('hero-subtitle'),
      metaChip: document.getElementById('meta-chip'),
      eventDate: document.getElementById('event-date'),
      selectorButton: document.getElementById('selector-button'),
      selectorLabel: document.getElementById('selector-label'),
      selectorArrow: document.getElementById('selector-arrow'),
      selectorPanel: document.getElementById('selector-panel'),
      productSearch: document.getElementById('product-search'),
      productList: document.getElementById('product-list'),
      quickGroups: document.getElementById('quick-groups'),
      clearSelection: document.getElementById('clear-selection'),
      selectTopProducts: document.getElementById('select-top-products'),
      closeSelector: document.getElementById('close-selector'),
      kpiGrid: document.getElementById('kpi-grid'),
      timelineChart: document.getElementById('timeline-chart'),
      timelineChartStage: document.getElementById('timeline-chart-stage'),
      timelineTooltip: document.getElementById('timeline-tooltip'),
      revenueBars: document.getElementById('revenue-bars'),
      unitsBars: document.getElementById('units-bars'),
      miniGrid: document.getElementById('mini-grid'),
      productTableBody: document.getElementById('product-table-body'),
      categoryTableBody: document.getElementById('category-table-body'),
      groupTableBody: document.getElementById('group-table-body'),
      conclusionText: document.getElementById('conclusion-text'),
      conclusionIcon: document.getElementById('conclusion-icon'),
      warningStrip: document.getElementById('warning-strip'),
      footerNote: document.getElementById('footer-note'),
      timelineNote: document.getElementById('timeline-note'),
      windowScopeNote: document.getElementById('window-scope-note'),
    }};

    const windowButtons = Array.from(document.querySelectorAll('.window-button'));

    function parseDate(dateText) {{
      return new Date(`${{dateText}}T00:00:00`);
    }}

    function formatDate(dateText) {{
      return new Intl.DateTimeFormat('es-CO', {{ day: '2-digit', month: '2-digit', year: 'numeric' }}).format(parseDate(dateText));
    }}

    function formatShortDate(dateText) {{
      return new Intl.DateTimeFormat('es-CO', {{ day: '2-digit', month: '2-digit' }}).format(parseDate(dateText));
    }}

    function formatCurrency(value) {{
      return new Intl.NumberFormat('es-CO', {{ style: 'currency', currency: 'COP', maximumFractionDigits: 0 }}).format(value || 0);
    }}

    function formatNumber(value) {{
      return new Intl.NumberFormat('es-CO', {{ maximumFractionDigits: 0 }}).format(value || 0);
    }}

    function formatPct(value) {{
      if (value === null || Number.isNaN(value)) {{
        return 'n/a';
      }}
      const sign = value > 0 ? '+' : '';
      return `${{sign}}${{value.toFixed(1)}}%`;
    }}

    function escapeHtml(text) {{
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }}

    function dateToKey(dateObject) {{
      return dateObject.toISOString().slice(0, 10);
    }}

    function addDays(dateObject, days) {{
      const clone = new Date(dateObject);
      clone.setDate(clone.getDate() + days);
      return clone;
    }}

    function getTrendWindowDays(windowDays) {{
      if (windowDays <= 7) {{
        return 3;
      }}
      if (windowDays <= 14) {{
        return 5;
      }}
      return 7;
    }}

    function intersects(leftArray, selectedSet) {{
      if (selectedSet.size === 0) {{
        return true;
      }}
      return leftArray.some((value) => selectedSet.has(value));
    }}

    function deriveScope() {{
      const eventDate = parseDate(state.eventDate);
      const preStart = addDays(eventDate, -state.windowDays);
      const postEnd = addDays(eventDate, state.windowDays - 1);
      const selectedSet = state.selectedProducts;
      const trendWindowDays = getTrendWindowDays(state.windowDays);

      const scopedLines = PAYLOAD.lines.filter((line) => selectedSet.size === 0 || selectedSet.has(line.product));
      const scopedOrders = PAYLOAD.orders.filter((order) => intersects(order.products, selectedSet));
      const preDatasetRows = PAYLOAD.lines.filter((line) => line.date >= dateToKey(preStart) && line.date < state.eventDate);
      const postDatasetRows = PAYLOAD.lines.filter((line) => line.date >= state.eventDate && line.date <= dateToKey(postEnd));

      const preLineRows = scopedLines.filter((line) => line.date >= dateToKey(preStart) && line.date < state.eventDate);
      const postLineRows = scopedLines.filter((line) => line.date >= state.eventDate && line.date <= dateToKey(postEnd));
      const preOrders = scopedOrders.filter((order) => order.date >= dateToKey(preStart) && order.date < state.eventDate);
      const postOrders = scopedOrders.filter((order) => order.date >= state.eventDate && order.date <= dateToKey(postEnd));

      const lineMetrics = (rows) => {{
        const revenue = rows.reduce((accumulator, row) => accumulator + row.revenue, 0);
        const units = rows.reduce((accumulator, row) => accumulator + row.quantity, 0);
        const marginRows = rows.filter((row) => row.marginPct !== null);
        const weightedMarginRevenue = marginRows.reduce((accumulator, row) => accumulator + row.revenue, 0);
        const weightedMargin = weightedMarginRevenue > 0
          ? marginRows.reduce((accumulator, row) => accumulator + (row.revenue * row.marginPct), 0) / weightedMarginRevenue
          : null;
        return {{ revenue, units, weightedMargin, marginCoverageRevenue: weightedMarginRevenue }};
      }};

      const orderMetrics = (rows) => {{
        const revenue = rows.reduce((accumulator, row) => accumulator + row.revenue, 0);
        const units = rows.reduce((accumulator, row) => accumulator + row.units, 0);
        const orders = rows.length;
        return {{
          revenue,
          units,
          orders,
          avgTicket: orders > 0 ? revenue / orders : 0,
          avgItemsPerOrder: orders > 0 ? units / orders : 0,
        }};
      }};

      const preLine = lineMetrics(preLineRows);
      const postLine = lineMetrics(postLineRows);
      const preOrder = orderMetrics(preOrders);
      const postOrder = orderMetrics(postOrders);

      const timeline = [];
      for (let cursor = new Date(preStart); cursor <= postEnd; cursor = addDays(cursor, 1)) {{
        const dateKey = dateToKey(cursor);
        const dayLines = scopedLines.filter((line) => line.date === dateKey);
        const dayOrders = scopedOrders.filter((order) => order.date === dateKey);
        timeline.push({{
          date: dateKey,
          revenue: dayLines.reduce((accumulator, row) => accumulator + row.revenue, 0),
          units: dayLines.reduce((accumulator, row) => accumulator + row.quantity, 0),
          orders: dayOrders.length,
          isPost: dateKey >= state.eventDate,
        }});
      }}

      const movingAverageValues = computeMovingAverage(
        timeline.map((point) => point.revenue),
        trendWindowDays,
      );
      timeline.forEach((point, index) => {{
        point.movingAvg = movingAverageValues[index];
      }});

      const productNames = Array.from(new Set(scopedLines.map((line) => line.product))).sort((left, right) => left.localeCompare(right));
      const productRows = productNames.map((product) => {{
        const preRows = preLineRows.filter((line) => line.product === product);
        const postRows = postLineRows.filter((line) => line.product === product);
        const preRevenue = preRows.reduce((accumulator, row) => accumulator + row.revenue, 0);
        const postRevenue = postRows.reduce((accumulator, row) => accumulator + row.revenue, 0);
        const preUnits = preRows.reduce((accumulator, row) => accumulator + row.quantity, 0);
        const postUnits = postRows.reduce((accumulator, row) => accumulator + row.quantity, 0);
        const preMarginRows = preRows.filter((row) => row.marginPct !== null);
        const postMarginRows = postRows.filter((row) => row.marginPct !== null);
        const preMargin = preMarginRows.length > 0
          ? preMarginRows.reduce((accumulator, row) => accumulator + (row.marginPct * row.revenue), 0) / preMarginRows.reduce((accumulator, row) => accumulator + row.revenue, 0)
          : null;
        const postMargin = postMarginRows.length > 0
          ? postMarginRows.reduce((accumulator, row) => accumulator + (row.marginPct * row.revenue), 0) / postMarginRows.reduce((accumulator, row) => accumulator + row.revenue, 0)
          : null;
        let status = 'stable';
        if (preRevenue === 0 && postRevenue > 0) {{ status = 'new'; }}
        if (preRevenue > 0 && postRevenue === 0) {{ status = 'dropped'; }}
        return {{
          product,
          preRevenue,
          postRevenue,
          deltaRevenue: postRevenue - preRevenue,
          deltaPct: pctChange(preRevenue, postRevenue),
          preUnits,
          postUnits,
          preMargin,
          postMargin,
          marginDelta: preMargin === null || postMargin === null ? null : postMargin - preMargin,
          status,
        }};
      }}).filter((row) => row.preRevenue > 0 || row.postRevenue > 0)
        .sort((left, right) => Math.abs(right.deltaRevenue) - Math.abs(left.deltaRevenue));

      const categoryNames = Array.from(new Set(scopedLines.map((line) => line.category))).sort((left, right) => left.localeCompare(right));
      const totalPreRevenue = preLine.revenue || 1;
      const totalPostRevenue = postLine.revenue || 1;
      const categoryRows = categoryNames.map((category) => {{
        const preRevenue = preLineRows.filter((line) => line.category === category).reduce((accumulator, row) => accumulator + row.revenue, 0);
        const postRevenue = postLineRows.filter((line) => line.category === category).reduce((accumulator, row) => accumulator + row.revenue, 0);
        const mixPre = preRevenue / totalPreRevenue;
        const mixPost = postRevenue / totalPostRevenue;
        return {{
          category,
          preRevenue,
          postRevenue,
          mixPre,
          mixPost,
          deltaMix: (mixPost - mixPre) * 100,
        }};
      }}).filter((row) => row.preRevenue > 0 || row.postRevenue > 0)
        .sort((left, right) => right.postRevenue - left.postRevenue);

      const groupRows = PAYLOAD.productGroups.map((group) => {{
        const members = new Set(group.products);
        const groupLines = PAYLOAD.lines.filter((line) => members.has(line.product));
        const groupOrders = PAYLOAD.orders.filter((order) => order.products.some((product) => members.has(product)));
        const preGroupRevenue = groupLines.filter((line) => line.date >= dateToKey(preStart) && line.date < state.eventDate).reduce((accumulator, row) => accumulator + row.revenue, 0);
        const postGroupRevenue = groupLines.filter((line) => line.date >= state.eventDate && line.date <= dateToKey(postEnd)).reduce((accumulator, row) => accumulator + row.revenue, 0);
        const postGroupOrders = groupOrders.filter((order) => order.date >= state.eventDate && order.date <= dateToKey(postEnd));
        const postRevenueOrders = postGroupOrders.reduce((accumulator, order) => accumulator + order.revenue, 0);
        return {{
          name: group.name,
          productCount: group.products.length,
          products: group.products,
          postRevenue: postGroupRevenue,
          postOrders: postGroupOrders.length,
          postAvgTicket: postGroupOrders.length > 0 ? postRevenueOrders / postGroupOrders.length : 0,
          deltaRevenue: pctChange(preGroupRevenue, postGroupRevenue),
        }};
      }});

      const selectionLabel = selectedSet.size === 0 ? 'todo el portafolio' : `${{selectedSet.size}} producto(s) seleccionado(s)`;
      const missingPreDays = countMissingDays(preDatasetRows, preStart, addDays(eventDate, -1));
      const missingPostDays = countMissingDays(postDatasetRows, eventDate, postEnd);
      const activePreDays = countActiveDays(preLineRows);
      const activePostDays = countActiveDays(postLineRows);
      const trendDelta = describeTrendMomentum(timeline);

      return {{
        eventDate: state.eventDate,
        windowDays: state.windowDays,
        trendWindowDays,
        selectionLabel,
        preLine,
        postLine,
        preOrder,
        postOrder,
        deltas: {{
          revenue: pctChange(preLine.revenue, postLine.revenue),
          units: pctChange(preLine.units, postLine.units),
          orders: pctChange(preOrder.orders, postOrder.orders),
          ticket: pctChange(preOrder.avgTicket, postOrder.avgTicket),
        }},
        timeline,
        productRows,
        categoryRows,
        groupRows,
        warnings: buildWarnings(preLine, postLine, missingPreDays, missingPostDays, activePreDays, activePostDays),
        missingPreDays,
        missingPostDays,
        activePreDays,
        activePostDays,
        trendDelta,
      }};
    }}

    function pctChange(previous, current) {{
      if (!previous) {{
        return current > 0 ? null : 0;
      }}
      return ((current - previous) / previous) * 100;
    }}

    function countMissingDays(rows, startDate, endDate) {{
      const expected = [];
      for (let cursor = new Date(startDate); cursor <= endDate; cursor = addDays(cursor, 1)) {{
        expected.push(dateToKey(cursor));
      }}
      const observed = new Set(rows.map((row) => row.date));
      return expected.filter((dateKey) => !observed.has(dateKey)).length;
    }}

    function countActiveDays(rows) {{
      return new Set(rows.map((row) => row.date)).size;
    }}

    function computeMovingAverage(values, windowSize) {{
      return values.map((_, index) => {{
        const start = Math.max(0, index - windowSize + 1);
        const slice = values.slice(start, index + 1);
        if (slice.length === 0) {{
          return 0;
        }}
        return slice.reduce((accumulator, value) => accumulator + value, 0) / slice.length;
      }});
    }}

    function describeTrendMomentum(timeline) {{
      if (timeline.length < 2) {{
        return 0;
      }}
      const first = timeline[0].movingAvg || 0;
      const last = timeline[timeline.length - 1].movingAvg || 0;
      if (first === 0) {{
        return last > 0 ? null : 0;
      }}
      return ((last - first) / first) * 100;
    }}

    function buildWarnings(preLine, postLine, missingPreDays, missingPostDays, activePreDays, activePostDays) {{
      const messages = [];
      if (missingPreDays > 0 || missingPostDays > 0) {{
        messages.push(`Hay huecos de cobertura en la ventana: pre ${{missingPreDays}} dia(s), pos ${{missingPostDays}} dia(s).`);
      }}
      const marginCoverageRatioPre = preLine.revenue > 0 ? (preLine.marginCoverageRevenue / preLine.revenue) : 0;
      const marginCoverageRatioPost = postLine.revenue > 0 ? (postLine.marginCoverageRevenue / postLine.revenue) : 0;
      if ((preLine.revenue > 0 || postLine.revenue > 0) && (marginCoverageRatioPre < 0.5 || marginCoverageRatioPost < 0.5)) {{
        messages.push('El analisis de margen es parcial o inexistente para la seleccion actual.');
      }}
      if (preLine.revenue === 0 && postLine.revenue > 0) {{
        messages.push('No hay base de revenue en la ventana pre para esta seleccion; el crecimiento porcentual no es comparable.');
      }} else if (postLine.revenue === 0 && preLine.revenue > 0) {{
        messages.push('La seleccion no tuvo revenue en la ventana pos; revisa si hubo descontinuacion, quiebre o falta de adopcion.');
      }}
      if (activePreDays <= 2 && activePostDays <= 2 && (preLine.revenue > 0 || postLine.revenue > 0)) {{
        messages.push('La seleccion opera con actividad muy intermitente; prioriza lectura cualitativa sobre porcentajes exactos.');
      }}
      return messages;
    }}

    function renderProductSelector() {{
      const query = state.search.trim().toLowerCase();
      const products = PAYLOAD.catalog.filter((product) => product.toLowerCase().includes(query));
      refs.productList.innerHTML = products.map((product) => {{
        const active = state.selectedProducts.has(product);
        return `
          <button type="button" class="product-option ${{active ? 'active' : ''}}" data-product="${{escapeHtml(product)}}">
            <input type="checkbox" ${{active ? 'checked' : ''}} tabindex="-1" />
            <span>${{escapeHtml(product)}}</span>
          </button>
        `;
      }}).join('');

      refs.productList.querySelectorAll('[data-product]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const product = button.getAttribute('data-product');
          if (state.selectedProducts.has(product)) {{
            state.selectedProducts.delete(product);
          }} else {{
            state.selectedProducts.add(product);
          }}
          update();
          toggleSelector(true);
        }});
      }});

      refs.selectorLabel.textContent = state.selectedProducts.size === 0
        ? 'Todo el portafolio'
        : `${{state.selectedProducts.size}} seleccionados`;
    }}

    function renderQuickGroups() {{
      refs.quickGroups.innerHTML = PAYLOAD.productGroups.map((group) => `
        <button type="button" class="group-chip" data-group="${{escapeHtml(group.name)}}">${{escapeHtml(group.name)}}</button>
      `).join('');

      refs.quickGroups.querySelectorAll('[data-group]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const groupName = button.getAttribute('data-group');
          const group = PAYLOAD.productGroups.find((entry) => entry.name === groupName);
          if (!group) {{
            return;
          }}
          state.selectedProducts = new Set(group.products);
          update();
          toggleSelector(true);
        }});
      }});
    }}

    function toggleSelector(forceOpen) {{
      state.selectorOpen = typeof forceOpen === 'boolean' ? forceOpen : !state.selectorOpen;
      refs.selectorPanel.classList.toggle('open', state.selectorOpen);
      refs.selectorArrow.textContent = state.selectorOpen ? '▴' : '▾';
    }}

    function renderKpis(scope) {{
      const kpis = [
        {{ label: 'Revenue pos', value: formatCurrency(scope.postLine.revenue), delta: scope.deltas.revenue, accent: 'positive' }},
        {{ label: 'Unidades pos', value: `${{formatNumber(scope.postLine.units)}} u`, delta: scope.deltas.units, accent: 'positive' }},
        {{ label: 'Ordenes impactadas', value: formatNumber(scope.postOrder.orders), delta: scope.deltas.orders, accent: 'neutral' }},
        {{ label: 'Ticket promedio pos', value: formatCurrency(scope.postOrder.avgTicket), delta: scope.deltas.ticket, accent: 'warning' }},
      ];

      refs.kpiGrid.innerHTML = kpis.map((item) => {{
        const deltaClass = item.delta === null ? 'delta-neutral' : item.delta >= 0 ? 'delta-positive' : 'delta-negative';
        const deltaText = item.delta === null ? 'Base cero' : `${{item.delta >= 0 ? '↑' : '↓'}} ${{Math.abs(item.delta).toFixed(1)}}% vs pre`;
        return `
          <article class="panel kpi-card">
            <div class="kpi-label">${{escapeHtml(item.label)}}</div>
            <div class="kpi-value">${{escapeHtml(item.value)}}</div>
            <div class="delta-pill ${{deltaClass}}">${{deltaText}}</div>
          </article>
        `;
      }}).join('');
    }}

    function renderLineChart(scope) {{
      const svg = refs.timelineChart;
      const width = 1080;
      const height = 320;
      const padding = {{ top: 24, right: 18, bottom: 34, left: 62 }};
      const innerWidth = width - padding.left - padding.right;
      const innerHeight = height - padding.top - padding.bottom;
      const values = scope.timeline.flatMap((point) => [point.revenue, point.movingAvg || 0]);
      const maxValue = Math.max(...values, 1);
      const minValue = 0;
      const xStep = scope.timeline.length > 1 ? innerWidth / (scope.timeline.length - 1) : innerWidth;
      const xAt = (index) => padding.left + (index * xStep);
      const yAt = (value) => padding.top + innerHeight - (((value - minValue) / (maxValue - minValue || 1)) * innerHeight);
      const linePath = scope.timeline.map((point, index) => `${{index === 0 ? 'M' : 'L'}}${{xAt(index)}},${{yAt(point.revenue)}}`).join(' ');
      const movingAveragePath = scope.timeline.map((point, index) => `${{index === 0 ? 'M' : 'L'}}${{xAt(index)}},${{yAt(point.movingAvg || 0)}}`).join(' ');
      const eventIndex = scope.timeline.findIndex((point) => point.date === scope.eventDate);
      const eventX = eventIndex >= 0 ? xAt(eventIndex) : padding.left;
      const gridLines = 5;

      const yTicks = Array.from({{ length: gridLines }}, (_, index) => {{
        const value = (maxValue / (gridLines - 1)) * index;
        return {{ value, y: yAt(value) }};
      }}).reverse();

      svg.innerHTML = `
        <defs>
          <linearGradient id="timeline-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="rgba(59,130,246,0.22)" />
            <stop offset="100%" stop-color="rgba(59,130,246,0.02)" />
          </linearGradient>
        </defs>
        ${{yTicks.map((tick) => `<line x1="${{padding.left}}" y1="${{tick.y}}" x2="${{width - padding.right}}" y2="${{tick.y}}" stroke="rgba(148,163,184,0.12)" stroke-dasharray="4 6"></line><text x="10" y="${{tick.y + 4}}" fill="#7f91b2" font-size="11">${{formatNumber(tick.value)}}</text>`).join('')}}
        <path d="${{linePath}} L${{width - padding.right}},${{height - padding.bottom}} L${{padding.left}},${{height - padding.bottom}} Z" fill="url(#timeline-fill)"></path>
        <path d="${{linePath}}" fill="none" stroke="#3b82f6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
        <path d="${{movingAveragePath}}" fill="none" stroke="#f59e0b" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"></path>
        <line x1="${{eventX}}" y1="${{padding.top}}" x2="${{eventX}}" y2="${{height - padding.bottom}}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="8 8"></line>
        <text x="${{eventX + 10}}" y="${{padding.top + 16}}" fill="#fbbf24" font-size="11" font-weight="700">EVENTO</text>
        ${{scope.timeline.map((point, index) => `<circle cx="${{xAt(index)}}" cy="${{yAt(point.revenue)}}" r="4.3" fill="${{point.isPost ? '#1fbf87' : '#3b82f6'}}" stroke="#050816" stroke-width="2"></circle>`).join('')}}
        ${{scope.timeline.map((point, index) => `<circle class="timeline-hit" data-index="${{index}}" cx="${{xAt(index)}}" cy="${{yAt(point.revenue)}}" r="14" fill="transparent" style="cursor:pointer;"></circle>`).join('')}}
        ${{scope.timeline.map((point, index) => `<text x="${{xAt(index)}}" y="${{height - 10}}" fill="#7f91b2" font-size="11" text-anchor="middle">${{formatShortDate(point.date)}}</text>`).join('')}}
      `;

      refs.timelineTooltip.classList.remove('visible');
      refs.timelineTooltip.innerHTML = '';

      svg.querySelectorAll('.timeline-hit').forEach((node) => {{
        node.addEventListener('mouseenter', (event) => {{
          const index = Number(node.getAttribute('data-index'));
          showTimelineTooltip(event, scope.timeline[index]);
        }});
        node.addEventListener('mousemove', (event) => {{
          const index = Number(node.getAttribute('data-index'));
          showTimelineTooltip(event, scope.timeline[index]);
        }});
        node.addEventListener('mouseleave', () => {{
          hideTimelineTooltip();
        }});
      }});
    }}

    function showTimelineTooltip(event, point) {{
      const tooltip = refs.timelineTooltip;
      const stageRect = refs.timelineChartStage.getBoundingClientRect();

      tooltip.innerHTML = `
        <div class="chart-tooltip-date">${{formatDate(point.date)}} · ${{point.isPost ? 'Ventana pos' : 'Ventana pre'}}</div>
        <div class="chart-tooltip-row"><span>Revenue</span><strong>${{formatCurrency(point.revenue)}}</strong></div>
        <div class="chart-tooltip-row"><span>Media movil</span><strong>${{formatCurrency(point.movingAvg || 0)}}</strong></div>
        <div class="chart-tooltip-row"><span>Unidades</span><strong>${{formatNumber(point.units)}}</strong></div>
        <div class="chart-tooltip-row"><span>Ordenes</span><strong>${{formatNumber(point.orders)}}</strong></div>
      `;
      tooltip.classList.add('visible');

      const offsetX = event.clientX - stageRect.left + 18;
      const offsetY = event.clientY - stageRect.top - 18;
      const maxLeft = Math.max(12, stageRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, stageRect.height - tooltip.offsetHeight - 12);
      const left = Math.min(Math.max(12, offsetX), maxLeft);
      const top = Math.min(Math.max(12, offsetY - tooltip.offsetHeight), maxTop);

      tooltip.style.left = `${{left}}px`;
      tooltip.style.top = `${{top}}px`;
    }}

    function hideTimelineTooltip() {{
      refs.timelineTooltip.classList.remove('visible');
    }}

    function renderBarChart(svgElement, preValue, postValue, labels) {{
      const width = 600;
      const height = 320;
      const padding = {{ top: 36, right: 48, bottom: 40, left: 58 }};
      const innerHeight = height - padding.top - padding.bottom;
      const maxValue = Math.max(preValue, postValue, 1);
      const barWidth = 86;
      const baseline = height - padding.bottom;
      const yAt = (value) => baseline - ((value / maxValue) * innerHeight);
      const preX = 190;
      const postX = 324;
      const preHeight = baseline - yAt(preValue);
      const postHeight = baseline - yAt(postValue);
      svgElement.innerHTML = `
        <line x1="${{padding.left}}" y1="${{baseline}}" x2="${{width - padding.right}}" y2="${{baseline}}" stroke="rgba(148,163,184,0.16)"></line>
        <rect x="${{preX}}" y="${{yAt(preValue)}}" width="${{barWidth}}" height="${{preHeight}}" rx="18" fill="#334155"></rect>
        <rect x="${{postX}}" y="${{yAt(postValue)}}" width="${{barWidth}}" height="${{postHeight}}" rx="18" fill="#1fbf87"></rect>
        <text x="${{preX + (barWidth / 2)}}" y="${{yAt(preValue) - 12}}" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="700">${{labels.format(preValue)}}</text>
        <text x="${{postX + (barWidth / 2)}}" y="${{yAt(postValue) - 12}}" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="700">${{labels.format(postValue)}}</text>
        <text x="${{preX + (barWidth / 2)}}" y="${{baseline + 22}}" fill="#7f91b2" font-size="12" text-anchor="middle">Pre</text>
        <text x="${{postX + (barWidth / 2)}}" y="${{baseline + 22}}" fill="#7f91b2" font-size="12" text-anchor="middle">Pos</text>
      `;
    }}

    function renderMiniCards(scope) {{
      const strongestProduct = scope.productRows[0];
      const revenueDriver = scope.deltas.units !== null && scope.deltas.ticket !== null && Math.abs(scope.deltas.units) > Math.abs(scope.deltas.ticket)
        ? 'El movimiento del revenue esta explicado principalmente por volumen.'
        : 'El cambio observado tiene mas relacion con ticket promedio y composicion de orden.';
      const churnMessage = scope.productRows.filter((row) => row.status === 'new').length > 0 || scope.productRows.filter((row) => row.status === 'dropped').length > 0
        ? `${{scope.productRows.filter((row) => row.status === 'new').length}} nuevo(s) y ${{scope.productRows.filter((row) => row.status === 'dropped').length}} caido(s) en la ventana.`
        : 'No hay churn relevante de productos en la seleccion.';
      const cards = [
        {{
          title: 'Driver principal',
          body: revenueDriver,
        }},
        {{
          title: 'Producto mas movil',
          body: strongestProduct ? `${{strongestProduct.product}} movio ${{formatCurrency(strongestProduct.deltaRevenue)}}.` : 'No hay suficiente actividad para destacar un SKU.',
        }},
        {{
          title: 'Churn de portafolio',
          body: churnMessage,
        }},
      ];
      refs.miniGrid.innerHTML = cards.map((card) => `
        <article class="summary-card">
          <strong>${{escapeHtml(card.title)}}</strong>
          <span>${{escapeHtml(card.body)}}</span>
        </article>
      `).join('');
    }}

    function renderProductTable(scope) {{
      refs.productTableBody.innerHTML = scope.productRows.slice(0, 18).map((row) => {{
        const statusLabel = row.status === 'new' ? 'Nuevo' : row.status === 'dropped' ? 'Caido' : 'Activo';
        const statusClass = row.status === 'new' ? 'status-new' : row.status === 'dropped' ? 'status-dropped' : 'status-stable';
        const marginLabel = row.postMargin === null ? 'n/a' : `${{row.postMargin.toFixed(1)}}%`;
        return `
          <tr>
            <td>${{escapeHtml(row.product)}}</td>
            <td>${{formatCurrency(row.preRevenue)}}</td>
            <td>${{formatCurrency(row.postRevenue)}}</td>
            <td class="${{row.deltaRevenue >= 0 ? 'delta-positive' : 'delta-negative'}}">${{formatPct(row.deltaPct)}}</td>
            <td>${{formatNumber(row.postUnits)}} <span class="text-muted">vs ${{formatNumber(row.preUnits)}}</span></td>
            <td>${{marginLabel}}</td>
            <td><span class="status-pill ${{statusClass}}">${{statusLabel}}</span></td>
          </tr>
        `;
      }}).join('');
    }}

    function renderCategoryTable(scope) {{
      refs.categoryTableBody.innerHTML = scope.categoryRows.map((row) => `
        <tr>
          <td>${{escapeHtml(row.category)}}</td>
          <td>${{formatCurrency(row.preRevenue)}}</td>
          <td>${{formatCurrency(row.postRevenue)}}</td>
          <td>${{(row.mixPre * 100).toFixed(1)}}%</td>
          <td>${{(row.mixPost * 100).toFixed(1)}}%</td>
          <td class="${{row.deltaMix >= 0 ? 'delta-positive' : 'delta-negative'}}">${{formatPct(row.deltaMix)}}</td>
        </tr>
      `).join('');
    }}

    function renderGroupTable(scope) {{
      if (scope.groupRows.length === 0) {{
        refs.groupTableBody.innerHTML = '<tr><td colspan="6" class="text-muted">No hay grupos configurados.</td></tr>';
        return;
      }}
      refs.groupTableBody.innerHTML = scope.groupRows.map((row) => `
        <tr>
          <td>${{escapeHtml(row.name)}}</td>
          <td>${{row.productCount}}</td>
          <td>${{formatCurrency(row.postRevenue)}}</td>
          <td>${{formatNumber(row.postOrders)}}</td>
          <td>${{formatCurrency(row.postAvgTicket)}}</td>
          <td class="${{row.deltaRevenue === null ? 'delta-neutral' : row.deltaRevenue >= 0 ? 'delta-positive' : 'delta-negative'}}">${{formatPct(row.deltaRevenue)}}</td>
        </tr>
      `).join('');
    }}

    function renderConclusion(scope) {{
      const direction = scope.deltas.revenue === null ? 'sin base comparable' : scope.deltas.revenue >= 0 ? 'positivo' : 'negativo';
      const icon = scope.deltas.revenue === null ? '•' : scope.deltas.revenue >= 0 ? '↗' : '↘';
      const driver = Math.abs(scope.deltas.units || 0) >= Math.abs(scope.deltas.ticket || 0)
        ? 'volumen'
        : 'ticket y mix de orden';
      const trendText = scope.trendDelta === null
        ? `la media movil de ${{scope.trendWindowDays}} dias no tiene base suficiente para comparar su arranque contra el cierre`
        : scope.trendDelta >= 0
          ? `la media movil de ${{scope.trendWindowDays}} dias cierra al alza (+${{scope.trendDelta.toFixed(1)}}%)`
          : `la media movil de ${{scope.trendWindowDays}} dias cierra a la baja (${{scope.trendDelta.toFixed(1)}}%)`;
      refs.conclusionIcon.textContent = icon;
      refs.conclusionIcon.style.background = scope.deltas.revenue !== null && scope.deltas.revenue < 0
        ? 'rgba(239, 68, 68, 0.14)'
        : 'rgba(31, 191, 135, 0.14)';
      refs.conclusionIcon.style.borderColor = scope.deltas.revenue !== null && scope.deltas.revenue < 0
        ? 'rgba(239, 68, 68, 0.24)'
        : 'rgba(31, 191, 135, 0.24)';
      refs.conclusionIcon.style.color = scope.deltas.revenue !== null && scope.deltas.revenue < 0
        ? '#fda4af'
        : '#61e3b7';

      const selectionText = state.selectedProducts.size === 0
        ? 'todo el portafolio'
        : `${{state.selectedProducts.size}} producto(s) seleccionado(s)`;
      const revenueDeltaText = scope.deltas.revenue === null
        ? 'sin porcentaje comparable'
        : `${{scope.deltas.revenue >= 0 ? '+' : ''}}${{scope.deltas.revenue.toFixed(1)}}%`;
      refs.conclusionText.innerHTML = `Tras evaluar el evento del <strong>${{formatDate(scope.eventDate)}}</strong> con una ventana de <strong>${{scope.windowDays}} dias</strong>, el desempeno de <strong>${{escapeHtml(selectionText)}}</strong> fue <strong>${{direction}}</strong>. El revenue paso de <strong>${{formatCurrency(scope.preLine.revenue)}}</strong> a <strong>${{formatCurrency(scope.postLine.revenue)}}</strong> (${{revenueDeltaText}}) y el ticket promedio de las ordenes impactadas paso de <strong>${{formatCurrency(scope.preOrder.avgTicket)}}</strong> a <strong>${{formatCurrency(scope.postOrder.avgTicket)}}</strong>. La lectura dominante es que el cambio viene por <strong>${{driver}}</strong>; ademas, <strong>${{trendText}}</strong>.`;

      if (scope.warnings.length > 0) {{
        refs.warningStrip.classList.add('visible');
        refs.warningStrip.textContent = scope.warnings.join(' ');
      }} else {{
        refs.warningStrip.classList.remove('visible');
        refs.warningStrip.textContent = '';
      }}
    }}

    function renderStaticMeta(scope) {{
      refs.heroTitle.textContent = PAYLOAD.meta.reportTitle;
      refs.heroSubtitle.textContent = `Comparador pre/pos sobre una fecha elegida para responder preguntas de ventas, ticket promedio, mix y adopcion de combos en ${{PAYLOAD.meta.storeName}}.`;
      refs.metaChip.textContent = `${{PAYLOAD.meta.storeName}} · ${{PAYLOAD.meta.productCount}} SKUs · ${{PAYLOAD.meta.lineCount}} lineas validas`;
      refs.timelineNote.textContent = `Serie diaria de revenue para ${{scope.selectionLabel}}, con media movil de ${{scope.trendWindowDays}} dias.`;
      refs.windowScopeNote.textContent = `${{formatDate(dateToKey(addDays(parseDate(scope.eventDate), -scope.windowDays)))}} → ${{formatDate(dateToKey(addDays(parseDate(scope.eventDate), scope.windowDays - 1)))}}`;
      refs.footerNote.textContent = `Cobertura base: ${{PAYLOAD.meta.dateMin}} a ${{PAYLOAD.meta.dateMax}} · Filas descartadas: ${{PAYLOAD.meta.quality.droppedRows}} (${{PAYLOAD.meta.quality.droppedPct}}%).`;
    }}

    function update() {{
      renderProductSelector();
      const scope = deriveScope();
      renderStaticMeta(scope);
      renderKpis(scope);
      renderLineChart(scope);
      renderBarChart(refs.revenueBars, scope.preLine.revenue, scope.postLine.revenue, {{ format: formatCurrency }});
      renderBarChart(refs.unitsBars, scope.preLine.units, scope.postLine.units, {{ format: (value) => formatNumber(value) }});
      renderMiniCards(scope);
      renderProductTable(scope);
      renderCategoryTable(scope);
      renderGroupTable(scope);
      renderConclusion(scope);
      refs.eventDate.value = state.eventDate;
      windowButtons.forEach((button) => button.classList.toggle('active', Number(button.dataset.window) === state.windowDays));
    }}

    refs.eventDate.addEventListener('change', (event) => {{
      state.eventDate = event.target.value;
      update();
    }});

    refs.selectorButton.addEventListener('click', () => toggleSelector());
    refs.productSearch.addEventListener('input', (event) => {{
      state.search = event.target.value;
      renderProductSelector();
    }});
    refs.clearSelection.addEventListener('click', () => {{
      state.selectedProducts = new Set();
      update();
      toggleSelector(true);
    }});
    refs.selectTopProducts.addEventListener('click', () => {{
      state.selectedProducts = new Set(PAYLOAD.topProducts.slice(0, 5).map((entry) => entry.product));
      update();
      toggleSelector(true);
    }});
    refs.closeSelector.addEventListener('click', () => toggleSelector(false));

    windowButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        state.windowDays = Number(button.dataset.window);
        update();
      }});
    }});

    document.addEventListener('click', (event) => {{
      if (!refs.selectorPanel.contains(event.target) && !refs.selectorButton.contains(event.target)) {{
        toggleSelector(false);
      }}
    }});

    renderQuickGroups();
    update();
  </script>
</body>
</html>
"""


class DeltaReportBuilder:
    """Orchestrate config loading, dataset normalization and artifact generation."""

    def __init__(self, config: BuilderConfig):
        self.config = config

    def run(self) -> tuple[Path, Path, Path | None]:
        """Build JSON and HTML artifacts and return their paths."""
        dataset = DeltaDatasetLoader(self.config.input_csv).load()
        payload = DeltaPayloadBuilder(self.config, dataset).build()
        html = DeltaHtmlRenderer(payload).render()

        self.config.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_json.parent.mkdir(parents=True, exist_ok=True)

        self.config.output_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.config.output_html.write_text(html, encoding="utf-8")

        discarded_path: Path | None = None
        if not dataset.discarded_rows.empty:
            self.config.output_discarded_csv.parent.mkdir(parents=True, exist_ok=True)
            dataset.discarded_rows.to_csv(self.config.output_discarded_csv, index=False)
            discarded_path = self.config.output_discarded_csv

        return self.config.output_html, self.config.output_json, discarded_path


def load_config(config_path: Path) -> BuilderConfig:
    """Load a JSON configuration file and validate its contents."""
    if not config_path.exists():
        raise DeltaBuilderError(f"Configuracion no encontrada: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)
    return BuilderConfig.from_dict(raw_data, config_path.parent)


def build_cli_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for standalone execution."""
    parser = argparse.ArgumentParser(
        description="Build a standalone impact delta report from the sales CSV.",
    )
    parser.add_argument(
        "--config",
        default="delta_report_config.json",
        help="JSON configuration file for the delta builder.",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    parser = build_cli_parser()
    arguments = parser.parse_args()

    raw_config_path = Path(arguments.config)
    if raw_config_path.is_absolute():
        config_path = raw_config_path
    else:
        config_path = (Path(__file__).resolve().parent / raw_config_path).resolve()

    config = load_config(config_path)
    output_html, output_json, discarded_path = DeltaReportBuilder(config).run()

    print(f"HTML generado: {output_html}")
    print(f"Datos intermedios: {output_json}")
    if discarded_path is not None:
        print(f"Filas descartadas: {discarded_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())