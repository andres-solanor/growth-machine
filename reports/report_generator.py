"""
╔══════════════════════════════════════════════════════════════════════╗
║  STORE SALES REPORT GENERATOR                                       ║
║  Rappi · Analytics · Restaurant Metrics                             ║
║                                                                      ║
║  Genera un reporte HTML interactivo a partir de datos de carritos    ║
║  de ventas. Diseñado para ser extensible y reutilizable.            ║
╚══════════════════════════════════════════════════════════════════════╝

USO (desde la raíz del repo o desde este directorio):
    python report_generator.py --input input_data/ventas.csv --output report.html

    O como módulo:
        from report_generator import ReportGenerator
        gen = ReportGenerator("ventas.csv")
        gen.run("report.html")

EXTENSIBILIDAD:
    - Para agregar un nuevo análisis: crear función en AnalysisModules
      que retorne un dict, registrarla en run_all_analyses()
    - Para agregar un nuevo insight: crear función decorada con
      @insight_rule en InsightEngine
    - Para agregar un nuevo chart: agregar sección en ReportRenderer
    - Para soportar nuevos datos: crear nuevo módulo de análisis
      (ver EXTENSION_POINTS al final del archivo)
"""

import pandas as pd
import numpy as np
from itertools import combinations
from collections import Counter
from dataclasses import dataclass, field, asdict, fields as dataclass_fields, is_dataclass
from typing import Optional, Callable, Any
import json
import math
import argparse
import sys
from pathlib import Path
import logging
from calendar import monthrange
from datetime import datetime, timezone

# Directorio del proyecto (donde viven input_data/, report.html, etc.)
PROJECT_DIR = Path(__file__).resolve().parent


def resolve_project_path(path: str | Path) -> Path:
    """Resuelve rutas relativas contra PROJECT_DIR (no contra cwd)."""
    p = Path(path)
    return p if p.is_absolute() else (PROJECT_DIR / p).resolve()


# Versión del esquema del payload JSON (consumido por la app web).
# Incrementar ante cambios incompatibles de estructura.
PAYLOAD_SCHEMA_VERSION = 1


def to_jsonable(obj: Any) -> Any:
    """Convierte recursivamente estructuras de análisis a tipos JSON puros.

    DataFrames → list[dict] (orient="records"), escalares numpy → nativos,
    NaN/NaT/inf → None, Timestamps → ISO 8601, dataclasses → dict.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is pd.NaT:
        return None
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, (pd.Period, np.datetime64, np.timedelta64, pd.Timedelta)):
        return str(obj)
    if isinstance(obj, pd.DataFrame):
        return to_jsonable(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return to_jsonable(obj.tolist())
    if isinstance(obj, np.ndarray):
        return to_jsonable(obj.tolist())
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {
            (k if isinstance(k, str) else str(k)): to_jsonable(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    # Último recurso: representación textual (igual que el viejo default=str).
    return str(obj)


# ═══════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ReportConfig:
    """Configuración central del reporte. Modificar aquí para personalizar."""

    # ── Columnas esperadas del CSV ──
    col_date: str = "Fecha"
    col_time: str = "Hora"
    col_order_id: str = "Código venta"
    col_product_raw: str = "Producto"
    col_quantity: str = "Cantidad"
    col_unit_price: str = "Individual"
    col_total: str = "Total"
    col_product: str = "Nombre Corregido"
    col_category: str = "Categoria Real"
    col_subcategory: str = "Sub Categoria Real"
    col_margin_pct: str = "margin_pct"  # OPCIONAL: % de margen por producto
    col_month: str = "Month"
    col_weekday: str = "Week Day"
    col_hour: str = "Hour"

    # ── Normalización de categorías ──
    # Mapeo: nombre_raw → nombre_limpio
    category_normalization: dict = field(default_factory=lambda: {
        "Panadería": "Panadería",
        "Panaderia": "Panadería",
        "PAN": "Panadería",
        "PAN TL": "Panadería",
        "Reposteria": "Repostería",
        "Bebidas": "Bebidas",
        "Brunch": "Brunch",
        "Piñateria": "Piñatería",
        "TRUFAS X 5 UNIDADES": "Repostería",
        "-": "Otros",
    })

    # ── Orden canónico de días y meses ──
    day_order: list = field(default_factory=lambda: [
        "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"
    ])
    month_order: list = field(default_factory=lambda: [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ])

    # ── Parámetros de análisis ──
    pareto_threshold: float = 80.0          # % de revenue para corte Pareto
    margin_pareto_threshold: float = 80.0   # % de profit para corte Pareto de rentabilidad
    min_basket_size: int = 2                # mínimo items para market basket
    top_n_products: int = 20                # top N productos en charts
    top_n_pairs: int = 15                   # top N pares en market basket
    top_n_single_ticket_products: int = 15  # top N productos single por ticket promedio
    min_single_ticket_orders: int = 10      # órdenes mínimas para ranking single
    rolling_window: int = 7                 # ventana para media móvil
    trend_min_months: int = 2               # meses mínimos para calcular tendencia
    trend_min_base_revenue: float = 200000  # mínimo revenue base para incluir tendencia
    trend_min_base_orders: int = 10          # mínimo órdenes base para incluir tendencia
    anomaly_std_threshold: float = 2.0      # desviaciones estándar para anomalía

    # ── Ticket buckets (COP) ──
    ticket_bins: list = field(default_factory=lambda: [
        0, 5000, 10000, 15000, 20000, 30000, 50000, 200000
    ])
    ticket_labels: list = field(default_factory=lambda: [
        "<5K", "5-10K", "10-15K", "15-20K", "20-30K", "30-50K", "50K+"
    ])

    # ── Metadata del reporte ──
    store_name: str = "La Panettería · Suramérica"
    brand: str = "Analytiks Consulting"
    currency: str = "COP"
    cat_colors: dict[str, str] = field(default_factory=lambda: {
        "Bebidas": "#3b82f6",
        "Panadería": "#f59e0b",
        "Repostería": "#ef4444",
        "Brunch": "#10b981",
        "Piñatería": "#8b5cf6",
        "Otros": "#6b7280",
    })

    # Alias cortos aceptados en configs de tenant bajo la clave "columns".
    _COLUMN_ALIASES = {
        "date": "col_date",
        "time": "col_time",
        "order_id": "col_order_id",
        "product_raw": "col_product_raw",
        "quantity": "col_quantity",
        "unit_price": "col_unit_price",
        "total": "col_total",
        "product": "col_product",
        "category": "col_category",
        "subcategory": "col_subcategory",
        "margin_pct": "col_margin_pct",
        "month": "col_month",
        "weekday": "col_weekday",
        "hour": "col_hour",
    }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ReportConfig":
        """Crea una configuración desde un dict (e.g. JSON de tenant).

        Acepta cualquier campo del dataclass por nombre directo, más la clave
        "columns" con alias cortos (date, order_id, total, ...). Claves
        desconocidas generan warning y se ignoran — nunca rompen el reporte.
        """
        valid = {f.name for f in dataclass_fields(cls) if not f.name.startswith("_")}
        kwargs: dict[str, Any] = {}
        for key, value in (data or {}).items():
            if key == "columns" and isinstance(value, dict):
                for alias, col_name in value.items():
                    target = cls._COLUMN_ALIASES.get(alias)
                    if target is None:
                        logger.warning("Config: alias de columna desconocido '%s' ignorado", alias)
                    else:
                        kwargs[target] = col_name
            elif key in valid:
                kwargs[key] = value
            else:
                logger.warning("Config: campo desconocido '%s' ignorado", key)
        return cls(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
# 1.1 LOGGING
# ═══════════════════════════════════════════════════════════════════════

logger = logging.getLogger("report_generator")


def configure_logging(verbose: bool = False) -> None:
    """Configura logging estándar para observabilidad del pipeline."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


@dataclass
class DataQualityReport:
    """Resumen de calidad de datos tras validación y saneamiento."""

    initial_rows: int
    final_rows: int
    dropped_rows_missing_product: int
    invalid_dates: int
    invalid_numeric: dict[str, int]

    @property
    def dropped_total(self) -> int:
        return self.initial_rows - self.final_rows

    @property
    def dropped_pct(self) -> float:
        if self.initial_rows == 0:
            return 0.0
        return round(self.dropped_total / self.initial_rows * 100, 2)


class DataValidator:
    """Valida esquema y sanea columnas críticas antes del análisis."""

    def __init__(self, config: ReportConfig):
        self.c = config

    def required_columns(self) -> list[str]:
        """Retorna columnas mínimas requeridas para generar el reporte."""
        c = self.c
        return [
            c.col_date,
            c.col_order_id,
            c.col_product,
            c.col_quantity,
            c.col_unit_price,
            c.col_total,
            c.col_category,
            c.col_weekday,
            c.col_hour,
        ]

    def optional_columns(self) -> list[str]:
        """Retorna columnas opcionales para análisis adicionales."""
        c = self.c
        return [
            c.col_margin_pct,  # Margen por producto (para análisis de rentabilidad)
        ]

    def validate_schema(self, df: pd.DataFrame) -> None:
        """Lanza ValueError si faltan columnas obligatorias."""
        missing = [col for col in self.required_columns() if col not in df.columns]
        if missing:
            raise ValueError(
                "CSV inválido: faltan columnas requeridas: "
                + ", ".join(sorted(missing))
            )

    def sanitize(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, DataQualityReport]:
        """Convierte tipos críticos y elimina filas no utilizables."""
        self.validate_schema(df)
        c = self.c
        out = df.copy()
        initial_rows = len(out)

        # Fecha
        out[c.col_date] = pd.to_datetime(out[c.col_date], errors="coerce")
        invalid_dates = int(out[c.col_date].isna().sum())

        # Numéricos
        numeric_cols = [c.col_quantity, c.col_unit_price, c.col_total, c.col_hour]
        invalid_numeric: dict[str, int] = {}
        for col in numeric_cols:
            converted = pd.to_numeric(out[col], errors="coerce")
            invalid_numeric[col] = int(converted.isna().sum())
            out[col] = converted

        # Opcional: margin_pct (si existe en CSV)
        if c.col_margin_pct in out.columns:
            # Soporta formatos como "57.89%", "57,89%" y numéricos ya limpios.
            margin_raw = out[c.col_margin_pct]
            margin_clean = (
                margin_raw.astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
                .replace({"": np.nan, "nan": np.nan, "None": np.nan})
            )
            margin_converted = pd.to_numeric(margin_clean, errors="coerce")
            margin_missing = int(margin_clean.isna().sum())
            margin_invalid = int((margin_clean.notna() & margin_converted.isna()).sum())
            invalid_numeric[c.col_margin_pct] = margin_invalid
            out[c.col_margin_pct] = margin_converted
            if margin_invalid > 0:
                logger.warning(
                    f"{margin_invalid} valores inválidos en columna '{c.col_margin_pct}', "
                    f"serán tratados como NaN. Análisis de rentabilidad puede estar incompleto."
                )
            if margin_missing > 0:
                logger.info(
                    f"{margin_missing} filas sin margen en '{c.col_margin_pct}'. "
                    f"El análisis de rentabilidad usará solo filas con margen observado."
                )
        else:
            logger.info(f"Columna '{c.col_margin_pct}' no encontrada. Análisis de rentabilidad deshabilitado.")

        # ── Identificar filas a descartar con su motivo ──
        drop_subset_labels: dict[str, str] = {
            c.col_date:     "Fecha inválida",
            c.col_order_id: "Código de venta faltante",
            c.col_product:  "Producto faltante",
            c.col_quantity: "Cantidad inválida",
            c.col_total:    "Total inválido",
            c.col_hour:     "Hora inválida",
        }
        discard_mask = out[[*drop_subset_labels]].isna().any(axis=1)
        discarded_idx = out.index[discard_mask]

        discarded = df.loc[discarded_idx].copy()
        discarded["motivo_descarte"] = [
            "; ".join(
                label for col, label in drop_subset_labels.items() if pd.isna(out.at[idx, col])
            )
            for idx in discarded_idx
        ]
        discarded.insert(0, "fila_original", discarded_idx + 2)  # +2: header + 1-based

        before_drop = len(out)
        out = out.dropna(subset=[*drop_subset_labels])

        # Cast final para evitar problemas en visualizaciones y groupby
        out[c.col_hour] = out[c.col_hour].astype(int)

        dropped_rows_missing_product = int(before_drop - len(out))
        report = DataQualityReport(
            initial_rows=initial_rows,
            final_rows=len(out),
            dropped_rows_missing_product=dropped_rows_missing_product,
            invalid_dates=invalid_dates,
            invalid_numeric=invalid_numeric,
        )
        return out, discarded, report


# ═══════════════════════════════════════════════════════════════════════
# 2. DATA PROCESSOR
# ═══════════════════════════════════════════════════════════════════════

class DataProcessor:
    """Carga, limpia y normaliza los datos de carritos."""

    def __init__(self, filepath: str, config: ReportConfig):
        self.config = config
        if not Path(filepath).exists():
            raise FileNotFoundError(f"CSV no encontrado: {filepath}")
        self.raw_df = pd.read_csv(filepath)
        self.quality_report: Optional[DataQualityReport] = None
        self.discarded_df: pd.DataFrame = pd.DataFrame()
        self.df = self._process()

    def _process(self) -> pd.DataFrame:
        df = self.raw_df.copy()
        c = self.config
        validator = DataValidator(c)
        df, self.discarded_df, quality = validator.sanitize(df)
        self.quality_report = quality
        logger.info(
            "Data quality | rows=%s kept=%s dropped=%s (%.2f%%)",
            quality.initial_rows,
            quality.final_rows,
            quality.dropped_total,
            quality.dropped_pct,
        )

        # Normalize categories
        df["Categoria"] = df[c.col_category].map(c.category_normalization).fillna("Otros")

        # Computed columns
        iso = df[c.col_date].dt.isocalendar()
        df["year_week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
        df["year_month"] = df[c.col_date].dt.to_period("M").astype(str)

        return df

    def data_quality_metrics(self) -> dict[str, Any]:
        """Métricas de calidad visibles para el reporte HTML."""
        c = self.config
        df = self.df
        qr = self.quality_report

        if qr is None or df.empty:
            return {
                "initial_rows": qr.initial_rows if qr else 0,
                "valid_rows": qr.final_rows if qr else 0,
                "dropped_pct": qr.dropped_pct if qr else 0.0,
                "invalid_dates": qr.invalid_dates if qr else 0,
                "invalid_numeric": qr.invalid_numeric if qr else {},
                "missing_days": 0,
                "incomplete_weeks": 0,
                "partial_months": [],
                "coverage_note": "Sin datos válidos para evaluar cobertura temporal.",
                "risk_level": "high",
            }

        date_min = df[c.col_date].min().normalize()
        date_max = df[c.col_date].max().normalize()
        full_range_days = pd.date_range(start=date_min, end=date_max, freq="D")
        observed_days = pd.DatetimeIndex(df[c.col_date].dt.normalize().unique())
        missing_days = int(len(full_range_days.difference(observed_days)))

        week_day_counts = df.groupby("year_week")[c.col_date].apply(lambda s: s.dt.normalize().nunique())
        incomplete_weeks = int((week_day_counts < 7).sum())

        partial_months: list[dict[str, Any]] = []
        for month_str, group in df.groupby("year_month"):
            year_i, month_i = [int(v) for v in month_str.split("-")]
            month_days = monthrange(year_i, month_i)[1]
            observed = int(group[c.col_date].dt.day.nunique())
            if observed < month_days:
                partial_months.append({"month": month_str, "observed_days": observed, "month_days": month_days})

        dropped_pct = qr.dropped_pct
        if dropped_pct >= 10 or missing_days > 7:
            risk_level = "high"
        elif dropped_pct >= 3 or missing_days > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        coverage_note = (
            f"Cobertura del {len(observed_days)}/{len(full_range_days)} días entre "
            f"{date_min.strftime('%Y-%m-%d')} y {date_max.strftime('%Y-%m-%d')}."
        )

        return {
            "initial_rows": qr.initial_rows,
            "valid_rows": qr.final_rows,
            "dropped_pct": dropped_pct,
            "invalid_dates": qr.invalid_dates,
            "invalid_numeric": qr.invalid_numeric,
            "missing_days": missing_days,
            "incomplete_weeks": incomplete_weeks,
            "partial_months": partial_months,
            "coverage_note": coverage_note,
            "risk_level": risk_level,
        }

    def summary(self) -> dict:
        """Métricas resumen globales."""
        c = self.config
        df = self.df

        if df.empty:
            return {
                "total_revenue": 0,
                "total_orders": 0,
                "total_units": 0,
                "avg_ticket": 0,
                "avg_items_per_order": 0,
                "unique_products": 0,
                "multi_item_pct": 0,
                "multi_item_orders": 0,
                "date_min": "N/A",
                "date_max": "N/A",
                "date_range": "N/A",
                "date_min_iso": None,
                "date_max_iso": None,
            }

        total_revenue = int(df[c.col_total].sum())
        total_orders = df[c.col_order_id].nunique()
        total_units = int(df[c.col_quantity].sum())
        unique_products = df[c.col_product].nunique()

        orders_per_cart = df.groupby(c.col_order_id).size()
        multi_item_orders = int((orders_per_cart >= 2).sum())
        avg_items = round(orders_per_cart.mean(), 1) if not orders_per_cart.empty else 0
        multi_item_pct = round(multi_item_orders / total_orders * 100, 1) if total_orders else 0

        return {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_units": total_units,
            "avg_ticket": int(total_revenue / total_orders) if total_orders else 0,
            "avg_items_per_order": avg_items,
            "unique_products": unique_products,
            "multi_item_pct": multi_item_pct,
            "multi_item_orders": multi_item_orders,
            "date_min": df[c.col_date].min().strftime("%d %b"),
            "date_max": df[c.col_date].max().strftime("%d %b %Y"),
            "date_range": f"{df[c.col_date].min().strftime('%d %b')} – {df[c.col_date].max().strftime('%d %b %Y')}",
            "date_min_iso": df[c.col_date].min().strftime("%Y-%m-%d"),
            "date_max_iso": df[c.col_date].max().strftime("%Y-%m-%d"),
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. ANALYSIS MODULES
# ═══════════════════════════════════════════════════════════════════════

class AnalysisModules:
    """
    Cada método es un módulo de análisis independiente.
    Retorna un dict con los resultados listos para el renderer.
    """

    def __init__(self, df: pd.DataFrame, config: ReportConfig):
        self.df = df
        self.c = config

    # ─── TIMELINE ───────────────────────────────────────────────────

    def timeline(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "daily": pd.DataFrame(columns=["date_str", "revenue", "orders", "rolling_rev", "rolling_orders"]),
                "weekly": pd.DataFrame(columns=["year_week", "revenue", "orders"]),
                "dow": pd.DataFrame(columns=["day", "revenue", "orders"]),
                "heatmap_days": c.day_order,
                "heatmap_hours": [],
                "heatmap_z": [],
                "hourly": pd.DataFrame(columns=["hour", "revenue", "orders"]),
                "monthly_cat": pd.DataFrame(columns=["month", "category", "revenue"]),
                "best_hour": 0,
                "best_day": "N/A",
                "best_combo": "N/A",
            }

        # Daily
        daily = df.groupby(c.col_date).agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
            units=(c.col_quantity, "sum"),
        ).reset_index()
        daily["date_str"] = daily[c.col_date].dt.strftime("%Y-%m-%d")
        daily["rolling_rev"] = daily["revenue"].rolling(c.rolling_window, min_periods=1).mean()
        daily["rolling_orders"] = daily["orders"].rolling(c.rolling_window, min_periods=1).mean()

        # Weekly
        weekly = df.groupby("year_week").agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
            units=(c.col_quantity, "sum"),
        ).reset_index().sort_values("year_week")

        # Day of week
        dow = df.groupby(c.col_weekday).agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
        ).reindex(c.day_order).reset_index()
        dow.columns = ["day", "revenue", "orders"]

        # Heatmap: hour × day
        heatmap = df.groupby([c.col_weekday, c.col_hour])[c.col_order_id].nunique().reset_index()
        heatmap.columns = ["day", "hour", "orders"]
        hm_pivot = heatmap.pivot(index="hour", columns="day", values="orders").fillna(0)
        hm_pivot = hm_pivot.reindex(columns=c.day_order)

        # Hourly
        hourly = df.groupby(c.col_hour).agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
        ).reset_index()
        hourly.columns = ["hour", "revenue", "orders"]

        # Monthly by category
        monthly_cat = df.groupby(["year_month", "Categoria"])[c.col_total].sum().reset_index()
        monthly_cat.columns = ["month", "category", "revenue"]

        # Peak identification
        best_hour = int(hourly.loc[hourly["orders"].idxmax(), "hour"])
        best_day = dow.loc[dow["orders"].idxmax(), "day"]
        # Best hour×day combo from heatmap
        hm_flat = heatmap.loc[heatmap["orders"].idxmax()]
        best_combo = f"{hm_flat['day']} {int(hm_flat['hour'])}:00"

        return {
            "daily": daily[["date_str", "revenue", "orders", "rolling_rev", "rolling_orders"]],
            "weekly": weekly[["year_week", "revenue", "orders"]],
            "dow": dow,
            "heatmap_days": c.day_order,
            "heatmap_hours": list(hm_pivot.index.astype(int)),
            "heatmap_z": hm_pivot.values.tolist(),
            "hourly": hourly,
            "monthly_cat": monthly_cat,
            "best_hour": best_hour,
            "best_day": best_day,
            "best_combo": best_combo,
        }

    # ─── PRODUCTS ───────────────────────────────────────────────────

    def products(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            empty_prod = pd.DataFrame(columns=[c.col_product, "units", "revenue", "orders", "avg_price", "category", "cum_rev_pct", "rev_share"])
            return {
                "all_products": empty_prod,
                "top_n": empty_prod,
                "n_pareto": 0,
                "total_products": 0,
                "cat_totals": pd.Series(dtype=float),
            }

        prod = df.groupby(c.col_product).agg(
            units=(c.col_quantity, "sum"),
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
            avg_price=(c.col_unit_price, "mean"),
            category=("Categoria", "first"),
        ).reset_index()
        prod = prod.sort_values("revenue", ascending=False).reset_index(drop=True)
        prod["cum_rev_pct"] = (prod["revenue"].cumsum() / prod["revenue"].sum() * 100).round(1)
        prod["rev_share"] = (prod["revenue"] / prod["revenue"].sum() * 100).round(2)

        # Pareto: how many products for threshold
        n_pareto = int((prod["cum_rev_pct"] <= c.pareto_threshold).sum())
        if n_pareto == 0 and not prod.empty:
            n_pareto = 1

        # Top N
        top_n = prod.head(c.top_n_products)

        # Category totals
        cat_totals = df.groupby("Categoria")[c.col_total].sum().sort_values(ascending=False)

        return {
            "all_products": prod,
            "top_n": top_n,
            "n_pareto": n_pareto,
            "total_products": len(prod),
            "cat_totals": cat_totals,
        }

    # ─── MARKET BASKET ──────────────────────────────────────────────

    def market_basket(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "pairs": pd.DataFrame(columns=["product_a", "product_b", "count", "support", "lift"]),
                "cat_pairs": pd.DataFrame(columns=["cat_a", "cat_b", "count"]),
                "total_baskets": 0,
                "high_lift_pairs": [],
            }

        # Filter multi-item orders
        order_sizes = df.groupby(c.col_order_id).size()
        multi_ids = order_sizes[order_sizes >= c.min_basket_size].index
        multi = df[df[c.col_order_id].isin(multi_ids)]

        baskets = multi.groupby(c.col_order_id)[c.col_product].apply(list)
        total_baskets = len(baskets)
        if total_baskets == 0:
            return {
                "pairs": pd.DataFrame(columns=["product_a", "product_b", "count", "support", "lift"]),
                "cat_pairs": pd.DataFrame(columns=["cat_a", "cat_b", "count"]),
                "total_baskets": 0,
                "high_lift_pairs": [],
            }
        item_counts = multi.groupby(c.col_product)[c.col_order_id].nunique().to_dict()

        # Count pairs
        pair_counter = Counter()
        for items in baskets:
            unique_items = sorted(set(items))
            if len(unique_items) >= 2:
                for pair in combinations(unique_items, 2):
                    pair_counter[pair] += 1

        # Build pair stats with lift
        pair_data = []
        for (a, b), count in pair_counter.most_common(c.top_n_pairs * 2):
            support = count / total_baskets
            sup_a = item_counts.get(a, 1) / total_baskets
            sup_b = item_counts.get(b, 1) / total_baskets
            lift = support / (sup_a * sup_b) if (sup_a * sup_b) > 0 else 0
            pair_data.append({
                "product_a": a, "product_b": b,
                "count": count, "support": round(support, 4),
                "lift": round(lift, 2),
            })
        pairs_df = pd.DataFrame(pair_data).head(c.top_n_pairs)

        # Category combinations
        cat_baskets = multi.groupby(c.col_order_id)["Categoria"].apply(lambda x: sorted(set(x)))
        cat_pair_counter = Counter()
        for cats in cat_baskets:
            if len(cats) >= 2:
                for pair in combinations(cats, 2):
                    cat_pair_counter[pair] += 1
        cat_pairs = [{"cat_a": a, "cat_b": b, "count": cnt}
                     for (a, b), cnt in cat_pair_counter.most_common(10)]

        # High lift pairs (strong unexpected associations)
        high_lift = [p for p in pair_data if p["lift"] >= 1.5][:5]

        return {
            "pairs": pairs_df,
            "cat_pairs": pd.DataFrame(cat_pairs),
            "total_baskets": total_baskets,
            "high_lift_pairs": high_lift,
        }

    # ─── CART COMPOSITION ───────────────────────────────────────────

    def cart_composition(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "cart_dist": pd.DataFrame(columns=["products_in_cart", "count"]),
                "ticket_stats": {"mean": 0, "median": 0, "p25": 0, "p75": 0, "max": 0},
                "ticket_dist": pd.DataFrame(columns=["bucket", "count"]),
                "cart_weekly": pd.DataFrame(columns=["week", "avg_items"]),
                "segment_stats": pd.DataFrame(columns=["segment", "orders", "share_pct", "avg_ticket"]),
                "multi_bucket_stats": pd.DataFrame(columns=["bucket", "orders", "share_multi_pct", "avg_ticket"]),
                "single_top_ticket": pd.DataFrame(columns=["product", "orders", "avg_ticket"]),
            }

        cart = df.groupby(c.col_order_id).agg(
            items=(c.col_quantity, "sum"),
            unique_products=(c.col_product, "nunique"),
            total=(c.col_total, "sum"),
            categories=("Categoria", "nunique"),
        ).reset_index()

        # Distribution of unique products per order
        cart_dist = cart["unique_products"].value_counts().sort_index().reset_index()
        cart_dist.columns = ["products_in_cart", "count"]

        # Ticket stats
        ticket_stats = {
            "mean": int(cart["total"].mean()),
            "median": int(cart["total"].median()),
            "p25": int(cart["total"].quantile(0.25)),
            "p75": int(cart["total"].quantile(0.75)),
            "max": int(cart["total"].max()),
        }

        # Ticket buckets
        cart["ticket_bucket"] = pd.cut(
            cart["total"], bins=c.ticket_bins, labels=c.ticket_labels
        )
        ticket_dist = cart["ticket_bucket"].value_counts().sort_index().reset_index()
        ticket_dist.columns = ["bucket", "count"]

        # Cart size evolution by week
        items_per_order = df.groupby(["year_week", c.col_order_id]).size().reset_index(name="items")
        cart_weekly = items_per_order.groupby("year_week")["items"].mean().reset_index()
        cart_weekly.columns = ["week", "avg_items"]
        cart_weekly = cart_weekly.sort_values("week")

        # Segmentación por tamaño de carrito en unidades (1 unidad vs 2+ unidades)
        one_unit = cart[cart["items"] == 1].copy()
        multi_unit = cart[cart["items"] >= 2].copy()
        total_orders = len(cart)
        segment_stats = pd.DataFrame(
            [
                {
                    "segment": "1 unidad",
                    "orders": int(len(one_unit)),
                    "share_pct": round(float(len(one_unit) / total_orders * 100), 1) if total_orders else 0.0,
                    "avg_ticket": float(one_unit["total"].mean()) if not one_unit.empty else 0.0,
                },
                {
                    "segment": "2+ unidades",
                    "orders": int(len(multi_unit)),
                    "share_pct": round(float(len(multi_unit) / total_orders * 100), 1) if total_orders else 0.0,
                    "avg_ticket": float(multi_unit["total"].mean()) if not multi_unit.empty else 0.0,
                },
            ]
        )

        # Buckets de canastas 2+ por número total de unidades
        if multi_unit.empty:
            multi_bucket = pd.DataFrame(columns=["bucket", "orders", "share_multi_pct", "avg_ticket"])
        else:
            multi_unit = multi_unit.copy()
            multi_unit["multi_bucket"] = np.where(
                multi_unit["items"] >= 4,
                "4+ unidades",
                multi_unit["items"].astype(int).astype(str) + " unidades",
            )
            multi_bucket = multi_unit.groupby("multi_bucket").agg(
                orders=(c.col_order_id, "nunique"),
                avg_ticket=("total", "mean"),
            ).reset_index()
            order_preference = {"2 unidades": 0, "3 unidades": 1, "4+ unidades": 2}
            multi_bucket["sort_key"] = multi_bucket["multi_bucket"].map(order_preference).fillna(9)
            multi_bucket = multi_bucket.sort_values("sort_key").drop(columns=["sort_key"])
            total_multi = int(multi_bucket["orders"].sum())
            multi_bucket["share_multi_pct"] = (
                multi_bucket["orders"] / total_multi * 100 if total_multi else 0.0
            )
            multi_bucket = multi_bucket.rename(columns={"multi_bucket": "bucket"})

        # Ranking de productos en canastas de 1 unidad, por volumen (órdenes)
        if one_unit.empty:
            single_top_ticket = pd.DataFrame(columns=["product", "orders", "avg_ticket"])
        else:
            one_unit_ids = set(one_unit[c.col_order_id])
            one_unit_rows = df[df[c.col_order_id].isin(one_unit_ids)].copy()
            one_unit_orders = one_unit_rows.groupby(c.col_order_id).agg(
                product=(c.col_product, "first"),
                ticket=(c.col_total, "sum"),
            ).reset_index()
            single_top_ticket = one_unit_orders.groupby("product").agg(
                orders=(c.col_order_id, "nunique"),
                avg_ticket=("ticket", "mean"),
            ).reset_index()
            single_top_ticket = single_top_ticket[
                single_top_ticket["orders"] >= c.min_single_ticket_orders
            ].sort_values(["orders", "avg_ticket"], ascending=[False, False]).head(c.top_n_single_ticket_products)

        return {
            "cart_dist": cart_dist,
            "ticket_stats": ticket_stats,
            "ticket_dist": ticket_dist,
            "cart_weekly": cart_weekly,
            "segment_stats": segment_stats,
            "multi_bucket_stats": multi_bucket,
            "single_top_ticket": single_top_ticket,
        }

    # ─── TRENDS (productos creciendo / decreciendo) ────────────────

    def trends(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "growing": [],
                "declining": [],
                "months": [],
                "base_month": "",
                "compare_month": "",
            }

        # Monthly revenue and orders per product
        monthly_prod = df.groupby(["year_month", c.col_product]).agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
        ).reset_index()
        months = sorted(monthly_prod["year_month"].unique())

        if len(months) < c.trend_min_months:
            return {
                "growing": [],
                "declining": [],
                "months": months,
                "base_month": "",
                "compare_month": "",
            }

        # Compare last full month vs first full month
        # (skip last month if it might be partial — check if it has < 20 days)
        last_month_days = df[df["year_month"] == months[-1]][c.col_date].dt.day.nunique()
        if last_month_days < 20 and len(months) > 2:
            compare_month = months[-2]
            base_month = months[0]
        else:
            compare_month = months[-1]
            base_month = months[0]

        base_df = monthly_prod[monthly_prod["year_month"] == base_month].set_index(c.col_product)
        compare_df = monthly_prod[monthly_prod["year_month"] == compare_month].set_index(c.col_product)
        if base_df.empty or compare_df.empty:
            return {
                "growing": [],
                "declining": [],
                "months": months,
                "base_month": base_month,
                "compare_month": compare_month,
            }

        base_revenue = base_df["revenue"]
        compare_revenue = compare_df["revenue"]
        base_orders = base_df["orders"]

        # Avoid noisy % changes driven by tiny base volumes.
        eligible_products = base_revenue[
            (base_revenue >= c.trend_min_base_revenue)
            & (base_orders >= c.trend_min_base_orders)
        ].index
        base = base_revenue[base_revenue.index.isin(eligible_products)]
        compare = compare_revenue[compare_revenue.index.isin(eligible_products)]
        if base.empty or compare.empty:
            return {
                "growing": [],
                "declining": [],
                "months": months,
                "base_month": base_month,
                "compare_month": compare_month,
                "eligible_count": 0,
            }

        # Calculate growth
        growth = ((compare - base) / base * 100).dropna()
        growth = growth[growth.abs() > 10]  # Only meaningful changes

        growing = growth[growth > 0].sort_values(ascending=False).head(5)
        declining = growth[growth < 0].sort_values().head(5)

        return {
            "growing": [{"product": p, "growth_pct": round(v, 1)} for p, v in growing.items()],
            "declining": [{"product": p, "growth_pct": round(v, 1)} for p, v in declining.items()],
            "base_month": base_month,
            "compare_month": compare_month,
            "eligible_count": int(len(eligible_products)),
        }

    # ─── TICKET & OPPORTUNITY WINDOWS ──────────────────────────────

    def ticket_opportunities(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "day_ticket": pd.DataFrame(columns=["day", "orders", "avg_ticket"]),
                "hour_ticket": pd.DataFrame(columns=["hour", "orders", "avg_ticket"]),
                "opportunity_hours": pd.DataFrame(columns=["hour", "orders", "avg_ticket", "gap_pct"]),
            }

        order_totals = df.groupby([c.col_order_id, c.col_weekday, c.col_hour]).agg(
            ticket=(c.col_total, "sum")
        ).reset_index()

        day_ticket = order_totals.groupby(c.col_weekday).agg(
            orders=(c.col_order_id, "nunique"),
            avg_ticket=("ticket", "mean"),
        ).reindex(c.day_order).reset_index()
        day_ticket.columns = ["day", "orders", "avg_ticket"]

        hour_ticket = order_totals.groupby(c.col_hour).agg(
            orders=(c.col_order_id, "nunique"),
            avg_ticket=("ticket", "mean"),
        ).reset_index()
        hour_ticket.columns = ["hour", "orders", "avg_ticket"]

        baseline_ticket = float(order_totals["ticket"].mean()) if not order_totals.empty else 0.0
        min_orders_cutoff = float(hour_ticket["orders"].quantile(0.6)) if not hour_ticket.empty else 0.0
        opp = hour_ticket[
            (hour_ticket["orders"] >= min_orders_cutoff)
            & (hour_ticket["avg_ticket"] < baseline_ticket)
        ].copy()
        if not opp.empty and baseline_ticket > 0:
            opp["gap_pct"] = ((baseline_ticket - opp["avg_ticket"]) / baseline_ticket * 100).round(1)
        else:
            opp["gap_pct"] = 0.0
        opp = opp.sort_values(["orders", "gap_pct"], ascending=[False, False]).head(5)

        return {
            "day_ticket": day_ticket,
            "hour_ticket": hour_ticket,
            "opportunity_hours": opp,
        }

    # ─── MARKET BASKET RULES A -> B ───────────────────────────────

    def basket_rules(self) -> dict:
        df, c = self.df, self.c
        empty_rules = pd.DataFrame(columns=[
            "antecedent", "consequent", "count", "support", "confidence", "lift", "conviction", "score"
        ])
        if df.empty:
            return {"rules": empty_rules}

        order_sizes = df.groupby(c.col_order_id).size()
        multi_ids = order_sizes[order_sizes >= c.min_basket_size].index
        multi = df[df[c.col_order_id].isin(multi_ids)]
        baskets = multi.groupby(c.col_order_id)[c.col_product].apply(lambda x: sorted(set(x)))
        total_baskets = len(baskets)
        if total_baskets == 0:
            return {"rules": empty_rules}

        item_counts = Counter()
        directed_counts = Counter()
        for items in baskets:
            for item in items:
                item_counts[item] += 1
            for a, b in combinations(items, 2):
                directed_counts[(a, b)] += 1
                directed_counts[(b, a)] += 1

        rules = []
        for (a, b), count in directed_counts.items():
            support = count / total_baskets
            sup_a = item_counts[a] / total_baskets
            sup_b = item_counts[b] / total_baskets
            confidence = count / item_counts[a] if item_counts[a] > 0 else 0.0
            lift = support / (sup_a * sup_b) if sup_a > 0 and sup_b > 0 else 0.0
            conviction = ((1 - sup_b) / (1 - confidence)) if confidence < 0.999 and (1 - confidence) > 0 else float("inf")
            score = confidence * lift * np.log1p(count)
            rules.append({
                "antecedent": a,
                "consequent": b,
                "count": int(count),
                "support": round(support, 4),
                "confidence": round(confidence, 3),
                "lift": round(lift, 2),
                "conviction": round(conviction, 2) if conviction != float("inf") else 99.99,
                "score": round(float(score), 3),
            })

        rules_df = pd.DataFrame(rules)
        if rules_df.empty:
            return {"rules": empty_rules}

        rules_df = rules_df[(rules_df["count"] >= 15) & (rules_df["confidence"] >= 0.15)]
        # Remove inverse duplicates (A->B vs B->A), keeping the stronger direction.
        rules_df["pair_key"] = rules_df.apply(
            lambda row: "||".join(sorted([str(row["antecedent"]), str(row["consequent"])])),
            axis=1,
        )
        rules_df = rules_df.sort_values(["score", "count", "confidence"], ascending=[False, False, False])
        rules_df = rules_df.drop_duplicates(subset=["pair_key"], keep="first")
        rules_df = rules_df.drop(columns=["pair_key"]).head(20)
        return {"rules": rules_df}

    # ─── ANOMALIES (días atípicos) ─────────────────────────────────

    def anomalies(self) -> dict:
        df, c = self.df, self.c
        if df.empty:
            return {
                "high_days": [],
                "low_days": [],
                "avg_daily_revenue": 0,
                "std_daily_revenue": 0,
            }

        daily = df.groupby(c.col_date).agg(
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
        ).reset_index()

        rev_mean = daily["revenue"].mean()
        rev_std = daily["revenue"].std()
        if pd.isna(rev_std) or rev_std == 0:
            return {
                "high_days": [],
                "low_days": [],
                "avg_daily_revenue": int(rev_mean) if not pd.isna(rev_mean) else 0,
                "std_daily_revenue": 0,
            }
        threshold_high = rev_mean + c.anomaly_std_threshold * rev_std
        threshold_low = rev_mean - c.anomaly_std_threshold * rev_std

        high_days = daily[daily["revenue"] > threshold_high].sort_values("revenue", ascending=False)
        low_days = daily[daily["revenue"] < threshold_low].sort_values("revenue")

        return {
            "high_days": [
                {"date": row[c.col_date].strftime("%d %b"), "revenue": int(row["revenue"]),
                 "orders": int(row["orders"]), "z_score": round((row["revenue"] - rev_mean) / rev_std, 1)}
                for _, row in high_days.head(5).iterrows()
            ],
            "low_days": [
                {"date": row[c.col_date].strftime("%d %b"), "revenue": int(row["revenue"]),
                 "orders": int(row["orders"]), "z_score": round((row["revenue"] - rev_mean) / rev_std, 1)}
                for _, row in low_days.head(5).iterrows()
            ],
            "avg_daily_revenue": int(rev_mean),
            "std_daily_revenue": int(rev_std),
        }

    # ─── PROFITABILITY (Rentabilidad por margen) ──────────────────

    def profitability(self) -> dict:
        """
        Análisis de rentabilidad si datos de margen están disponibles.
        Retorna estructura vacía si margin_pct no existe en CSV.
        """
        df, c = self.df, self.c
        
        # Si no hay columna de margen, retorna estructura vacía
        if c.col_margin_pct not in df.columns:
            return {
                "has_margin_data": False,
                "margin_available": False,
                "products_by_profitability": pd.DataFrame(),
                "profit_pareto": pd.DataFrame(),
                "n_profit_pareto": 0,
                "product_classification": {},
                "margin_by_category": pd.Series(dtype=float),
                "margin_weighted_pairs": [],
                "margin_row_coverage_pct": 0.0,
            }
        
        # Si todos los valores de margen son NaN, también retorna vacío
        if df[c.col_margin_pct].isna().all():
            return {
                "has_margin_data": False,
                "margin_available": False,
                "products_by_profitability": pd.DataFrame(),
                "profit_pareto": pd.DataFrame(),
                "n_profit_pareto": 0,
                "product_classification": {},
                "margin_by_category": pd.Series(dtype=float),
                "margin_weighted_pairs": [],
                "margin_row_coverage_pct": 0.0,
            }
        
        # Usar solo productos con margen observado (sin imputación).
        # Evita asignar márgenes artificiales a SKUs que vienen nulos en el CSV.
        prod = df.groupby(c.col_product).agg(
            units=(c.col_quantity, "sum"),
            revenue=(c.col_total, "sum"),
            orders=(c.col_order_id, "nunique"),
            avg_margin=(c.col_margin_pct, "mean"),
            category=("Categoria", "first"),
        ).reset_index()

        prod = prod[prod["avg_margin"].notna()].copy()
        if prod.empty:
            return {
                "has_margin_data": False,
                "margin_available": False,
                "products_by_profitability": pd.DataFrame(),
                "profit_pareto": pd.DataFrame(),
                "n_profit_pareto": 0,
                "product_classification": {},
                "margin_by_category": pd.Series(dtype=float),
                "margin_weighted_pairs": [],
                "margin_row_coverage_pct": 0.0,
            }
        
        prod["profit"] = prod["revenue"] * prod["avg_margin"] / 100
        prod = prod.sort_values("profit", ascending=False).reset_index(drop=True)
        prod["cum_profit_pct"] = (prod["profit"].cumsum() / prod["profit"].sum() * 100).round(1)
        prod["profit_share"] = (prod["profit"] / prod["profit"].sum() * 100).round(2)

        margin_row_coverage_pct = round(float(df[c.col_margin_pct].notna().mean() * 100), 1)
        
        # Pareto de profit
        n_profit_pareto = int((prod["cum_profit_pct"] <= c.margin_pareto_threshold).sum())
        if n_profit_pareto == 0 and not prod.empty:
            n_profit_pareto = 1
        
        # Clasificación de productos: Tractor, Champion, Question Mark
        # Basado en: frecuencia (orders) y margen (avg_margin)
        orders_median = prod["orders"].median()
        margin_median = prod["avg_margin"].median()
        
        classification = {}
        for _, row in prod.iterrows():
            product_name = row[c.col_product]
            high_volume = row["orders"] >= orders_median
            high_margin = row["avg_margin"] >= margin_median
            
            if high_volume and high_margin:
                classification[product_name] = "Champion"
            elif high_volume and not high_margin:
                classification[product_name] = "Tractor"
            elif not high_volume and high_margin:
                classification[product_name] = "Gem"
            else:
                classification[product_name] = "Niche"
        
        # Margen promedio por categoría
        df_with_margin = df[df[c.col_margin_pct].notna()].copy()
        margin_by_cat = df_with_margin.groupby("Categoria")[c.col_margin_pct].mean().sort_values(ascending=False)
        
        # Pairs ponderados por margen (si existen datos de basket)
        basket = self.market_basket()
        margin_weighted_pairs = []
        if not basket["high_lift_pairs"]:
            logger.debug("No high lift pairs found for margin weighting")
        else:
            for pair in basket["high_lift_pairs"]:
                a_prod = prod[prod[c.col_product] == pair["product_a"]]
                b_prod = prod[prod[c.col_product] == pair["product_b"]]
                if not a_prod.empty and not b_prod.empty:
                    # Score ajustado por margen del consequent
                    margin_score = pair["lift"] * b_prod.iloc[0]["avg_margin"] / 100
                    margin_weighted_pairs.append({
                        "antecedent": pair["product_a"],
                        "consequent": pair["product_b"],
                        "original_lift": pair["lift"],
                        "margin_weighted_score": round(margin_score, 3),
                    })
        
        return {
            "has_margin_data": True,
            "margin_available": True,
            "products_by_profitability": prod,
            "profit_pareto": prod.head(n_profit_pareto),
            "n_profit_pareto": n_profit_pareto,
            "product_classification": classification,
            "classification_thresholds": {
                "orders_median": float(orders_median),
                "margin_median": float(margin_median),
            },
            "margin_by_category": margin_by_cat,
            "margin_weighted_pairs": margin_weighted_pairs,
            "margin_row_coverage_pct": margin_row_coverage_pct,
        }

    def interactive_base(self) -> dict:
        """Dataset base a nivel fila para filtros de fecha en frontend."""
        df, c = self.df, self.c
        columns = [
            "date_str",
            "year_week",
            "year_month",
            "day",
            "hour",
            "order_id",
            "product",
            "category",
            "quantity",
            "unit_price",
            "total",
            "margin_pct",
        ]
        if df.empty:
            return {"rows": pd.DataFrame(columns=columns)}

        base = pd.DataFrame(
            {
                "date_str": df[c.col_date].dt.strftime("%Y-%m-%d"),
                "year_week": df["year_week"],
                "year_month": df["year_month"],
                "day": df[c.col_weekday],
                "hour": df[c.col_hour],
                "order_id": df[c.col_order_id],
                "product": df[c.col_product],
                "category": df["Categoria"],
                "quantity": df[c.col_quantity],
                "unit_price": df[c.col_unit_price],
                "total": df[c.col_total],
                "margin_pct": df[c.col_margin_pct] if c.col_margin_pct in df.columns else np.nan,
            }
        )
        return {"rows": base}

    def bundle_recommendations(self) -> dict:
        """Sugiere bundles por seguridad de lanzamiento, test y balance margen/conversión."""
        df, c = self.df, self.c
        empty = {
            "has_data": False,
            "has_margin_data": False,
            "margin_row_coverage_pct": 0.0,
            "launch_ready": [],
            "test_candidates": [],
            "balanced": [],
            "margin_focus": [],
            "conversion_focus": [],
            "notes": "Sin datos suficientes para construir sugerencias de bundles.",
        }
        if df.empty:
            return empty

        rules_df = self.basket_rules()["rules"].copy()
        if rules_df.empty:
            return {
                **empty,
                "notes": "No hay reglas A→B suficientes para recomendaciones accionables.",
            }

        stats = df.groupby(c.col_product).agg(
            orders=(c.col_order_id, "nunique"),
            revenue=(c.col_total, "sum"),
            avg_margin=(c.col_margin_pct, "mean") if c.col_margin_pct in df.columns else (c.col_total, lambda _: np.nan),
            category=("Categoria", "first"),
        )

        has_margin = c.col_margin_pct in df.columns and not df[c.col_margin_pct].isna().all()
        margin_coverage = round(float(df[c.col_margin_pct].notna().mean() * 100), 1) if c.col_margin_pct in df.columns else 0.0

        classification: dict[str, str] = {}
        margin_median = np.nan
        if has_margin:
            prof = self.profitability()
            classification = prof.get("product_classification", {})
            margin_median = float(prof.get("classification_thresholds", {}).get("margin_median", np.nan))

        combos: list[dict[str, Any]] = []
        for _, row in rules_df.iterrows():
            a = str(row["antecedent"])
            b = str(row["consequent"])
            if a not in stats.index or b not in stats.index:
                continue

            a_stat = stats.loc[a]
            b_stat = stats.loc[b]
            a_margin = float(a_stat["avg_margin"]) if pd.notna(a_stat["avg_margin"]) else np.nan
            b_margin = float(b_stat["avg_margin"]) if pd.notna(b_stat["avg_margin"]) else np.nan
            combined_margin = float(np.nanmean([a_margin, b_margin])) if (pd.notna(a_margin) or pd.notna(b_margin)) else np.nan
            adoption_score = float(row["confidence"] * row["lift"] * np.log1p(row["count"]))
            margin_boost = (1 + max(0.0, b_margin) / 100) if pd.notna(b_margin) else 1.0
            margin_score = adoption_score * margin_boost

            anchor_class = classification.get(a, "Unknown")
            consequent_class = classification.get(b, "Unknown")
            is_launch_ready = (
                row["confidence"] >= 0.25
                and row["count"] >= 20
                and (not has_margin or (pd.notna(b_margin) and pd.notna(margin_median) and b_margin >= margin_median))
            )

            combos.append(
                {
                    "anchor": a,
                    "target": b,
                    "anchor_category": str(a_stat["category"]),
                    "target_category": str(b_stat["category"]),
                    "anchor_class": anchor_class,
                    "target_class": consequent_class,
                    "count": int(row["count"]),
                    "support": float(row["support"]),
                    "confidence": float(row["confidence"]),
                    "lift": float(row["lift"]),
                    "conviction": float(row["conviction"]),
                    "target_margin": round(float(b_margin), 2) if pd.notna(b_margin) else None,
                    "combined_margin": round(float(combined_margin), 2) if pd.notna(combined_margin) else None,
                    "adoption_score": round(adoption_score, 3),
                    "margin_score": round(float(margin_score), 3),
                    "launch_ready": is_launch_ready,
                }
            )

        if not combos:
            return {
                **empty,
                "notes": "No se pudieron construir bundles con los datos actuales.",
            }

        combos_df = pd.DataFrame(combos)
        for score_col in ["adoption_score", "margin_score"]:
            col_min = combos_df[score_col].min()
            col_max = combos_df[score_col].max()
            if col_max > col_min:
                combos_df[f"{score_col}_norm"] = (combos_df[score_col] - col_min) / (col_max - col_min)
            else:
                combos_df[f"{score_col}_norm"] = 0.5
        combos_df["balanced_score"] = (0.5 * combos_df["adoption_score_norm"] + 0.5 * combos_df["margin_score_norm"]).round(3)

        launch_ready = combos_df[combos_df["launch_ready"]].sort_values(
            ["balanced_score", "confidence", "count"],
            ascending=[False, False, False],
        ).head(8)
        test_candidates = combos_df[~combos_df["launch_ready"]].sort_values(
            ["lift", "confidence", "count"],
            ascending=[False, False, False],
        ).head(8)
        balanced = combos_df.sort_values(
            ["balanced_score", "confidence"],
            ascending=[False, False],
        ).head(10)
        margin_focus = combos_df.sort_values(
            ["margin_score", "target_margin", "confidence"],
            ascending=[False, False, False],
        ).head(10)
        conversion_focus = combos_df.sort_values(
            ["confidence", "count", "lift"],
            ascending=[False, False, False],
        ).head(10)

        notes = (
            "Ranking balanceado por probabilidad de adopción y aporte de margen."
            if has_margin
            else "Sin margen confiable: ranking prioriza señales de conversión (confidence/lift/soporte)."
        )

        return {
            "has_data": True,
            "has_margin_data": bool(has_margin),
            "margin_row_coverage_pct": margin_coverage,
            "launch_ready": launch_ready.to_dict("records"),
            "test_candidates": test_candidates.to_dict("records"),
            "balanced": balanced.to_dict("records"),
            "margin_focus": margin_focus.to_dict("records"),
            "conversion_focus": conversion_focus.to_dict("records"),
            "notes": notes,
        }

    # ─── RUN ALL ────────────────────────────────────────────────────

    def run_all(self) -> dict:
        """Ejecuta todos los módulos de análisis. Punto de extensión principal."""
        return {
            "interactive_base": self.interactive_base(),
            "timeline": self.timeline(),
            "products": self.products(),
            "basket": self.market_basket(),
            "cart": self.cart_composition(),
            "trends": self.trends(),
            "anomalies": self.anomalies(),
            "ticket": self.ticket_opportunities(),
            "basket_rules": self.basket_rules(),
            "profitability": self.profitability(),  # PHASE 4: Análisis de rentabilidad
            "bundles": self.bundle_recommendations(),
            # ↓ EXTENSION POINT: agregar nuevos módulos aquí
            # "search": self.search_analysis(),
            # "cohorts": self.cohort_analysis(),
        }


# ═══════════════════════════════════════════════════════════════════════
# 4. INSIGHT ENGINE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Insight:
    """Un hallazgo generado automáticamente."""
    title: str
    body: str
    category: str          # "revenue", "product", "basket", "time", "trend", "anomaly"
    severity: str = "info" # "info", "warning", "opportunity", "risk"
    priority: int = 5      # 1 (highest) to 10 (lowest)
    action: str = ""
    owner: str = ""
    horizon: str = ""


# Registry of insight rules
_insight_rules: list[Callable] = []


def insight_rule(func):
    """Decorador para registrar una regla de insight."""
    _insight_rules.append(func)
    return func


# ─── PREDEFINED INSIGHT RULES ──────────────────────────────────────

@insight_rule
def insight_pareto(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Concentración de revenue en pocos productos."""
    n = analyses["products"]["n_pareto"]
    total = analyses["products"]["total_products"]
    if total == 0:
        return None
    pct = round(n / total * 100)
    return Insight(
        title="Concentración de revenue",
        body=f"Solo <strong>{n} productos</strong> de {total} ({pct}%) generan el "
             f"{config.pareto_threshold:.0f}% del revenue. "
             f"Un problema de disponibilidad en cualquiera de los top 5 tiene impacto "
             f"directo en GMV. Estos items deben estar siempre visibles y bien nombrados "
             f"en el catálogo.",
        category="revenue",
        severity="warning",
        priority=1,
    )


@insight_rule
def insight_beverages_anchor(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Detecta si una categoría domina en market basket como ancla."""
    pairs = analyses["basket"]["pairs"]
    if pairs.empty:
        return None

    # Count category appearances in top pairs
    cat_counts = Counter()
    for _, row in pairs.iterrows():
        prods = analyses["products"]["all_products"]
        for p_col in ["product_a", "product_b"]:
            match = prods[prods[config.col_product] == row[p_col]]
            if not match.empty:
                cat_counts[match.iloc[0]["category"]] += 1

    if not cat_counts:
        return None
    top_cat, top_count = cat_counts.most_common(1)[0]
    total_appearances = sum(cat_counts.values())
    pct = round(top_count / total_appearances * 100)

    if pct < 40:
        return None

    return Insight(
        title=f"{top_cat} como ancla del carrito",
        body=f"La categoría <strong>{top_cat}</strong> aparece en el {pct}% de los pares "
             f"más frecuentes del market basket. Actúa como ancla que acompaña productos "
             f"de mayor ticket. <em>Oportunidad:</em> optimizar combos con esta categoría "
             f"como base.",
        category="basket",
        severity="opportunity",
        priority=2,
    )


@insight_rule
def insight_multi_item_rate(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Tasa de carritos multi-item."""
    pct = summary["multi_item_pct"]
    avg = summary["avg_items_per_order"]
    severity = "opportunity" if pct < 50 else "info"

    return Insight(
        title=f"{pct}% de órdenes son multi-item",
        body=f"El promedio es {avg} items por orden. "
             f"{'Hay espacio significativo para incrementar cross-sell, especialmente en carritos de 1 item.' if pct < 50 else 'Base sólida para cross-sell — enfocarse en incrementar de 2 a 3 items.'} ",
        category="basket",
        severity=severity,
        priority=3,
    )


@insight_rule
def insight_ticket_distribution(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Análisis de distribución de ticket."""
    ts = analyses["cart"]["ticket_stats"]
    if ts["mean"] == 0:
        return None
    skew = "derecha" if ts["mean"] > ts["median"] else "izquierda"
    gap_pct = round(abs(ts["mean"] - ts["median"]) / ts["mean"] * 100)

    return Insight(
        title=f"Ticket promedio ${ts['mean']:,} {config.currency}",
        body=f"El ticket mediano (${ts['median']:,}) está {'por debajo' if ts['median'] < ts['mean'] else 'por encima'} "
             f"del promedio ({gap_pct}% de diferencia), indicando una distribución con cola a la {skew}. "
             f"El 50% de los pedidos cae entre ${ts['p25']:,} y ${ts['p75']:,}.",
        category="revenue",
        severity="info",
        priority=4,
    )


@insight_rule
def insight_tractor_products(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Detecta productos 'Tractor' (alto volumen, bajo margen)."""
    if not analyses["profitability"]["has_margin_data"]:
        return None
    
    classification = analyses["profitability"]["product_classification"]
    tractors = [p for p, c in classification.items() if c == "Tractor"]
    
    if not tractors or len(tractors) < 2:
        return None
    
    # Get profitability data
    profs = analyses["profitability"]["products_by_profitability"]
    tractor_data = profs[profs[config.col_product].isin(tractors[:3])]
    
    margin_avg = tractor_data["avg_margin"].mean()
    orders_avg = int(tractor_data["orders"].mean())
    
    return Insight(
        title=f"Productos 'Tractor': alto volumen, margen {margin_avg:.1f}%",
        body=f"Encontrados {len(tractors)} productos con alto volumen pero bajo margen (Tractores). "
             f"Estos conducen tráfico pero generan poco profit. Considera: "
             f"(1) aumentar precio en 5-10%, (2) vender como bundle con items de alto margen, "
             f"(3) usar como lead magnet pero promover cross-sell agresivamente. "
             f"Promedio: {orders_avg} órdenes/período, {margin_avg:.1f}% margen.",
        category="profitability",
        severity="warning",
        priority=2,
        action="Revisar precios y estrategia de empaquetamiento",
        owner="Pricing & Marketing",
        horizon="Corto plazo (1-2 semanas)"
    )


@insight_rule
def insight_champion_products(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Destaca productos 'Champion' (alto volumen, alto margen)."""
    if not analyses["profitability"]["has_margin_data"]:
        return None
    
    classification = analyses["profitability"]["product_classification"]
    champions = [p for p, c in classification.items() if c == "Champion"]
    
    if not champions:
        return None
    
    profs = analyses["profitability"]["products_by_profitability"]
    champion_data = profs[profs[config.col_product].isin(champions[:3])]
    
    margin_avg = champion_data["avg_margin"].mean()
    profit_share = champion_data["profit_share"].sum()
    total_revenue = summary.get("total_revenue", 0)
    revenue_share = (champion_data["revenue"].sum() / total_revenue * 100) if total_revenue else 0.0
    
    return Insight(
        title=f"Productos 'Champion': {len(champions)} ítems high-margin high-volume",
        body=f"Estos {len(champions)} productos son los generadores de profit principales (margen promedio {margin_avg:.1f}%). "
               f"Representan {profit_share:.1f}% del profit total pero solo {revenue_share:.1f}% del revenue. "
             f"Estrategia: maximizar visibilidad, stock seguro, promoción selectiva (ej: en bundles de bajo margen).",
        category="profitability",
        severity="info",
        priority=1,
        action="Garantizar stock y visibilidad máxima",
        owner="Catalog & Inventory",
        horizon="Continuo"
    )


@insight_rule
def insight_margin_concentration(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Detecta concentración de profit en pocas categorías."""
    if not analyses["profitability"]["has_margin_data"]:
        return None
    
    margin_by_cat = analyses["profitability"]["margin_by_category"]
    if margin_by_cat.empty or len(margin_by_cat) < 2:
        return None
    
    # Margen máximo vs mínimo
    max_margin = margin_by_cat.iloc[0]
    min_margin = margin_by_cat.iloc[-1]
    gap = max_margin - min_margin
    
    if gap < 5:  # Diferencia pequeña, no es un insight
        return None
    
    high_margin_cats = margin_by_cat[margin_by_cat >= margin_by_cat.mean()].index.tolist()
    
    return Insight(
        title=f"Dispersión de margen: {max_margin:.1f}% - {min_margin:.1f}% entre categorías",
        body=f"Hay una brecha de {gap:.1f}% entre la categoría de mayor margen ({margin_by_cat.index[0]}) "
             f"y menor ({margin_by_cat.index[-1]}). Las categorías de alto margen ({', '.join(high_margin_cats[:2])}) "
             f"deberían recibir prioridad en promoción y merchandising. Considere: "
             f"(1) revisar precios de bajo margen, (2) empaquetar bajo margen con alto margen, "
             f"(3) probar descuentos en bajo margen solo para incentivar cross-sell.",
        category="profitability",
        severity="warning",
        priority=3,
        action="Optimizar mix de precios por categoría",
        owner="Pricing & Category Management",
        horizon="Medio plazo (2-4 semanas)"
    )


@insight_rule
def insight_peak_times(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Picos de demanda temporal."""
    tl = analyses["timeline"]
    return Insight(
        title="Picos de demanda",
        body=f"La hora pico es las <strong>{tl['best_hour']}:00</strong> y el día con más "
             f"órdenes es <strong>{tl['best_day']}</strong>. "
             f"La combinación más fuerte es <strong>{tl['best_combo']}</strong>. "
             f"Estos picos informan decisiones de staffing y timing de promociones.",
        category="time",
        severity="info",
        priority=3,
    )


@insight_rule
def insight_high_lift_pairs(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Pares con lift alto → oportunidad de combos."""
    high_lift = analyses["basket"]["high_lift_pairs"]
    if not high_lift:
        return None

    pair_strs = [f"<strong>{p['product_a']}</strong> + <strong>{p['product_b']}</strong> (lift {p['lift']})"
                 for p in high_lift[:3]]
    pairs_html = ", ".join(pair_strs)

    return Insight(
        title="Oportunidad de combos (Market Basket)",
        body=f"Los pares con lift alto representan combinaciones que ocurren más de lo esperado "
             f"por azar — candidatos naturales para combos en el menú: {pairs_html}. "
             f"Los pares de alta frecuencia pero lift bajo ya son habituales; el upside está "
             f"en promover los de alto lift.",
        category="basket",
        severity="opportunity",
        priority=2,
    )


@insight_rule
def insight_growing_products(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Productos en tendencia de crecimiento."""
    growing = analyses["trends"].get("growing", [])
    if not growing:
        return None

    items = ", ".join([f"<strong>{g['product']}</strong> (+{g['growth_pct']}%)" for g in growing[:3]])
    base = analyses["trends"]["base_month"]
    comp = analyses["trends"]["compare_month"]
    eligible = analyses["trends"].get("eligible_count", 0)

    return Insight(
        title="Productos en crecimiento",
        body=f"Comparando {base} vs {comp}, los productos con mayor crecimiento en revenue "
             f"son: {items}. Estos representan demanda emergente que podría amplificarse con "
             f"mejor posicionamiento en el catálogo. El ranking filtra productos con base suficiente "
             f"({eligible} elegibles) para evitar porcentajes engañosos.",
        category="trend",
        severity="opportunity",
        priority=3,
    )


@insight_rule
def insight_declining_products(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Productos en caída."""
    declining = analyses["trends"].get("declining", [])
    if not declining:
        return None

    items = ", ".join([f"<strong>{d['product']}</strong> ({d['growth_pct']}%)" for d in declining[:3]])
    base = analyses["trends"]["base_month"]
    comp = analyses["trends"]["compare_month"]
    eligible = analyses["trends"].get("eligible_count", 0)

    return Insight(
        title="Productos en declive",
        body=f"Comparando {base} vs {comp}, los productos con mayor caída: {items}. "
             f"Investigar si se debe a disponibilidad, estacionalidad, o pérdida de demanda genuina. "
             f"El análisis usa solo productos con base suficiente ({eligible} elegibles).",
        category="trend",
        severity="risk",
        priority=3,
    )


@insight_rule
def insight_anomaly_days(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Días atípicos de revenue."""
    anom = analyses["anomalies"]
    high = anom["high_days"]
    low = anom["low_days"]
    if not high and not low:
        return None

    parts = []
    if high:
        top = high[0]
        parts.append(f"Día de mayor pico: <strong>{top['date']}</strong> "
                     f"(${top['revenue']:,}, {top['z_score']}σ sobre la media)")
    if low:
        bot = low[0]
        parts.append(f"Día más bajo: <strong>{bot['date']}</strong> "
                     f"(${bot['revenue']:,}, {abs(bot['z_score'])}σ bajo la media)")

    return Insight(
        title="Días atípicos",
        body=f"El revenue diario promedio es ${anom['avg_daily_revenue']:,} ± "
             f"${anom['std_daily_revenue']:,}. {'. '.join(parts)}. "
             f"Los picos pueden indicar eventos especiales o campañas efectivas; "
             f"los valles pueden indicar problemas operativos o fechas festivas.",
        category="anomaly",
        severity="info",
        priority=5,
    )


@insight_rule
def insight_category_balance(summary: dict, analyses: dict, config: ReportConfig) -> Optional[Insight]:
    """Balance entre categorías."""
    cat_totals = analyses["products"]["cat_totals"]
    if cat_totals.empty:
        return None
    total = cat_totals.sum()
    top_cat = cat_totals.index[0]
    top_pct = round(cat_totals.iloc[0] / total * 100, 1)

    top3 = [(cat, round(val / total * 100, 1)) for cat, val in cat_totals.head(3).items()]
    top3_str = ", ".join([f"<strong>{c}</strong> ({p}%)" for c, p in top3])

    return Insight(
        title="Balance de categorías",
        body=f"Las 3 categorías principales concentran el "
             f"{sum(p for _, p in top3):.0f}% del revenue: {top3_str}. "
             f"{'La distribución está relativamente balanceada.' if top_pct < 40 else f'{top_cat} domina con {top_pct}% — alta dependencia de una categoría.'}",
        category="revenue",
        severity="info" if top_pct < 40 else "warning",
        priority=4,
    )


# ─── ENGINE ─────────────────────────────────────────────────────────

class InsightEngine:
    """Ejecuta todas las reglas registradas y retorna insights ordenados."""

    @staticmethod
    def generate(summary: dict, analyses: dict, config: ReportConfig) -> list[Insight]:
        insights = []
        defaults = {
            "revenue": ("Optimizar portafolio y pricing de top SKUs", "Comercial", "1-2 semanas"),
            "basket": ("Lanzar test A/B de bundles en menú", "Growth", "2 semanas"),
            "time": ("Ajustar staffing y slots promocionales", "Operaciones", "1 semana"),
            "trend": ("Reubicar productos en catálogo según tendencia", "Catálogo", "1-2 semanas"),
            "anomaly": ("Auditar campañas/eventos y operación del día", "BI + Operaciones", "72 horas"),
        }
        for rule in _insight_rules:
            try:
                result = rule(summary, analyses, config)
                if result is not None:
                    if not result.action or not result.owner or not result.horizon:
                        action, owner, horizon = defaults.get(
                            result.category,
                            ("Revisar hallazgo y priorizar experimento", "Equipo BI", "1 semana"),
                        )
                        result.action = result.action or action
                        result.owner = result.owner or owner
                        result.horizon = result.horizon or horizon
                    insights.append(result)
            except Exception as e:
                logger.warning("Insight rule '%s' failed: %s: %s", rule.__name__, type(e).__name__, e)
        insights.sort(key=lambda x: x.priority)
        return insights


# ═══════════════════════════════════════════════════════════════════════
# 5. REPORT RENDERER
# ═══════════════════════════════════════════════════════════════════════

class ReportRenderer:
    """Genera el HTML final del reporte."""

    SEVERITY_STYLES = {
        "info": "",
        "warning": "yellow",
        "opportunity": "green",
        "risk": "red",
    }

    def __init__(
        self,
        summary: dict[str, Any],
        analyses: dict[str, Any],
        insights: list[Insight],
        quality: dict[str, Any],
        recommendations: list[dict[str, str]],
        config: ReportConfig,
    ) -> None:
        self.s = summary
        self.a = analyses
        self.insights = insights
        self.q = quality
        self.recommendations = recommendations
        self.c = config

    @staticmethod
    def _j(obj: Any) -> str:
        """Serialize to JSON for embedding in HTML."""
        if isinstance(obj, pd.DataFrame):
            return obj.to_json(orient="records")
        return json.dumps(obj, default=str)

    def render(self) -> str:
        return (
            self._head()
            + self._kpi_section()
            + self._executive_section()
            + self._quality_section()
            + self._date_filter_section()
            + self._timeline_section()
            + self._products_section()
            + self._profitability_section()  # PHASE 4: Rentabilidad
            + self._bundles_section()
            + self._basket_section()
            + self._cart_section()
            + self._ticket_section()
            + self._rules_section()
            + self._insights_section()
            + self._footer()
        )

    # ─── HTML SKELETON ──────────────────────────────────────────────

    def _head(self) -> str:
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.c.store_name} — Sales Analytics Report</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0c0f14; --surface: #151921; --surface2: #1c2230;
  --border: #2a3040; --text: #e2e6ed; --text-muted: #8a92a3;
  --accent: #f59e0b; --accent2: #3b82f6; --accent3: #10b981;
  --accent4: #ef4444; --accent5: #8b5cf6;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:40px 24px; }}
.header {{ margin-bottom:48px; padding-bottom:32px; border-bottom:1px solid var(--border); }}
.header-label {{ font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:3px; text-transform:uppercase; color:var(--accent); margin-bottom:12px; }}
.header h1 {{ font-size:32px; font-weight:700; letter-spacing:-0.5px; margin-bottom:8px; }}
.header .subtitle {{ font-size:15px; color:var(--text-muted); }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:48px; }}
.kpi {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; position:relative; overflow:hidden; }}
.kpi::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; }}
.kpi:nth-child(1)::before {{ background:linear-gradient(135deg,#f59e0b,#f97316); }}
.kpi:nth-child(2)::before {{ background:linear-gradient(135deg,#3b82f6,#6366f1); }}
.kpi:nth-child(3)::before {{ background:linear-gradient(135deg,#10b981,#06b6d4); }}
.kpi:nth-child(4)::before {{ background:linear-gradient(135deg,#ef4444,#f97316); }}
.kpi:nth-child(5)::before {{ background:linear-gradient(135deg,#f59e0b,#f97316); }}
.kpi:nth-child(6)::before {{ background:linear-gradient(135deg,#3b82f6,#6366f1); }}
.kpi-label {{ font-size:11px; text-transform:uppercase; letter-spacing:1.5px; color:var(--text-muted); margin-bottom:8px; font-family:'JetBrains Mono',monospace; }}
.kpi-value {{ font-size:26px; font-weight:700; letter-spacing:-0.5px; }}
.kpi-sub {{ font-size:12px; color:var(--text-muted); margin-top:4px; }}
.section {{ margin-bottom:56px; }}
.section-header {{ display:flex; align-items:baseline; gap:12px; margin-bottom:24px; }}
.section-num {{ font-family:'JetBrains Mono',monospace; font-size:13px; color:var(--accent); font-weight:500; }}
.section-title {{ font-size:20px; font-weight:700; }}
.section-desc {{ font-size:14px; color:var(--text-muted); margin-top:-16px; margin-bottom:24px; max-width:700px; }}
.section-explainer {{ background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.25); border-radius:10px; padding:12px 14px; margin:-10px 0 18px 0; font-size:13px; color:#b9c3d8; line-height:1.6; }}
.chart-row {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; }}
.chart-row.full {{ grid-template-columns:1fr; }}
.chart-box {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; min-height:350px; }}
.chart-box-title {{ font-size:13px; font-weight:500; color:var(--text-muted); margin-bottom:12px; font-family:'JetBrains Mono',monospace; letter-spacing:0.5px; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.data-table th {{ text-align:left; padding:10px 12px; border-bottom:2px solid var(--border); color:var(--text-muted); font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:1px; font-weight:500; }}
.data-table td {{ padding:10px 12px; border-bottom:1px solid var(--border); }}
.data-table tr:hover td {{ background:var(--surface2); }}
.mono {{ font-family:'JetBrains Mono',monospace; font-size:12px; }}
.insight-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.insight {{ background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:8px; padding:20px; }}
.insight.green {{ border-left-color:var(--accent3); }}
.insight.yellow {{ border-left-color:var(--accent); }}
.insight.red {{ border-left-color:var(--accent4); }}
.insight-title {{ font-weight:700; font-size:14px; margin-bottom:8px; }}
.insight-body {{ font-size:13px; color:var(--text-muted); line-height:1.7; }}
.insight-meta {{ margin-top:10px; font-size:11px; color:var(--text-muted); font-family:'JetBrains Mono',monospace; }}
.pill {{ display:inline-block; padding:4px 8px; border:1px solid var(--border); border-radius:999px; font-size:11px; margin-right:8px; }}
.pill.high {{ border-color:#ef4444; color:#ef4444; }}
.pill.medium {{ border-color:#f59e0b; color:#f59e0b; }}
.pill.low {{ border-color:#10b981; color:#10b981; }}
.mini-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:14px; }}
.mini-card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px; }}
.mini-title {{ font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:1px; font-family:'JetBrains Mono',monospace; margin-bottom:6px; }}
.mini-value {{ font-size:22px; font-weight:700; }}
.classification-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px; margin-top:12px; }}
.class-badge {{ background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:12px; text-align:center; font-size:12px; font-weight:500; }}
.cat-top-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin-top:10px; }}
.cat-top-box {{ background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:12px; overflow-x:auto; }}
.cat-top-box .data-table {{ min-width:560px; }}
.cat-orders {{ color:var(--text-muted); font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:400; }}
.info-box {{ background:var(--surface); border-left:3px solid var(--accent2); border-radius:8px; padding:16px; margin-top:16px; font-size:13px; line-height:1.6; }}
.info-box ul {{ margin-left:20px; margin-top:8px; }}
.info-box li {{ margin-bottom:6px; }}
.info-box code {{ background:var(--surface2); padding:2px 6px; border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:12px; }}
.filter-panel {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px; margin-bottom:36px; }}
.filter-row {{ display:flex; gap:12px; align-items:end; flex-wrap:wrap; }}
.filter-field {{ display:flex; flex-direction:column; gap:6px; min-width:180px; }}
.filter-label {{ font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--text-muted); font-family:'JetBrains Mono',monospace; }}
.filter-input {{ background:var(--surface2); border:1px solid var(--border); color:var(--text); border-radius:8px; padding:8px 10px; font-size:13px; }}
.filter-checkboxes {{ display:flex; flex-wrap:wrap; gap:8px; padding:10px; border:1px solid var(--border); border-radius:8px; background:var(--surface2); min-height:42px; }}
.filter-check {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--text); font-family:'JetBrains Mono',monospace; }}
.filter-check input {{ accent-color:#3b82f6; }}
.btn {{ border:1px solid var(--border); background:var(--surface2); color:var(--text); border-radius:8px; padding:8px 12px; font-size:12px; cursor:pointer; }}
.btn:hover {{ border-color:#3b82f6; }}
.filter-status {{ margin-top:10px; font-size:12px; color:var(--text-muted); }}
.section-badge {{ display:inline-block; margin-left:10px; font-size:10px; color:#f59e0b; border:1px solid rgba(245,158,11,0.4); border-radius:999px; padding:2px 8px; font-family:'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:1px; vertical-align:middle; }}
.range-label {{ margin-top:-12px; margin-bottom:16px; font-size:12px; color:#9db0d1; font-family:'JetBrains Mono',monospace; }}
.footer {{ margin-top:48px; padding-top:24px; border-top:1px solid var(--border); font-size:12px; color:var(--text-muted); font-family:'JetBrains Mono',monospace; }}
@media(max-width:768px) {{ .chart-row,.insight-grid,.cat-top-grid {{ grid-template-columns:1fr; }} .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <div class="header-label">{self.c.brand} · {self.c.store_name}</div>
  <h1>Sales & Cart Analysis Report</h1>
  <div class="subtitle">{self.s['date_range']} · {self.s['total_orders']:,} órdenes · {self.s['unique_products']} productos</div>
</div>
"""

    def _kpi_section(self) -> str:
        s = self.s
        n_pareto = self.a["products"]["n_pareto"]
        return f"""
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">Revenue Total</div><div class="kpi-value">${s['total_revenue']/1e6:.1f}M</div><div class="kpi-sub">{self.c.currency}</div></div>
  <div class="kpi"><div class="kpi-label">Órdenes</div><div class="kpi-value">{s['total_orders']:,}</div><div class="kpi-sub">{s['date_range']}</div></div>
  <div class="kpi"><div class="kpi-label">Ticket Promedio</div><div class="kpi-value">${s['avg_ticket']:,}</div><div class="kpi-sub">{self.c.currency} por orden</div></div>
  <div class="kpi"><div class="kpi-label">Items / Orden</div><div class="kpi-value">{s['avg_items_per_order']}</div><div class="kpi-sub">{s['multi_item_pct']}% con 2+ items</div></div>
  <div class="kpi"><div class="kpi-label">Unidades</div><div class="kpi-value">{s['total_units']:,}</div><div class="kpi-sub">vendidas en total</div></div>
  <div class="kpi"><div class="kpi-label">{self.c.pareto_threshold:.0f}% Revenue</div><div class="kpi-value">{n_pareto} items</div><div class="kpi-sub">de {s['unique_products']} totales</div></div>
</div>
<div class="section-explainer"><strong>Cómo leer este bloque:</strong> resume salud comercial del período. Si baja <em>items/orden</em>, priorizar cross-sell; si sube la concentración (Pareto), aumentar foco operativo en los SKUs tractores para reducir riesgo de quiebres.</div>
"""

    def _executive_section(self) -> str:
        cards = ""
        for rec in self.recommendations[:3]:
            cards += (
                f'<div class="mini-card">'
                f'<div class="mini-title">{rec["impact"]} · {rec["owner"]} · {rec["horizon"]}</div>'
                f'<div style="font-size:14px">{rec["action"]}</div>'
                f'</div>'
            )
        return f"""
<div class="section">
    <div class="section-header"><span class="section-num">00</span><span class="section-title">Qué Haría Esta Semana</span></div>
    <div class="section-desc">Recomendaciones accionables priorizadas automáticamente con la información disponible.</div>
    <div class="section-explainer"><strong>Cómo usarlo:</strong> este bloque traduce hallazgos en decisiones concretas. Ejecuta primero acciones de impacto <em>ALTO</em>, revisa resultado en 1-2 semanas y reitera.</div>
    <div class="mini-grid">{cards}</div>
</div>
"""

    def _quality_section(self) -> str:
        q = self.q
        risk = q.get("risk_level", "medium")
        partials = q.get("partial_months", [])
        partials_text = ", ".join([f"{m['month']} ({m['observed_days']}/{m['month_days']} días)" for m in partials[:4]])
        if not partials_text:
            partials_text = "No se detectaron meses parciales."

        invalid_numeric_total = sum(q.get("invalid_numeric", {}).values())
        return f"""
<div class="section">
    <div class="section-header"><span class="section-num">DQ</span><span class="section-title">Data Quality</span></div>
    <div class="section-desc">{q.get('coverage_note', '')}</div>
    <div class="section-explainer"><strong>Cómo leerlo:</strong> mide confiabilidad del reporte. Riesgo alto implica decisiones tácticas de corto plazo, pero evita conclusiones estratégicas hasta corregir cobertura y calidad.</div>
    <div><span class="pill {risk}">Riesgo {risk.upper()}</span></div>
    <div class="mini-grid">
        <div class="mini-card"><div class="mini-title">Filas válidas</div><div class="mini-value">{q.get('valid_rows', 0):,}</div></div>
        <div class="mini-card"><div class="mini-title">% descartadas</div><div class="mini-value">{q.get('dropped_pct', 0):.2f}%</div></div>
        <div class="mini-card"><div class="mini-title">Días faltantes</div><div class="mini-value">{q.get('missing_days', 0)}</div></div>
        <div class="mini-card"><div class="mini-title">Semanas incompletas</div><div class="mini-value">{q.get('incomplete_weeks', 0)}</div></div>
    </div>
    <div class="section-desc" style="margin-top:14px">Fechas inválidas detectadas: <strong>{q.get('invalid_dates', 0)}</strong>. Coerciones numéricas totales: <strong>{invalid_numeric_total}</strong>. Meses parciales: {partials_text}</div>
</div>
"""

    def _date_filter_section(self) -> str:
        return """
<div class="filter-panel">
    <div class="section-header" style="margin-bottom:10px"><span class="section-num">FLT</span><span class="section-title">Selector de Fecha (Modo Interactivo)</span></div>
    <div class="section-desc" style="margin-bottom:10px">Afecta timeline, heatmap, productos, ticket y rentabilidad. Market Basket, reglas e insights se mantienen en período completo.</div>
    <div class="filter-row">
        <div class="filter-field">
            <span class="filter-label">Fecha Inicio</span>
            <input id="date-from" class="filter-input" type="date" />
        </div>
        <div class="filter-field">
            <span class="filter-label">Fecha Fin</span>
            <input id="date-to" class="filter-input" type="date" />
        </div>
        <div class="filter-field" style="min-width:320px;flex:1 1 320px;">
            <span class="filter-label">Días de la Semana</span>
            <div class="filter-checkboxes" id="weekday-multiselect">
                <label class="filter-check"><input type="checkbox" id="weekday-check-all" checked />Select all</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Lun" checked />Lun</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Mar" checked />Mar</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Mié" checked />Mié</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Jue" checked />Jue</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Vie" checked />Vie</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Sáb" checked />Sáb</label>
                <label class="filter-check"><input type="checkbox" class="weekday-check" value="Dom" checked />Dom</label>
            </div>
        </div>
        <div class="filter-field">
            <span class="filter-label">Tipo de Día</span>
            <select id="day-type-filter" class="filter-input">
                <option value="all">Todos</option>
                <option value="workdays">Días Laborales (L-V)</option>
                <option value="weekend">Fin de Semana (S-D)</option>
            </select>
        </div>
        <button class="btn" id="date-apply" type="button">Aplicar rango</button>
        <button class="btn" id="date-reset" type="button">Reset</button>
    </div>
    <div id="date-filter-status" class="filter-status">Rango activo: período completo · días: todos · tipo: todos.</div>
</div>
"""

    # ─── TIMELINE ───────────────────────────────────────────────────

    def _timeline_section(self) -> str:
        tl = self.a["timeline"]
        return f"""
<div class="section">
  <div class="section-header"><span class="section-num">01</span><span class="section-title">Ventas en el Tiempo</span></div>
  <div class="section-desc">Evolución diaria y semanal. Línea naranja = media móvil {self.c.rolling_window}d.</div>
    <div id="range-label-timeline" class="range-label">Rango del gráfico: período completo</div>
    <div class="section-explainer"><strong>Interpretación:</strong> compara tendencia real vs ruido diario. Los picos recurrentes indican ventanas para promociones y staffing; caídas sostenidas exigen revisar disponibilidad y visibilidad en app.</div>
  <div class="chart-row full"><div class="chart-box"><div id="chart-daily"></div></div></div>
  <div class="chart-row">
    <div class="chart-box"><div id="chart-weekly"></div></div>
    <div class="chart-box"><div id="chart-dow"></div></div>
  </div>
    <div class="chart-row full"><div class="chart-box"><div class="chart-box-title">Mapa de calor por hora × día de semana</div><div style="display:flex;gap:10px;align-items:center;margin-bottom:8px"><label class="filter-label" for="heatmap-metric" style="margin:0">Métrica</label><select id="heatmap-metric" class="filter-input" style="min-width:260px"><option value="orders">Órdenes</option><option value="avg_orders_per_day">Promedio de órdenes (por día del período)</option><option value="avg_items_per_cart">Promedio de productos por carrito</option><option value="avg_ticket">Ticket promedio</option></select></div><div id="chart-heatmap"></div></div></div>
  <div class="chart-row full"><div class="chart-box"><div id="chart-cat-monthly"></div></div></div>
</div>
"""

    # ─── PRODUCTS ───────────────────────────────────────────────────

    def _products_section(self) -> str:
        return """
<div class="section">
  <div class="section-header"><span class="section-num">02</span><span class="section-title">Análisis de Productos</span></div>
  <div class="section-desc">Top productos por revenue, curva de Pareto y precio vs. volumen.</div>
    <div id="range-label-products" class="range-label">Rango del gráfico: período completo</div>
    <div class="section-explainer"><strong>Interpretación:</strong> identifica qué productos sostienen el negocio y cuáles tienen potencial de escala. Decisiones típicas: proteger top SKUs, reordenar catálogo y ajustar mix precio-volumen.</div>
  <div class="chart-row full"><div class="chart-box"><div id="chart-top20"></div></div></div>
  <div class="chart-row">
    <div class="chart-box"><div id="chart-pareto"></div></div>
    <div class="chart-box"><div id="chart-scatter"></div></div>
  </div>
</div>
"""

    # ─── PROFITABILITY (PHASE 4) ─────────────────────────────────────

    def _profitability_section(self) -> str:
        prof = self.a["profitability"]
        
        # Si no hay datos de margen, mostrar mensaje
        if not prof["has_margin_data"]:
            return """
<div class="section">
  <div class="section-header"><span class="section-num">02B</span><span class="section-title">Análisis de Rentabilidad</span></div>
  <div class="section-desc">Requiere datos de margen para análisis de profitabilidad.</div>
  <div class="section-explainer"><strong>Estado:</strong> no hay datos de margen disponibles. Proporcione una columna <code>margin_pct</code> (% de margen por producto) en el CSV para activar análisis de productos Tractor/Champion, Pareto de profit y estrategias de pricing.</div>
  <div class="info-box">
    <p>Para habilitar análisis de rentabilidad:</p>
    <ul>
      <li>Agregue una columna <code>margin_pct</code> al CSV con el % de margen de cada producto</li>
      <li>El analizador detectará automáticamente la columna y calculará profit por producto</li>
      <li>Se mostrarán productos clasificados como: Champion (alto margen, alto volumen), Tractor (bajo margen, alto volumen), Gem (alto margen, bajo volumen), Niche (bajo margen, bajo volumen)</li>
    </ul>
  </div>
</div>
"""
        
        # Hay datos de margen: mostrar análisis
        products = prof["products_by_profitability"]
        if products.empty:
            return ""
        
        # Clasificación de productos: tabla pequeña
        classification = prof["product_classification"]
        class_counts = Counter(classification.values())
        classification_html = ""
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
            icon = {"Champion": "👑", "Tractor": "🚜", "Gem": "💎", "Niche": "🎯"}.get(cls, "•")
            classification_html += f"<div class='class-badge'>{icon} {cls}: {count}</div>"

        thresholds = prof.get("classification_thresholds", {})
        orders_cut = thresholds.get("orders_median", 0.0)
        margin_cut = thresholds.get("margin_median", 0.0)
        margin_coverage = prof.get("margin_row_coverage_pct", 0.0)
        
        # Margen por categoría
        margin_by_cat = prof["margin_by_category"]
        cat_margin_rows = ""
        for cat, margin in margin_by_cat.items():
            cat_margin_rows += f"<tr><td>{cat}</td><td class='mono'>{margin:.1f}%</td></tr>"
        
        # Profit Pareto
        profit_pareto = prof["profit_pareto"]
        profit_pareto_html = ""
        if not profit_pareto.empty:
            cumsum = 0
            for _, row in profit_pareto.head(10).iterrows():
                cumsum += row["profit_share"]
                profit_pareto_html += (
                    f"<tr><td>{row[self.c.col_product]}</td>"
                    f"<td class='mono'>{int(row['revenue']):,}</td>"
                    f"<td class='mono'>{row['avg_margin']:.1f}%</td>"
                    f"<td class='mono'>{int(row['profit']):,}</td>"
                    f"<td class='mono'>{row['profit_share']:.1f}%</td>"
                    f"<td class='mono' style='color:#3b82f6'>{cumsum:.1f}%</td></tr>"
                )

        # Top 5 productos por categoría (ordenados por profit)
        category_top5_html = ""
        if "category" in products.columns and not products.empty:
            category_rank = (
                products.groupby("category", dropna=False)["orders"]
                .sum()
                .sort_values(ascending=False)
            )
            for category in category_rank.index.tolist():
                cat_df = products[products["category"].eq(category)].sort_values("profit", ascending=False)
                cat_name = str(category) if pd.notna(category) else "Sin categoría"
                cat_total_orders = int(category_rank.loc[category]) if pd.notna(category) else int(
                    products[products["category"].isna()]["orders"].sum()
                )
                rows_html = ""
                for _, row in cat_df.head(5).iterrows():
                    cls = classification.get(str(row[self.c.col_product]), "N/A")
                    rows_html += (
                        f"<tr><td>{row[self.c.col_product]}</td>"
                        f"<td class='mono'>{int(row['orders']):,}</td>"
                        f"<td class='mono'>{row['avg_margin']:.1f}%</td>"
                        f"<td class='mono'>{int(row['profit']):,}</td>"
                        f"<td class='mono'>{cls}</td></tr>"
                    )
                category_top5_html += (
                    f"<div class='cat-top-box'>"
                    f"<div class='chart-box-title'>Top 5 · {cat_name} <span class='cat-orders'>(Órdenes totales: {cat_total_orders:,})</span></div>"
                    f"<table class='data-table'><thead><tr><th>Producto</th><th>Órdenes</th><th>Margen</th><th>Profit</th><th>Clase</th></tr></thead><tbody>{rows_html}</tbody></table>"
                    f"</div>"
                )
        
        return f"""
<div class="section">
  <div class="section-header"><span class="section-num">02B</span><span class="section-title">Análisis de Rentabilidad</span></div>
    <div class="section-desc">Profit por producto, clasificación (Champion/Tractor/Gem/Niche), margen por categoría y top 5 por categoría.</div>
        <div id="range-label-profitability" class="range-label">Rango del gráfico: período completo</div>
    <div class="section-explainer"><strong>Interpretación:</strong> while revenue shows scale, profit reveals true drivers of business value. Champions deserve protection & promotion. Tractors need margin lift (via pricing, bundling, or cross-sell). Use this to rethink catalog priority and go-to-market strategy.</div>
    <div class="info-box">
        <p><strong>Cómo se calcula la Clasificación de Productos (algoritmo):</strong></p>
        <ul>
            <li><strong>Corte de volumen:</strong> órdenes por producto ≥ mediana de órdenes del portafolio (<strong>{orders_cut:.0f}</strong>) se considera alto volumen.</li>
            <li><strong>Corte de margen:</strong> margen promedio por producto ≥ mediana de margen del portafolio (<strong>{margin_cut:.1f}%</strong>) se considera alto margen.</li>
            <li><strong>Cobertura de margen:</strong> <strong>{margin_coverage:.1f}%</strong> de las filas trae <code>margin_pct</code>. Los cálculos de rentabilidad usan únicamente productos con margen observado.</li>
            <li><strong>Champion:</strong> alto volumen + alto margen. Producto prioritario para visibilidad, stock y promoción.</li>
            <li><strong>Tractor:</strong> alto volumen + bajo margen. Atrae demanda, pero requiere optimización de precio/bundle para capturar rentabilidad.</li>
            <li><strong>Gem:</strong> bajo volumen + alto margen. Tiene potencial de crecimiento rentable si gana exposición.</li>
            <li><strong>Niche:</strong> bajo volumen + bajo margen. Mantener selectivamente o redefinir propuesta.</li>
        </ul>
    </div>
  
  <div class="chart-row">
    <div class="chart-box">
      <div class="chart-box-title">Clasificación de Productos</div>
            <div id="profitability-classification-grid" class="classification-grid">{classification_html}</div>
    </div>
    <div class="chart-box">
      <div class="chart-box-title">Margen Promedio por Categoría</div>
            <table class="data-table"><thead><tr><th>Categoría</th><th>Margen %</th></tr></thead><tbody id="profitability-margin-by-category">{cat_margin_rows}</tbody></table>
    </div>
  </div>
  
  <div class="chart-row full">
    <div class="chart-box">
      <div class="chart-box-title">Pareto de Profit (Top 10 productos por profit)</div>
            <table class="data-table"><thead><tr><th>Producto</th><th>Revenue</th><th>Margen</th><th>Profit</th><th>% Profit</th><th>Acumulado %</th></tr></thead><tbody id="profitability-pareto-body">{profit_pareto_html}</tbody></table>
    </div>
  </div>

    <div class="chart-row full">
        <div class="chart-box">
            <div class="chart-box-title">Detalle para decisión: Top 5 productos por categoría</div>
            <div class="section-explainer"><strong>Uso sugerido:</strong> categorías ordenadas por relevancia operativa (órdenes totales desc). Dentro de cada categoría, prioriza Champions/Gems para visibilidad, usa Tractors para atraer tráfico y define bundles para mejorar margen del mix.</div>
            <div id="profitability-category-top-grid" class="cat-top-grid">{category_top5_html}</div>
        </div>
    </div>
</div>
"""

    @staticmethod
    def _bundle_rows(rows: list[dict[str, Any]], include_margin: bool) -> str:
        if not rows:
            return "<tr><td colspan='8'>Sin recomendaciones para este bloque.</td></tr>"
        output = ""
        for row in rows:
            target_margin = row.get("target_margin")
            margin_value = float(target_margin) if target_margin is not None and pd.notna(target_margin) else float("nan")
            margin_txt = (
                f"{margin_value:.1f}%"
                if include_margin and np.isfinite(margin_value)
                else "N/A"
            )
            output += (
                f"<tr><td>{row['anchor']}</td><td>{row['target']}</td>"
                f"<td class='mono'>{row['confidence']:.1%}</td>"
                f"<td class='mono'>{row['lift']:.2f}</td>"
                f"<td class='mono'>{row['count']}</td>"
                f"<td class='mono'>{margin_txt}</td>"
                f"<td>{row['anchor_class']}</td>"
                f"<td class='mono'>{row['balanced_score']:.2f}</td></tr>"
            )
        return output

    def _bundles_section(self) -> str:
        bundles = self.a.get("bundles", {})
        if not bundles.get("has_data"):
            return f"""
<div class="section">
  <div class="section-header"><span class="section-num">02C</span><span class="section-title">Bundles Recomendados</span></div>
  <div class="section-desc">{bundles.get('notes', 'Sin datos para recomendaciones de bundles.')}</div>
</div>
"""

        has_margin = bundles.get("has_margin_data", False)
        coverage = bundles.get("margin_row_coverage_pct", 0.0)
        launch_rows = self._bundle_rows(bundles.get("launch_ready", []), has_margin)
        test_rows = self._bundle_rows(bundles.get("test_candidates", []), has_margin)
        balanced_rows = self._bundle_rows(bundles.get("balanced", [])[:8], has_margin)

        return f"""
<div class="section">
  <div class="section-header"><span class="section-num">02C</span><span class="section-title">Bundles Recomendados</span></div>
  <div class="section-desc">Priorización por tres objetivos: lanzar con seguridad, testear hipótesis y balancear conversión+margen.</div>
    <div class="section-explainer"><strong>Cobertura de margen:</strong> {coverage:.1f}% · {bundles.get('notes', '')} Valores sin margen observado se muestran como <strong>N/A</strong>.</div>
  <div class="chart-row full"><div class="chart-box"><div class="chart-box-title">Lanzar con seguridad</div><table class="data-table"><thead><tr><th>Ancla</th><th>Sugerido</th><th>Confidence</th><th>Lift</th><th>Veces</th><th>Margen objetivo</th><th>Clase ancla</th><th>Score</th></tr></thead><tbody>{launch_rows}</tbody></table></div></div>
  <div class="chart-row full"><div class="chart-box"><div class="chart-box-title">Testear y medir</div><table class="data-table"><thead><tr><th>Ancla</th><th>Sugerido</th><th>Confidence</th><th>Lift</th><th>Veces</th><th>Margen objetivo</th><th>Clase ancla</th><th>Score</th></tr></thead><tbody>{test_rows}</tbody></table></div></div>
  <div class="chart-row full"><div class="chart-box"><div class="chart-box-title">Oportunidad balanceada</div><table class="data-table"><thead><tr><th>Ancla</th><th>Sugerido</th><th>Confidence</th><th>Lift</th><th>Veces</th><th>Margen objetivo</th><th>Clase ancla</th><th>Score</th></tr></thead><tbody>{balanced_rows}</tbody></table></div></div>
</div>
"""

    # ─── BASKET ─────────────────────────────────────────────────────

    def _basket_section(self) -> str:
        pairs = self.a["basket"]["pairs"]
        rows = ""
        for _, row in pairs.iterrows():
            lc = "#10b981" if row["lift"] >= 1.5 else ("#f59e0b" if row["lift"] >= 1 else "#ef4444")
            rows += f'<tr><td>{row["product_a"]}</td><td>{row["product_b"]}</td><td class="mono">{row["count"]}</td><td class="mono">{row["support"]:.1%}</td><td class="mono" style="color:{lc}">{row["lift"]:.2f}</td></tr>\n'

        return f"""
<div class="section">
    <div class="section-header"><span class="section-num">03</span><span class="section-title">Market Basket Analysis</span><span class="section-badge">Período completo</span></div>
  <div class="section-desc">Pares comprados juntos. Lift &gt; 1 = asociación positiva (ocurren juntos más de lo esperado).</div>
        <div class="section-explainer"><strong>Interpretación:</strong> un lift alto sugiere afinidad real entre productos y es candidato para bundle. Pares frecuentes con lift bajo suelen ser hábitos ya maduros, con menor upside promocional. Este bloque no cambia con el filtro de fecha interactivo para mantener consistencia estadística.</div>
  <div class="chart-row full"><div class="chart-box"><div id="chart-pairs"></div></div></div>
  <div class="chart-row">
    <div class="chart-box"><div class="chart-box-title">Detalle: Frecuencia y Lift</div>
      <table class="data-table"><thead><tr><th>Producto A</th><th>Producto B</th><th>Juntos</th><th>Soporte</th><th>Lift</th></tr></thead><tbody>{rows}</tbody></table>
    </div>
    <div class="chart-box"><div id="chart-catpairs"></div></div>
  </div>
</div>
"""

    # ─── CART COMPOSITION ───────────────────────────────────────────

    def _cart_section(self) -> str:
        cart = self.a["cart"]
        segment_rows = ""
        for _, row in cart.get("segment_stats", pd.DataFrame()).iterrows():
            segment_rows += (
                f"<tr><td>{row['segment']}</td><td class='mono'>{int(row['orders']):,}</td>"
                f"<td class='mono'>{float(row['share_pct']):.1f}%</td><td class='mono'>${float(row['avg_ticket']):,.0f}</td></tr>"
            )
        if not segment_rows:
            segment_rows = "<tr><td colspan='4'>Sin datos de segmentación.</td></tr>"

        multi_bucket_rows = ""
        for _, row in cart.get("multi_bucket_stats", pd.DataFrame()).iterrows():
            multi_bucket_rows += (
                f"<tr><td>{row['bucket']}</td><td class='mono'>{int(row['orders']):,}</td>"
                f"<td class='mono'>{float(row['share_multi_pct']):.1f}%</td><td class='mono'>${float(row['avg_ticket']):,.0f}</td></tr>"
            )
        if not multi_bucket_rows:
            multi_bucket_rows = "<tr><td colspan='4'>Sin canastas de 2+ unidades para este período.</td></tr>"

        single_top_rows = ""
        for i, row in enumerate(cart.get("single_top_ticket", pd.DataFrame()).itertuples(index=False), start=1):
            single_top_rows += (
                f"<tr><td class='mono'>{i}</td><td>{row.product}</td><td class='mono'>{int(row.orders):,}</td>"
                f"<td class='mono'>${float(row.avg_ticket):,.0f}</td></tr>"
            )
        if not single_top_rows:
            single_top_rows = "<tr><td colspan='4'>Sin datos suficientes para ranking de canastas de 1 unidad (revisar umbral mínimo).</td></tr>"

        return """
<div class="section">
  <div class="section-header"><span class="section-num">04</span><span class="section-title">Composición del Carrito</span></div>
  <div class="section-desc">Distribución de ítems por orden, ticket promedio y evolución.</div>
    <div class="section-badge">Período completo</div>
    <div class="section-explainer"><strong>Interpretación:</strong> muestra profundidad de compra. Si crece el peso de carritos de 1 ítem, priorizar upsell/cross-sell; si suben tickets altos, validar que no dependan de pocos eventos atípicos.</div>
  <div class="chart-row">
    <div class="chart-box"><div id="chart-cartdist"></div></div>
    <div class="chart-box"><div id="chart-ticketdist"></div></div>
  </div>
    <div class="chart-row">
        <div class="chart-box"><div id="chart-basket-share"></div></div>
        <div class="chart-box"><div id="chart-basket-ticket"></div></div>
    </div>
    <div class="chart-row full">
        <div class="chart-box"><div id="chart-multi-bucket-share"></div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box"><div class="chart-box-title">Share y ticket por tamaño de canasta (unidades)</div><table class="data-table"><thead><tr><th>Segmento</th><th>Órdenes</th><th>Share</th><th>Ticket Promedio</th></tr></thead><tbody>""" + segment_rows + """</tbody></table></div>
        <div class="chart-box"><div class="chart-box-title">Buckets de canastas 2+ unidades</div><table class="data-table"><thead><tr><th>Bucket</th><th>Órdenes</th><th>Share dentro de 2+</th><th>Ticket Promedio</th></tr></thead><tbody>""" + multi_bucket_rows + """</tbody></table></div>
    </div>
    <div class="chart-row full">
        <div class="chart-box"><div class="chart-box-title">Top productos de canastas Single-Product</div><table class="data-table"><thead><tr><th>#</th><th>Producto</th><th>Órdenes</th><th>Ticket Promedio</th></tr></thead><tbody>""" + single_top_rows + """</tbody></table></div>
    </div>
  <div class="chart-row full"><div class="chart-box"><div id="chart-cartevol"></div></div></div>
</div>
"""

    # ─── INSIGHTS ───────────────────────────────────────────────────

    def _insights_section(self) -> str:
        cards = ""
        for ins in self.insights:
            cls = self.SEVERITY_STYLES.get(ins.severity, "")
            cards += (
                f'<div class="insight {cls}">'
                f'<div class="insight-title">{ins.title}</div>'
                f'<div class="insight-body">{ins.body}</div>'
                f'<div class="insight-meta">Acción: {ins.action} · Responsable: {ins.owner} · Horizonte: {ins.horizon}</div>'
                f'</div>\n'
            )
        return f"""
<div class="section">
    <div class="section-header"><span class="section-num">05</span><span class="section-title">Hallazgos e Insights</span><span class="section-badge">Período completo</span></div>
    <div class="section-desc">{len(self.insights)} insights generados automáticamente, ordenados por prioridad. Se calculan sobre todo el período para evitar conclusiones inestables.</div>
  <div class="insight-grid">{cards}</div>
</div>
"""

    def _ticket_section(self) -> str:
        return """
<div class="section">
    <div class="section-header"><span class="section-num">06</span><span class="section-title">Ticket & Horas de Oportunidad</span></div>
    <div class="section-desc">Ticket promedio por día/hora y ventanas con buen tráfico pero ticket bajo (espacio para upsell).</div>
    <div id="range-label-ticket" class="range-label">Rango del gráfico: período completo</div>
    <div class="section-explainer"><strong>Interpretación:</strong> las horas marcadas como oportunidad combinan volumen relevante con ticket por debajo del promedio; son ideales para pruebas de combo o add-ons.</div>
    <div class="chart-row">
        <div class="chart-box"><div id="chart-ticket-day"></div></div>
        <div class="chart-box"><div id="chart-ticket-hour"></div></div>
    </div>
</div>
"""

    def _rules_section(self) -> str:
        rules = self.a["basket_rules"]["rules"]
        rows = ""
        for _, row in rules.head(12).iterrows():
            rows += (
                f"<tr><td>{row['antecedent']}</td><td>{row['consequent']}</td>"
                f"<td class='mono'>{row['count']}</td><td class='mono'>{row['confidence']:.1%}</td>"
                f"<td class='mono'>{row['lift']:.2f}</td><td class='mono'>{row['conviction']:.2f}</td></tr>"
            )
        return f"""
<div class="section">
    <div class="section-header"><span class="section-num">07</span><span class="section-title">Reglas A→B (Market Basket)</span><span class="section-badge">Período completo</span></div>
    <div class="section-desc">Reglas dirigidas con confidence, lift y conviction para campañas de bundle más precisas.</div>
    <div class="section-explainer"><strong>Cómo se calcula:</strong> <em>confidence</em> = probabilidad de comprar B dado A, <em>lift</em> = fuerza de asociación vs azar, <em>conviction</em> = estabilidad de la regla. <strong>Decisión:</strong> prioriza reglas con confidence alto, lift &gt; 1 y soporte suficiente para activar bundles o recomendadores. Este bloque se mantiene en período completo.</div>
    <div class="chart-row full"><div class="chart-box"><table class="data-table"><thead><tr><th>A (antecedente)</th><th>B (consecuente)</th><th>Veces</th><th>Confidence</th><th>Lift</th><th>Conviction</th></tr></thead><tbody>{rows}</tbody></table></div></div>
</div>
"""

    # ─── FOOTER + CHARTS JS ─────────────────────────────────────────

    def _footer(self) -> str:
                tl = self.a["timeline"]
                pr = self.a["products"]
                bk = self.a["basket"]
                ct = self.a["cart"]
                base = self.a.get("interactive_base", {}).get("rows", pd.DataFrame())

                # Serialize all data
                j = self._j
                cat_colors_json = json.dumps(self.c.cat_colors)
                day_order_json = json.dumps(self.c.day_order)

                return f"""
<div class="footer">Generado automáticamente · {self.c.store_name} · {self.s['date_range']}</div>
</div><!-- /container -->

<script>
function initCharts() {{
const PC = {{responsive:true, displayModeBar:false}};
const DL = {{
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    font:{{family:'DM Sans',color:'#8a92a3',size:12}},
    margin:{{t:40,r:20,b:50,l:60}},
    xaxis:{{gridcolor:'#1c2230',zerolinecolor:'#2a3040'}},
    yaxis:{{gridcolor:'#1c2230',zerolinecolor:'#2a3040'}},
}};
const CC = {cat_colors_json};
const DAY_ORDER = {day_order_json};
const BASE_ROWS = {j(base)};
const HAS_MARGIN_DATA = {str(self.a.get('profitability', {}).get('has_margin_data', False)).lower()};
const ROLLING_WINDOW = {self.c.rolling_window};
const TOP_N_PRODUCTS = {self.c.top_n_products};
const PARETO_THRESHOLD = {self.c.pareto_threshold};
const HEATMAP_METRIC_LABELS = {{
    orders: 'Órdenes',
    avg_orders_per_day: 'Promedio de órdenes por día',
    avg_items_per_cart: 'Promedio de productos por carrito',
    avg_ticket: 'Ticket promedio',
}};

function toNum(v) {{
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
}}

function mean(values) {{
    if (!values.length) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
}}

function median(values) {{
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const m = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 0) return (sorted[m - 1] + sorted[m]) / 2;
    return sorted[m];
}}

function quantile(values, q) {{
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sorted[base + 1] !== undefined) return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
    return sorted[base];
}}

function rolling(values, window) {{
    const out = [];
    for (let i = 0; i < values.length; i++) {{
        const from = Math.max(0, i - window + 1);
        const chunk = values.slice(from, i + 1);
        out.push(mean(chunk));
    }}
    return out;
}}

function getDateBounds(rows) {{
    if (!rows.length) return {{ min: '', max: '' }};
    const dates = rows.map(r => r.date_str).filter(Boolean).sort();
    return {{ min: dates[0], max: dates[dates.length - 1] }};
}}

function getSelectedDays() {{
    return Array.from(document.querySelectorAll('.weekday-check:checked')).map(el => String(el.value));
}}

function filterRows(rows, from, to, selectedDays, typeFilter) {{
    const weekendDays = new Set(['Sáb', 'Dom']);
    return rows.filter(r => {{
        const dateMatch = (!from || r.date_str >= from) && (!to || r.date_str <= to);
        const day = String(r.day || '');
        const dayMatch = selectedDays.length > 0 && selectedDays.includes(day);

        let typeMatch = true;
        if (typeFilter === 'workdays') typeMatch = !weekendDays.has(day);
        if (typeFilter === 'weekend') typeMatch = weekendDays.has(day);

        return dateMatch && dayMatch && typeMatch;
    }});
}}

function describeDayFilter(selectedDays, typeFilter) {{
    const dayLabel = selectedDays.length === 0
        ? 'ninguno'
        : selectedDays.length === DAY_ORDER.length
        ? 'todos'
        : selectedDays.join(', ');
    const typeMap = {{ all: 'todos', workdays: 'laborales', weekend: 'fin de semana' }};
    return {{
        dayLabel,
        typeLabel: typeMap[typeFilter] || 'todos',
    }};
}}

function buildDaily(rows) {{
    const byDate = new Map();
    for (const r of rows) {{
        const key = r.date_str;
        if (!byDate.has(key)) byDate.set(key, {{ revenue: 0, orders: new Set() }});
        const agg = byDate.get(key);
        agg.revenue += toNum(r.total);
        agg.orders.add(String(r.order_id));
    }}
    return [...byDate.entries()]
        .map(([date_str, agg]) => ({{ date_str, revenue: agg.revenue, orders: agg.orders.size }}))
        .sort((a, b) => a.date_str.localeCompare(b.date_str));
}}

function buildWeekly(rows) {{
    const byWeek = new Map();
    for (const r of rows) {{
        const key = String(r.year_week);
        if (!byWeek.has(key)) byWeek.set(key, {{ revenue: 0, orders: new Set() }});
        const agg = byWeek.get(key);
        agg.revenue += toNum(r.total);
        agg.orders.add(String(r.order_id));
    }}
    return [...byWeek.entries()]
        .map(([year_week, agg]) => ({{ year_week, revenue: agg.revenue, orders: agg.orders.size }}))
        .sort((a, b) => a.year_week.localeCompare(b.year_week));
}}

function buildDOW(rows) {{
    const byDay = new Map(DAY_ORDER.map(day => [day, {{ revenue: 0, orders: new Set() }}]));
    for (const r of rows) {{
        const day = String(r.day);
        if (!byDay.has(day)) byDay.set(day, {{ revenue: 0, orders: new Set() }});
        const agg = byDay.get(day);
        agg.revenue += toNum(r.total);
        agg.orders.add(String(r.order_id));
    }}
    return DAY_ORDER.map(day => ({{ day, revenue: byDay.get(day)?.revenue || 0, orders: byDay.get(day)?.orders?.size || 0 }}));
}}

function weekdayLabelFromDate(dateObj) {{
    const jsDay = dateObj.getDay();
    const map = {{0: 'Dom', 1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb'}};
    return map[jsDay] || 'Lun';
}}

function enumerateDates(from, to) {{
    if (!from || !to) return [];
    const out = [];
    let d = new Date(from + 'T00:00:00');
    const end = new Date(to + 'T00:00:00');
    while (d <= end) {{
        out.push(new Date(d));
        d.setDate(d.getDate() + 1);
    }}
    return out;
}}

function buildOrderSnapshots(rows) {{
    const byOrder = new Map();
    for (const r of rows) {{
        const oid = String(r.order_id);
        if (!byOrder.has(oid)) byOrder.set(oid, {{
            order_id: oid,
            date_str: String(r.date_str),
            day: String(r.day),
            hour: Number(r.hour),
            ticket: 0,
            products: new Set(),
        }});
        const agg = byOrder.get(oid);
        agg.ticket += toNum(r.total);
        agg.products.add(String(r.product));
    }}
    return [...byOrder.values()].map(o => ({{
        ...o,
        products_in_cart: o.products.size,
    }}));
}}

function buildHeatmap(rows, from, to, metric) {{
    const snapshots = buildOrderSnapshots(rows);
    const hours = [...new Set(snapshots.map(r => Number(r.hour)).filter(v => Number.isFinite(v)))].sort((a, b) => a - b);
    const byCell = new Map();
    for (const o of snapshots) {{
        const key = String(o.hour) + '::' + String(o.day);
        if (!byCell.has(key)) byCell.set(key, {{ orders: 0, tickets: [], items: [] }});
        const cell = byCell.get(key);
        cell.orders += 1;
        cell.tickets.push(o.ticket);
        cell.items.push(o.products_in_cart);
    }}

    const weekdayDays = new Map(DAY_ORDER.map(d => [d, 0]));
    const dates = enumerateDates(from, to);
    for (const d of dates) {{
        const label = weekdayLabelFromDate(d);
        weekdayDays.set(label, (weekdayDays.get(label) || 0) + 1);
    }}

    const z = hours.map(h => DAY_ORDER.map(d => {{
        const cell = byCell.get(String(h) + '::' + d) || {{ orders: 0, tickets: [], items: [] }};
        if (metric === 'avg_ticket') return mean(cell.tickets);
        if (metric === 'avg_items_per_cart') return mean(cell.items);
        if (metric === 'avg_orders_per_day') {{
            const denom = weekdayDays.get(d) || 1;
            return cell.orders / denom;
        }}
        return cell.orders;
    }}));

    const hoverSuffix = metric === 'avg_ticket'
        ? ' ticket promedio'
        : (metric === 'avg_items_per_cart'
            ? ' productos/carrito'
            : (metric === 'avg_orders_per_day' ? ' órdenes promedio/día' : ' órdenes'));

    return {{ hours, z, hoverSuffix }};
}}

function buildMonthlyCategory(rows) {{
    const byMonthCat = new Map();
    for (const r of rows) {{
        const key = String(r.year_month) + '::' + String(r.category);
        byMonthCat.set(key, (byMonthCat.get(key) || 0) + toNum(r.total));
    }}
    const records = [...byMonthCat.entries()].map(([k, revenue]) => {{
        const parts = k.split('::');
        return {{ month: parts[0], category: parts[1], revenue }};
    }});
    return records;
}}

function buildProducts(rows) {{
    const byProduct = new Map();
    for (const r of rows) {{
        const p = String(r.product);
        if (!byProduct.has(p)) {{
            byProduct.set(p, {{ product: p, revenue: 0, units: 0, prices: [], orders: new Set(), category: String(r.category || 'Otros') }});
        }}
        const agg = byProduct.get(p);
        agg.revenue += toNum(r.total);
        agg.units += toNum(r.quantity);
        agg.prices.push(toNum(r.unit_price));
        agg.orders.add(String(r.order_id));
    }}
    const all = [...byProduct.values()].map(v => ({{
        product: v.product,
        revenue: v.revenue,
        units: v.units,
        orders: v.orders.size,
        avg_price: mean(v.prices),
        category: v.category,
    }})).sort((a, b) => b.revenue - a.revenue);
    const totalRevenue = all.reduce((acc, x) => acc + x.revenue, 0) || 1;
    let cum = 0;
    for (const row of all) {{
        row.rev_share = (row.revenue / totalRevenue) * 100;
        cum += row.rev_share;
        row.cum_rev_pct = cum;
    }}
    return {{ all, top: all.slice(0, TOP_N_PRODUCTS) }};
}}

function buildOrderTickets(rows) {{
    const byOrder = new Map();
    for (const r of rows) {{
        const oid = String(r.order_id);
        if (!byOrder.has(oid)) byOrder.set(oid, {{ ticket: 0, day: String(r.day), hour: Number(r.hour) }});
        byOrder.get(oid).ticket += toNum(r.total);
    }}
    return [...byOrder.values()];
}}

function buildTicketSeries(rows) {{
    const orders = buildOrderTickets(rows);
    const byDay = new Map(DAY_ORDER.map(day => [day, []]));
    const byHour = new Map();
    for (const o of orders) {{
        if (!byDay.has(o.day)) byDay.set(o.day, []);
        byDay.get(o.day).push(o.ticket);
        const h = Number(o.hour);
        if (!byHour.has(h)) byHour.set(h, []);
        byHour.get(h).push(o.ticket);
    }}
    const dayTicket = DAY_ORDER.map(day => ({{
        day,
        orders: byDay.get(day)?.length || 0,
        avg_ticket: mean(byDay.get(day) || []),
    }}));
    const hourTicket = [...byHour.entries()].sort((a, b) => a[0] - b[0]).map(([hour, tickets]) => ({{
        hour,
        orders: tickets.length,
        avg_ticket: mean(tickets),
    }}));
    const baseline = mean(orders.map(o => o.ticket));
    const cutoff = quantile(hourTicket.map(h => h.orders), 0.6);
    const opp = hourTicket.filter(h => h.orders >= cutoff && h.avg_ticket < baseline).map(h => ({{
        ...h,
        gap_pct: baseline > 0 ? ((baseline - h.avg_ticket) / baseline) * 100 : 0,
    }}));
    return {{ dayTicket, hourTicket, opp }};
}}

function updateProfitability(rows) {{
    if (!HAS_MARGIN_DATA) return;
    const marginRows = rows.filter(r => r.margin_pct !== null && r.margin_pct !== undefined && Number.isFinite(Number(r.margin_pct)));
    const classGrid = document.getElementById('profitability-classification-grid');
    const marginBody = document.getElementById('profitability-margin-by-category');
    const paretoBody = document.getElementById('profitability-pareto-body');
    const catGrid = document.getElementById('profitability-category-top-grid');
    if (!classGrid || !marginBody || !paretoBody || !catGrid) return;

    if (!marginRows.length) {{
        classGrid.innerHTML = '<div class="class-badge">Sin margen en rango</div>';
        marginBody.innerHTML = '<tr><td colspan="2">Sin datos de margen en este rango.</td></tr>';
        paretoBody.innerHTML = '<tr><td colspan="6">Sin datos para Pareto de profit en este rango.</td></tr>';
        catGrid.innerHTML = '<div class="cat-top-box">Sin datos para top por categoría en este rango.</div>';
        return;
    }}

    const byProduct = new Map();
    for (const r of marginRows) {{
        const p = String(r.product);
        if (!byProduct.has(p)) byProduct.set(p, {{
            product: p,
            revenue: 0,
            units: 0,
            orders: new Set(),
            margins: [],
            category: String(r.category || 'Otros'),
        }});
        const agg = byProduct.get(p);
        agg.revenue += toNum(r.total);
        agg.units += toNum(r.quantity);
        agg.orders.add(String(r.order_id));
        agg.margins.push(toNum(r.margin_pct));
    }}

    const products = [...byProduct.values()].map(p => ({{
        ...p,
        orders_n: p.orders.size,
        avg_margin: mean(p.margins),
    }}));
    const ordersMedian = median(products.map(p => p.orders_n));
    const marginMedian = median(products.map(p => p.avg_margin));
    for (const p of products) {{
        p.profit = p.revenue * p.avg_margin / 100;
        if (p.orders_n >= ordersMedian && p.avg_margin >= marginMedian) p.cls = 'Champion';
        else if (p.orders_n >= ordersMedian) p.cls = 'Tractor';
        else if (p.avg_margin >= marginMedian) p.cls = 'Gem';
        else p.cls = 'Niche';
    }}
    products.sort((a, b) => b.profit - a.profit);

    const classCounts = {{ Champion: 0, Tractor: 0, Gem: 0, Niche: 0 }};
    for (const p of products) classCounts[p.cls] = (classCounts[p.cls] || 0) + 1;
    classGrid.innerHTML = Object.entries(classCounts).map(([k, v]) => '<div class="class-badge">' + k + ': ' + v + '</div>').join('');

    const byCategory = new Map();
    for (const r of marginRows) {{
        const c = String(r.category || 'Otros');
        if (!byCategory.has(c)) byCategory.set(c, []);
        byCategory.get(c).push(toNum(r.margin_pct));
    }}
    marginBody.innerHTML = [...byCategory.entries()]
        .map(([cat, vals]) => ({{ cat, avg: mean(vals) }}))
        .sort((a, b) => b.avg - a.avg)
        .map(x => '<tr><td>' + x.cat + '</td><td class="mono">' + x.avg.toFixed(1) + '%</td></tr>')
        .join('');

    const totalProfit = products.reduce((acc, p) => acc + p.profit, 0) || 1;
    let cum = 0;
    paretoBody.innerHTML = products.slice(0, 10).map(p => {{
        const share = (p.profit / totalProfit) * 100;
        cum += share;
        return '<tr><td>' + p.product + '</td><td class="mono">' + Math.round(p.revenue).toLocaleString() + '</td><td class="mono">' + p.avg_margin.toFixed(1) + '%</td><td class="mono">' + Math.round(p.profit).toLocaleString() + '</td><td class="mono">' + share.toFixed(1) + '%</td><td class="mono" style="color:#3b82f6">' + cum.toFixed(1) + '%</td></tr>';
    }}).join('');

    const byCatProducts = new Map();
    for (const p of products) {{
        if (!byCatProducts.has(p.category)) byCatProducts.set(p.category, []);
        byCatProducts.get(p.category).push(p);
    }}
    catGrid.innerHTML = [...byCatProducts.entries()].map(([cat, arr]) => {{
        const totalOrders = arr.reduce((acc, p) => acc + p.orders_n, 0);
        const rowsHtml = arr.slice(0, 5).map(p =>
            '<tr><td>' + p.product + '</td><td class="mono">' + p.orders_n.toLocaleString() + '</td><td class="mono">' + p.avg_margin.toFixed(1) + '%</td><td class="mono">' + Math.round(p.profit).toLocaleString() + '</td><td class="mono">' + p.cls + '</td></tr>'
        ).join('');
        return '<div class="cat-top-box"><div class="chart-box-title">Top 5 · ' + cat + ' <span class="cat-orders">(Órdenes totales: ' + totalOrders.toLocaleString() + ')</span></div><table class="data-table"><thead><tr><th>Producto</th><th>Órdenes</th><th>Margen</th><th>Profit</th><th>Clase</th></tr></thead><tbody>' + rowsHtml + '</tbody></table></div>';
    }}).join('');
}}

function renderDynamic(filteredRows, fromDate, toDate) {{
    const daily = buildDaily(filteredRows);
    const dailyRollingRev = rolling(daily.map(d => d.revenue), ROLLING_WINDOW);
    const dailyRollingOrders = rolling(daily.map(d => d.orders), ROLLING_WINDOW);

    Plotly.newPlot('chart-daily',[
        {{x:daily.map(d=>d.date_str),y:daily.map(d=>d.revenue),type:'bar',name:'Revenue diario',marker:{{color:'rgba(59,130,246,0.3)'}}}},
        {{x:daily.map(d=>d.date_str),y:dailyRollingRev,type:'scatter',mode:'lines',name:'Media {self.c.rolling_window}d',line:{{color:'#f59e0b',width:2.5}}}},
        {{x:daily.map(d=>d.date_str),y:daily.map(d=>d.orders),type:'bar',name:'Órdenes',marker:{{color:'rgba(16,185,129,0.3)'}},yaxis:'y2',visible:'legendonly'}},
        {{x:daily.map(d=>d.date_str),y:dailyRollingOrders,type:'scatter',mode:'lines',name:'Media {self.c.rolling_window}d (órdenes)',line:{{color:'#10b981',width:2,dash:'dot'}},yaxis:'y2',visible:'legendonly'}},
    ],{{...DL,title:'Revenue diario + Media Móvil',yaxis:{{...DL.yaxis,type:'linear',title:'Revenue ({self.c.currency})'}},yaxis2:{{overlaying:'y',side:'right',gridcolor:'transparent',type:'linear',title:'Órdenes'}},legend:{{x:0,y:1.12,orientation:'h',font:{{size:11}}}}}},PC);

    const weekly = buildWeekly(filteredRows);
    Plotly.newPlot('chart-weekly',[
        {{x:weekly.map(d=>d.year_week),y:weekly.map(d=>d.revenue),type:'bar',name:'Revenue',marker:{{color:'#3b82f6'}}}},
        {{x:weekly.map(d=>d.year_week),y:weekly.map(d=>d.orders),type:'scatter',mode:'lines+markers',name:'Órdenes',yaxis:'y2',line:{{color:'#f59e0b',width:2}},marker:{{size:5}}}},
    ],{{...DL,title:'Revenue y órdenes por semana',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Revenue'}},yaxis2:{{overlaying:'y',side:'right',gridcolor:'transparent',type:'linear',title:'Órdenes'}},legend:{{x:0,y:1.12,orientation:'h',font:{{size:11}}}}}},PC);

    const dow = buildDOW(filteredRows);
    Plotly.newPlot('chart-dow',[
        {{x:dow.map(d=>d.day),y:dow.map(d=>d.revenue),type:'bar',marker:{{color:'#8b5cf6'}}}},
    ],{{...DL,title:'Revenue por día de semana',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Revenue ({self.c.currency})'}}}},PC);

    const heatmapMetricSel = document.getElementById('heatmap-metric');
    const heatmapMetric = heatmapMetricSel ? heatmapMetricSel.value : 'orders';
    const hm = buildHeatmap(filteredRows, fromDate, toDate, heatmapMetric);
    Plotly.newPlot('chart-heatmap',[{{
        z:hm.z,x:DAY_ORDER,y:hm.hours.map(h=>String(h)+':00'),type:'heatmap',
        colorscale:[[0,'#0c0f14'],[0.5,'#3b82f6'],[1,'#f59e0b']],
        hovertemplate:'%{{x}} %{{y}}<br>%{{z:.2f}}' + hm.hoverSuffix + '<extra></extra>'
    }}],{{...DL,title:'Heatmap: ' + (HEATMAP_METRIC_LABELS[heatmapMetric] || 'Órdenes'),margin:{{...DL.margin,l:70}},xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'category',title:'Hora',dtick:1}}}},PC);

    const monthly = buildMonthlyCategory(filteredRows);
    const cats = [...new Set(monthly.map(d => d.category))];
    Plotly.newPlot('chart-cat-monthly',cats.map(c=>({{
        x:monthly.filter(d=>d.category===c).map(d=>d.month),
        y:monthly.filter(d=>d.category===c).map(d=>d.revenue),
        type:'bar',name:c,marker:{{color:CC[c]||'#6b7280'}}
    }})),{{...DL,title:'Revenue por categoría — Mensual',barmode:'stack',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Revenue ({self.c.currency})'}},legend:{{x:0,y:1.15,orientation:'h',font:{{size:11}}}}}},PC);

    const products = buildProducts(filteredRows);
    Plotly.newPlot('chart-top20',[{{
        y:products.top.map(d=>d.product).reverse(),
        x:products.top.map(d=>d.revenue).reverse(),
        type:'bar',orientation:'h',
        marker:{{color:products.top.map(d=>CC[d.category]||'#6b7280').reverse()}},
        text:products.top.map(d=>d.rev_share.toFixed(1)+'%').reverse(),textposition:'outside',
        hovertemplate:'%{{y}}<br>${{x:,.0f}} {self.c.currency}<extra></extra>'
    }}],{{...DL,title:'Top {self.c.top_n_products} Productos por Revenue',margin:{{...DL.margin,l:280}},xaxis:{{...DL.xaxis,type:'linear',title:'Revenue ({self.c.currency})'}}}},PC);

    Plotly.newPlot('chart-pareto',[
        {{x:products.all.map((_,i)=>i+1),y:products.all.map(d=>d.revenue),type:'bar',name:'Revenue',marker:{{color:'rgba(59,130,246,0.5)'}}}},
        {{x:products.all.map((_,i)=>i+1),y:products.all.map(d=>d.cum_rev_pct),type:'scatter',mode:'lines',name:'% Acumulado',yaxis:'y2',line:{{color:'#f59e0b',width:2}}}},
    ],{{...DL,title:'Curva de Pareto — Revenue',xaxis:{{...DL.xaxis,type:'linear',title:'# Producto (rank)'}},yaxis:{{...DL.yaxis,type:'linear',title:'Revenue'}},yaxis2:{{overlaying:'y',side:'right',gridcolor:'transparent',type:'linear',title:'% Acumulado',range:[0,105]}},shapes:[{{type:'line',x0:0,x1:products.all.length,y0:PARETO_THRESHOLD,y1:PARETO_THRESHOLD,yref:'y2',line:{{color:'#ef4444',width:1,dash:'dash'}}}}],legend:{{x:0.6,y:0.3}}}},PC);

    Plotly.newPlot('chart-scatter',[{{
        x:products.all.map(d=>d.avg_price),y:products.all.map(d=>d.units),mode:'markers',
        marker:{{size:products.all.map(d=>Math.max(8,Math.sqrt(d.revenue/50000)*5)),color:products.all.map(d=>CC[d.category]||'#6b7280'),opacity:0.8}},
        text:products.all.map(d=>d.product),
        hovertemplate:'%{{text}}<br>Precio: $%{{x:,.0f}}<br>Unidades: %{{y}}<extra></extra>'
    }}],{{...DL,title:'Precio vs Volumen',xaxis:{{...DL.xaxis,type:'linear',title:'Precio unitario ({self.c.currency})'}},yaxis:{{...DL.yaxis,type:'linear',title:'Unidades vendidas'}}}},PC);

    const ticket = buildTicketSeries(filteredRows);
    Plotly.newPlot('chart-ticket-day',[{{
            x:ticket.dayTicket.map(d=>d.day),
            y:ticket.dayTicket.map(d=>d.avg_ticket),
            type:'bar',marker:{{color:'#06b6d4'}},
            text:ticket.dayTicket.map(d=>d.orders+' órdenes'),textposition:'outside'
    }}],{{...DL,title:'Ticket Promedio por Día',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Ticket ({self.c.currency})'}}}},PC);

    const oppSet = new Set(ticket.opp.map(d => String(d.hour)));
    Plotly.newPlot('chart-ticket-hour',[{{
            x:ticket.hourTicket.map(d=>String(d.hour)+':00'),
            y:ticket.hourTicket.map(d=>d.avg_ticket),
            type:'bar',
            marker:{{color:ticket.hourTicket.map(d=>oppSet.has(String(d.hour))?'#ef4444':'#3b82f6')}},
            text:ticket.hourTicket.map(d=>d.orders),textposition:'outside',
            hovertemplate:'%{{x}}<br>Ticket: $%{{y:,.0f}}<br>Órdenes: %{{text}}<extra></extra>'
    }}],{{...DL,title:'Ticket por Hora (rojo = hora de oportunidad)',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Ticket ({self.c.currency})'}}}},PC);

    updateProfitability(filteredRows);
}}

function renderStatic() {{
    const pairs={j(bk['pairs'])};
    Plotly.newPlot('chart-pairs',[
        {{y:pairs.map(d=>d.product_a+' + '+d.product_b).reverse(),
            x:pairs.map(d=>d.count).reverse(),type:'bar',orientation:'h',
            marker:{{color:pairs.map(d=>d.lift>=1.5?'#10b981':(d.lift>=1?'#f59e0b':'#ef4444')).reverse()}},
            text:pairs.map(d=>'lift: '+d.lift.toFixed(2)).reverse(),textposition:'outside',
            textfont:{{size:11,family:'JetBrains Mono'}},
            hovertemplate:'%{{y}}<br>%{{x}} veces juntos<extra></extra>',showlegend:false}},
        {{x:[null],y:[null],type:'bar',marker:{{color:'#10b981'}},name:'Lift ≥ 1.5 (fuerte)',showlegend:true}},
        {{x:[null],y:[null],type:'bar',marker:{{color:'#f59e0b'}},name:'Lift 1.0–1.5 (moderada)',showlegend:true}},
        {{x:[null],y:[null],type:'bar',marker:{{color:'#ef4444'}},name:'Lift < 1.0 (negativa)',showlegend:true}},
    ],{{...DL,title:'Top {self.c.top_n_pairs} Pares (Market Basket)',margin:{{...DL.margin,l:380,r:100}},xaxis:{{...DL.xaxis,type:'linear',title:'Veces comprados juntos'}},legend:{{x:0.5,y:1.15,orientation:'h',font:{{size:11}}}}}},PC);

    const catP={j(bk['cat_pairs'])};
    Plotly.newPlot('chart-catpairs',[{{
        y:catP.map(d=>d.cat_a+' + '+d.cat_b).reverse(),
        x:catP.map(d=>d.count).reverse(),type:'bar',orientation:'h',
        marker:{{color:'#8b5cf6'}}
    }}],{{...DL,margin:{{...DL.margin,l:200}},xaxis:{{...DL.xaxis,type:'linear',title:'Veces juntas'}}}},PC);

    const cartD={j(ct['cart_dist'])};
    Plotly.newPlot('chart-cartdist',[{{
        x:cartD.map(d=>d.products_in_cart),y:cartD.map(d=>d.count),type:'bar',marker:{{color:'#3b82f6'}}
    }}],{{...DL,title:'Productos únicos por orden',xaxis:{{...DL.xaxis,type:'linear',title:'# productos',dtick:1}},yaxis:{{...DL.yaxis,type:'linear',title:'# órdenes'}}}},PC);

    const tickD={j(ct['ticket_dist'])};
    Plotly.newPlot('chart-ticketdist',[{{
        x:tickD.map(d=>d.bucket),y:tickD.map(d=>d.count),type:'bar',marker:{{color:'#f59e0b'}}
    }}],{{...DL,title:'Distribución del Ticket ({self.c.currency})',xaxis:{{...DL.xaxis,type:'category',title:'Rango'}},yaxis:{{...DL.yaxis,type:'linear',title:'# órdenes'}}}},PC);

    const cartE={j(ct['cart_weekly'])};
    Plotly.newPlot('chart-cartevol',[{{
        x:cartE.map(d=>d.week),y:cartE.map(d=>d.avg_items),type:'scatter',mode:'lines+markers',
        line:{{color:'#10b981',width:2.5}},marker:{{size:6}}
    }}],{{...DL,title:'Tamaño promedio de carrito por semana',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Items / orden'}}}},PC);

    const segmentStats = {j(ct.get('segment_stats', pd.DataFrame()))};
    Plotly.newPlot('chart-basket-share',[{{
        labels:segmentStats.map(d=>d.segment),
        values:segmentStats.map(d=>d.orders),
        type:'pie',
        hole:0.5,
        marker:{{colors:['#3b82f6','#10b981']}},
        textinfo:'label+percent'
    }}],{{...DL,title:'Share de canastas por unidades (1 vs 2+)',showlegend:true,margin:{{t:50,r:20,b:20,l:20}}}},PC);

    Plotly.newPlot('chart-basket-ticket',[{{
        x:segmentStats.map(d=>d.segment),
        y:segmentStats.map(d=>d.avg_ticket),
        type:'bar',
        marker:{{color:['#3b82f6','#10b981']}},
        text:segmentStats.map(d=>'$'+Math.round(d.avg_ticket).toLocaleString()),
        textposition:'outside'
    }}],{{...DL,title:'Ticket promedio por tamaño de canasta (unidades)',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Ticket ({self.c.currency})'}}}},PC);

    const multiBuckets = {j(ct.get('multi_bucket_stats', pd.DataFrame()))};
    Plotly.newPlot('chart-multi-bucket-share',[{{
        x:multiBuckets.map(d=>d.bucket),
        y:multiBuckets.map(d=>d.share_multi_pct),
        type:'bar',
        marker:{{color:'#8b5cf6'}},
        text:multiBuckets.map(d=>Number(d.share_multi_pct).toFixed(1)+'%'),
        textposition:'outside'
    }}],{{...DL,title:'Share de buckets dentro de canastas 2+ unidades',xaxis:{{...DL.xaxis,type:'category'}},yaxis:{{...DL.yaxis,type:'linear',title:'Share % en 2+'}}}},PC);

}}

function updateRangeLabels(from, to, rowsCount, selectedDays, typeFilter) {{
    const labels = [
        document.getElementById('range-label-timeline'),
        document.getElementById('range-label-products'),
        document.getElementById('range-label-profitability'),
        document.getElementById('range-label-ticket'),
    ];
    const filterDesc = describeDayFilter(selectedDays, typeFilter);
    const txt = 'Rango del gráfico: ' + from + ' a ' + to + ' · ' + rowsCount.toLocaleString() + ' filas · Días: ' + filterDesc.dayLabel + ' · Tipo: ' + filterDesc.typeLabel + '.';
    for (const el of labels) {{
        if (el) el.textContent = txt;
    }}
}}

function wireDateFilter() {{
    const fromInput = document.getElementById('date-from');
    const toInput = document.getElementById('date-to');
    const applyBtn = document.getElementById('date-apply');
    const resetBtn = document.getElementById('date-reset');
    const status = document.getElementById('date-filter-status');
    const heatmapMetricSel = document.getElementById('heatmap-metric');
    const weekdayChecks = Array.from(document.querySelectorAll('.weekday-check'));
    const weekdayCheckAll = document.getElementById('weekday-check-all');
    const dayTypeSel = document.getElementById('day-type-filter');
    const bounds = getDateBounds(BASE_ROWS);
    fromInput.value = bounds.min;
    toInput.value = bounds.max;
    fromInput.min = bounds.min;
    fromInput.max = bounds.max;
    toInput.min = bounds.min;
    toInput.max = bounds.max;

    function syncWeekdaySelectAll() {{
        if (!weekdayCheckAll) return;
        weekdayCheckAll.checked = weekdayChecks.length > 0 && weekdayChecks.every(el => el.checked);
    }}

    function applyRange() {{
        const from = fromInput.value;
        const to = toInput.value;
        const selectedDays = getSelectedDays();
        const typeFilter = dayTypeSel ? dayTypeSel.value : 'all';
        const rows = filterRows(BASE_ROWS, from, to, selectedDays, typeFilter);
        const effectiveFrom = from || bounds.min;
        const effectiveTo = to || bounds.max;
        renderDynamic(rows, effectiveFrom, effectiveTo);
        const filterDesc = describeDayFilter(selectedDays, typeFilter);
        status.textContent = 'Rango activo: ' + effectiveFrom + ' a ' + effectiveTo + ' · días: ' + filterDesc.dayLabel + ' · tipo: ' + filterDesc.typeLabel + ' · ' + rows.length.toLocaleString() + ' filas.';
        updateRangeLabels(effectiveFrom, effectiveTo, rows.length, selectedDays, typeFilter);
    }}

    applyBtn.addEventListener('click', applyRange);
    resetBtn.addEventListener('click', function() {{
        fromInput.value = bounds.min;
        toInput.value = bounds.max;
        weekdayChecks.forEach(el => {{ el.checked = true; }});
        syncWeekdaySelectAll();
        if (dayTypeSel) dayTypeSel.value = 'all';
        applyRange();
    }});
    if (weekdayCheckAll) {{
        weekdayCheckAll.addEventListener('change', function() {{
            weekdayChecks.forEach(el => {{ el.checked = weekdayCheckAll.checked; }});
        }});
    }}
    weekdayChecks.forEach(el => {{
        el.addEventListener('change', syncWeekdaySelectAll);
    }});
    if (heatmapMetricSel) {{
        heatmapMetricSel.addEventListener('change', applyRange);
    }}
    syncWeekdaySelectAll();
    applyRange();
}}

renderStatic();
wireDateFilter();
}} // end initCharts

var s=document.createElement('script');
s.src='https://cdn.plot.ly/plotly-2.27.0.min.js';
s.onload=initCharts;
s.onerror=function(){{
    var s2=document.createElement('script');
    s2.src='https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js';
    s2.onload=initCharts;
    document.head.appendChild(s2);
}};
document.head.appendChild(s);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
# 6. MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

class ReportGenerator:
    """Orquestador principal. Un solo punto de entrada."""

    def __init__(self, input_path: str, config: ReportConfig = None):
        self.config = config or ReportConfig()
        self.processor = DataProcessor(input_path, self.config)

    @staticmethod
    def build_recommendations(summary: dict[str, Any], analyses: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, str]]:
        """Construye recomendaciones ejecutables para la semana."""
        recs: list[dict[str, str]] = []

        n_pareto = analyses["products"].get("n_pareto", 0)
        total_products = analyses["products"].get("total_products", 0)
        if total_products:
            recs.append({
                "impact": "ALTO",
                "owner": "Catálogo",
                "horizon": "1 semana",
                "action": f"Blindar disponibilidad y visibilidad de los {n_pareto} SKUs que concentran el 80% del revenue.",
            })

        opp_hours = analyses.get("ticket", {}).get("opportunity_hours")
        if isinstance(opp_hours, pd.DataFrame) and not opp_hours.empty:
            top_opp = int(opp_hours.iloc[0]["hour"])
            recs.append({
                "impact": "MEDIO",
                "owner": "Growth",
                "horizon": "2 semanas",
                "action": f"Ejecutar test de upsell en la franja {top_opp}:00 (alto tráfico con ticket por debajo de la media).",
            })

        high_lift = analyses.get("basket", {}).get("high_lift_pairs", [])
        if high_lift:
            pair = high_lift[0]
            recs.append({
                "impact": "ALTO",
                "owner": "Growth + Comercial",
                "horizon": "2 semanas",
                "action": f"Probar bundle guiado para {pair['product_a']} + {pair['product_b']} (lift {pair['lift']}).",
            })

        launch_ready = analyses.get("bundles", {}).get("launch_ready", [])
        if launch_ready:
            top_bundle = launch_ready[0]
            recs.append({
                "impact": "ALTO",
                "owner": "Growth + Pricing",
                "horizon": "1-2 semanas",
                "action": (
                    f"Activar bundle {top_bundle['anchor']} + {top_bundle['target']} "
                    f"(confidence {top_bundle['confidence']:.1%}, lift {top_bundle['lift']:.2f})."
                ),
            })

        if quality.get("risk_level") == "high":
            recs.append({
                "impact": "ALTO",
                "owner": "BI",
                "horizon": "72 horas",
                "action": "Corregir cobertura temporal y calidad de datos antes de tomar decisiones de mediano plazo.",
            })

        # Keep concise top recommendations.
        return recs[:3]

    def _compute(self) -> dict[str, Any]:
        """Ejecuta todo el análisis y retorna las piezas crudas (con DataFrames).

        Este es el seam entre el motor de análisis y cualquier renderer
        (HTML local o payload JSON para la app web).
        """
        summary = self.processor.summary()
        analyses = AnalysisModules(self.processor.df, self.config).run_all()
        quality = self.processor.data_quality_metrics()
        insights = InsightEngine.generate(summary, analyses, self.config)
        recommendations = self.build_recommendations(summary, analyses, quality)
        return {
            "summary": summary,
            "analyses": analyses,
            "quality": quality,
            "insights": insights,
            "recommendations": recommendations,
        }

    def build_payload(self, computed: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Retorna el reporte completo como estructura JSON pura (sin HTML).

        Es el contrato con la app web (ver docs/SAAS-PLAN.md). Cambios
        incompatibles requieren incrementar PAYLOAD_SCHEMA_VERSION.
        """
        pieces = computed if computed is not None else self._compute()
        return {
            "meta": {
                "schema_version": PAYLOAD_SCHEMA_VERSION,
                "report_type": "sales_report",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "store_name": self.config.store_name,
                "currency": self.config.currency,
                "config": to_jsonable(asdict(self.config)),
            },
            "summary": to_jsonable(pieces["summary"]),
            "quality": to_jsonable(pieces["quality"]),
            "analyses": to_jsonable(pieces["analyses"]),
            "insights": to_jsonable(pieces["insights"]),
            "recommendations": to_jsonable(pieces["recommendations"]),
        }

    def write_payload(self, payload_path: str, computed: Optional[dict[str, Any]] = None) -> str:
        """Genera y escribe el payload JSON. Retorna la ruta escrita."""
        payload = self.build_payload(computed)
        out = Path(payload_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        logger.info("Payload JSON generado: %s", payload_path)
        return str(out)

    def run(self, output_path: str, payload_path: Optional[str] = None, fmt: str = "html") -> str:
        """Genera el reporte y lo guarda. fmt: "html" (default), "json" o "both"."""
        if fmt not in ("html", "json", "both"):
            raise ValueError(f"Formato no soportado: {fmt!r} (usa html, json o both)")

        pieces = self._compute()
        summary = pieces["summary"]
        insights = pieces["insights"]

        if fmt in ("json", "both"):
            resolved_payload = payload_path or str(Path(output_path).with_suffix(".payload.json"))
            self.write_payload(resolved_payload, pieces)

        if fmt in ("html", "both"):
            html = ReportRenderer(
                summary, pieces["analyses"], insights, pieces["quality"],
                pieces["recommendations"], self.config,
            ).render()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        # 6. Export discarded rows log (junto al artefacto generado)
        discarded_log_path: Optional[str] = None
        discarded_df = self.processor.discarded_df
        if discarded_df is not None and not discarded_df.empty:
            out_p = Path(output_path)
            discarded_log_path = str(out_p.parent / f"{out_p.stem}_filas_descartadas.csv")
            discarded_df.to_csv(discarded_log_path, index=False, encoding="utf-8-sig")

        # Print summary
        if fmt == "json":
            print(f"Payload generado: {payload_path or Path(output_path).with_suffix('.payload.json')}")
        else:
            print(f"Reporte generado: {output_path}")
        print(f"  Revenue: ${summary['total_revenue']:,} {self.config.currency}")
        print(f"  Órdenes: {summary['total_orders']:,}")
        print(f"  Productos: {summary['unique_products']}")
        print(f"  Insights: {len(insights)}")
        print(f"  Período: {summary['date_range']}")
        if self.processor.quality_report is not None:
            qr = self.processor.quality_report
            print(
                f"  Calidad: {qr.final_rows:,}/{qr.initial_rows:,} filas válidas "
                f"({qr.dropped_pct:.2f}% descartadas)"
            )
        if discarded_log_path:
            print(f"  Log descartadas: {discarded_log_path} ({len(discarded_df)} filas)")

        return output_path


# ═══════════════════════════════════════════════════════════════════════
# 7. CLI
# ═══════════════════════════════════════════════════════════════════════

_SAMPLE_CSV_NAMES: frozenset[str] = frozenset({"sales_carts_sample.csv"})


def _discover_csv_in(base: Path) -> Optional[str]:
    """Busca el CSV más reciente en base/input_data/ o archivos de prueba en base/."""
    input_data_dir = base / "input_data"
    if input_data_dir.is_dir():
        input_data_csvs = sorted(
            (p for p in input_data_dir.glob("*.csv") if p.name not in _SAMPLE_CSV_NAMES),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if input_data_csvs:
            return str(input_data_csvs[0])

    fixtures_dir = base / "fixtures"
    for filename in ("test_data_with_margins_normalized.csv", "test_data_with_margins.csv"):
        for parent in (fixtures_dir, base):
            candidate = parent / filename
            if candidate.is_file():
                return str(candidate)

    csv_files = sorted(base.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if csv_files:
        return str(csv_files[0])
    return None


def discover_default_input_csv() -> Optional[str]:
    """Encuentra un CSV usable sin --input (funciona desde cualquier cwd)."""
    found = _discover_csv_in(PROJECT_DIR)
    if found:
        return found
    cwd = Path.cwd()
    if cwd != PROJECT_DIR:
        return _discover_csv_in(cwd)
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store Sales Report Generator")
    parser.add_argument("--input", "--csv", "-i", help="Path to cart CSV file")
    parser.add_argument("--output", "-o", default="report.html", help="Output HTML path")
    parser.add_argument("--store", "-s", default=None, help="Store name for header (overrides --config)")
    parser.add_argument(
        "--format", "-f", default="html", choices=["html", "json", "both"],
        help="Output: html (default), json (payload para la app web) o both",
    )
    parser.add_argument("--payload-out", default=None, help="Ruta del payload JSON (default: <output>.payload.json)")
    parser.add_argument("--config", "-c", default=None, help="JSON de configuración de tenant (ReportConfig.from_dict)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logs")
    args = parser.parse_args()

    configure_logging(args.verbose)

    input_path = args.input or discover_default_input_csv()
    if not input_path:
        parser.error(
            "No se encontró un CSV automáticamente. "
            f"Usa --input <archivo.csv> o coloca CSVs en {PROJECT_DIR / 'input_data'}."
        )

    input_path = str(resolve_project_path(input_path))
    output_path = str(resolve_project_path(args.output))
    payload_path = str(resolve_project_path(args.payload_out)) if args.payload_out else None

    if not args.input:
        logger.info("Sin --input explícito. CSV detectado automáticamente: %s", input_path)

    if args.config:
        config_path = resolve_project_path(args.config)
        with open(config_path, "r", encoding="utf-8") as f:
            config = ReportConfig.from_dict(json.load(f))
        logger.info("Configuración de tenant cargada: %s", config_path)
    else:
        config = ReportConfig()
    if args.store:
        config.store_name = args.store

    gen = ReportGenerator(input_path, config)
    gen.run(output_path, payload_path=payload_path, fmt=args.format)


# ═══════════════════════════════════════════════════════════════════════
# EXTENSION POINTS — Guía para agregar funcionalidad
# ═══════════════════════════════════════════════════════════════════════
#
# 1. NUEVO MÓDULO DE ANÁLISIS:
#    - Agregar método en AnalysisModules (e.g., def search_analysis(self))
#    - Registrarlo en run_all() con una key nueva
#    - Agregar sección en ReportRenderer
#
# 2. NUEVO INSIGHT:
#    - Crear función decorada con @insight_rule
#    - Firma: (summary, analyses, config) -> Optional[Insight]
#    - Se registra automáticamente
#
# 3. NUEVA FUENTE DE DATOS:
#    - Extender DataProcessor para aceptar múltiples archivos
#    - O crear un segundo processor y pasar ambos a AnalysisModules
#
# 4. PERSONALIZACIÓN DE DISEÑO:
#    - Modificar CSS variables en :root dentro de _head()
#    - O hacer ReportConfig extensible con theme settings
#
# 5. DATOS DE USUARIO (cuando estén disponibles):
#    - Nuevo módulo: cohort_analysis() en AnalysisModules
#    - Nuevos insights: @insight_rule def insight_cohort_retention(...)
#    - Nueva sección en renderer: _cohorts_section()
#
# 6. DATOS DE SEARCH (cuando estén disponibles):
#    - Nuevo módulo: search_gap_analysis() en AnalysisModules
#    - Nuevos insights: catalog gap, keyword coverage
#    - Connect con discovery_patterns_brainstorm.docx framework
# ═══════════════════════════════════════════════════════════════════════
