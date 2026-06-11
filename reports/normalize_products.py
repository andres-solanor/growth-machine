#!/usr/bin/env python3
"""
normalize_products.py

Consolidates raw POS export files and produces a normalized sales CSV
ready for the report generators.

Usage:
    python reports/normalize_products.py

Workflow:
    1. Reads all raw POS exports from reports/input_data/ that match
       "Ventas detalladas de LA PANETTERIA MALL SURAMERICA*" (.xls/.xlsx/.csv).
       Also reads the legacy consolidated CSV if present.
    2. Concatenates and deduplicates by (Fecha, Código venta, Producto, Individual).
    3. Applies product_map.csv for enrichment:
         - Unambiguous products: match by system name; supports temporal updates
           (multiple rows with different fecha_desde).
         - Price-split products (precio_post present): post-cutoff rows matched by
           (sistema, precio_post); pre-cutoff rows split proportionally using the
           post-cutoff unit share per variant.
    4. Derives time features: Month, Week Day, Hour.
    5. Writes reports/input_data/normalized_sales.csv.

product_map.csv columns:
    sistema      — exact Producto value from POS export
    precio_post  — unit price (Individual) that identifies this variant after
                   fecha_desde; leave empty for unambiguous products
    fecha_desde  — ISO date from which this row is valid; leave empty for
                   products that have never changed
    nombre       — canonical product name   →  Nombre Corregido
    categoria    — category                 →  Categoria Real
    subcategoria — subcategory              →  Sub Categoria Real
    margen_pct   — margin %                 →  margin_pct
"""

import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent
INPUT_DIR = BASE / "input_data"
PRODUCT_MAP_FILE = INPUT_DIR / "product_map.csv"
OUTPUT_FILE = INPUT_DIR / "normalized_sales.csv"

RAW_PREFIX = "Ventas detalladas de LA PANETTERIA MALL SURAMERICA"
LEGACY_CSV_NAME = "Análisis Ventas Panetteria - Carritos.csv"
EXCLUDED_FILES = {"sales_carts_sample.csv", "product_map.csv", "normalized_sales.csv"}

DEDUP_KEY = ["Fecha", "Código venta", "Producto", "Individual"]
POS_COLS = ["Fecha", "Hora", "Código venta", "Producto", "Cantidad", "Individual", "Total"]
ENRICHMENT_COLS = ["Nombre Corregido", "Categoria Real", "Sub Categoria Real",
                   "Month", "Week Day", "Hour", "margin_pct"]

DAY_ES = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}

OUTPUT_COL_ORDER = POS_COLS + ENRICHMENT_COLS


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------

_SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"


def _read_spreadsheetml(path: Path) -> pd.DataFrame:
    """Parse a SpreadsheetML XML file (.xls exported from some POS systems)."""
    tree = ET.parse(path)
    root = tree.getroot()

    worksheet = root.find(f".//{{{_SS_NS}}}Worksheet")
    if worksheet is None:
        raise ValueError(f"No Worksheet element found in {path.name}")
    table = worksheet.find(f"{{{_SS_NS}}}Table")
    if table is None:
        raise ValueError(f"No Table element found in {path.name}")

    data = []
    for row_elem in table.findall(f"{{{_SS_NS}}}Row"):
        cells = row_elem.findall(f"{{{_SS_NS}}}Cell")
        row_vals: dict[int, str] = {}
        col_idx = 0
        for cell in cells:
            # ss:Index overrides the implicit column position (1-based)
            idx_attr = cell.get(f"{{{_SS_NS}}}Index")
            if idx_attr is not None:
                col_idx = int(idx_attr) - 1
            data_elem = cell.find(f"{{{_SS_NS}}}Data")
            row_vals[col_idx] = data_elem.text if data_elem is not None else None
            col_idx += 1

        max_idx = max(row_vals.keys(), default=-1)
        data.append([row_vals.get(i) for i in range(max_idx + 1)])

    if not data:
        return pd.DataFrame()

    headers = data[0]
    rows = data[1:]
    n_cols = len(headers)
    rows = [r + [None] * (n_cols - len(r)) for r in rows]
    return pd.DataFrame(rows, columns=headers)


def read_raw_file(path: Path) -> pd.DataFrame | None:
    """Lee un export POS (.csv, .xls SpreadsheetML/binario, .xlsx) SIN validar
    columnas: el worker SaaS renombra columnas de tenants con otros encabezados
    antes de validar. _read_file() conserva la validación de siempre."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(path, dtype=str)
        if suffix in (".xls", ".xlsx"):
            # Check if it's SpreadsheetML XML (common POS export trick)
            with open(path, "rb") as f:
                magic = f.read(6)
            if magic.startswith(b"<?xml"):
                return _read_spreadsheetml(path)
            engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
            return pd.read_excel(path, dtype=str, engine=engine)
        warnings.warn(f"Unsupported file type: {path.name} — skipped")
        return None
    except Exception as exc:
        warnings.warn(f"Could not read {path.name}: {exc} — skipped")
        return None


def _read_file(path: Path) -> pd.DataFrame | None:
    """Read a POS export file (SpreadsheetML .xls, .xlsx, or .csv)."""
    df = read_raw_file(path)
    if df is None:
        return None

    # Drop enrichment columns if present (legacy consolidated CSV)
    for col in ENRICHMENT_COLS:
        if col in df.columns:
            df = df.drop(columns=[col])

    missing = [c for c in POS_COLS if c not in df.columns]
    if missing:
        warnings.warn(f"{path.name}: missing columns {missing} — skipped")
        return None

    return df[POS_COLS]


# ---------------------------------------------------------------------------
# Step 1: discover + consolidate raw exports
# ---------------------------------------------------------------------------

def consolidate(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatena exports crudos, deduplica y normaliza tipos. Función pura."""
    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=DEDUP_KEY)
    removed = before - len(combined)
    if removed:
        print(f"  Deduplication removed {removed:,} overlapping rows.")

    combined["Fecha"] = pd.to_datetime(combined["Fecha"], errors="coerce")
    combined["Cantidad"] = pd.to_numeric(combined["Cantidad"], errors="coerce")
    combined["Individual"] = pd.to_numeric(combined["Individual"], errors="coerce")
    combined["Total"] = pd.to_numeric(combined["Total"], errors="coerce")
    combined = combined.sort_values("Fecha").reset_index(drop=True)

    date_range = f"{combined['Fecha'].min().date()} – {combined['Fecha'].max().date()}"
    print(f"  {len(combined):,} rows total ({date_range})")
    return combined


def load_raw_exports(
    input_dir: Path = INPUT_DIR,
    raw_prefix: str = RAW_PREFIX,
    legacy_csv_name: str = LEGACY_CSV_NAME,
) -> pd.DataFrame:
    raw_exports = sorted(
        [p for p in input_dir.glob(f"{raw_prefix}*") if p.suffix.lower() in (".xls", ".xlsx", ".csv")],
        key=lambda p: p.stat().st_mtime,
    )
    legacy = input_dir / legacy_csv_name
    legacy_paths = [legacy] if legacy.exists() else []

    all_paths = raw_exports + legacy_paths
    if not all_paths:
        sys.exit(
            f"[error] No POS exports found in {input_dir}\n"
            f"        Expected files starting with: '{raw_prefix}'"
        )

    print(f"Loading {len(all_paths)} source file(s):")
    frames = []
    for p in all_paths:
        df = _read_file(p)
        if df is not None:
            print(f"  {p.name}  ({len(df):,} rows)")
            frames.append(df)

    if not frames:
        sys.exit("[error] No valid exports could be loaded.")

    return consolidate(frames)


# ---------------------------------------------------------------------------
# Step 2: load and validate product map
# ---------------------------------------------------------------------------

def prepare_product_map(pm: pd.DataFrame) -> pd.DataFrame:
    """Valida y normaliza tipos de un product map ya cargado (CSV, JSON o DB).

    Lanza ValueError si faltan columnas requeridas. Función pura e idempotente.
    """
    required = {"sistema", "nombre", "categoria", "subcategoria", "margen_pct"}
    missing = required - set(pm.columns)
    if missing:
        raise ValueError(f"product_map is missing columns: {sorted(missing)}")

    pm = pm.copy()
    pm["precio_post"] = pd.to_numeric(pm.get("precio_post", pd.Series(dtype=str)), errors="coerce")
    pm["fecha_desde"] = pd.to_datetime(pm.get("fecha_desde", pd.Series(dtype=str)), errors="coerce")
    pm["margen_pct"] = pd.to_numeric(pm["margen_pct"], errors="coerce")
    return pm


def load_product_map(product_map_file: Path = PRODUCT_MAP_FILE) -> pd.DataFrame:
    if not product_map_file.exists():
        sys.exit(
            f"[error] {product_map_file} not found.\n"
            f"        Create it following the sample in reports/input_data/product_map.csv."
        )

    try:
        return prepare_product_map(pd.read_csv(product_map_file, dtype=str))
    except ValueError as exc:
        sys.exit(f"[error] {product_map_file.name}: {exc}")


# ---------------------------------------------------------------------------
# Step 3: compute post-cutoff unit split ratios
# ---------------------------------------------------------------------------

def compute_split_ratios(sales: pd.DataFrame, split_map: pd.DataFrame) -> dict:
    """Returns {sistema: {precio_post: unit_ratio}} using post-cutoff data."""
    ratios: dict = {}
    cutoffs = split_map.groupby("sistema")["fecha_desde"].min()

    for sistema, cutoff in cutoffs.items():
        variants = split_map[split_map["sistema"] == sistema]["precio_post"].dropna().unique()
        effective = cutoff if not pd.isna(cutoff) else pd.Timestamp.min
        post = sales[(sales["Producto"] == sistema) & (sales["Fecha"] >= effective)]
        total_units = post["Cantidad"].sum()

        if total_units == 0:
            warnings.warn(
                f"'{sistema}': no post-cutoff sales found to compute split ratios. "
                f"Using equal split across {len(variants)} variant(s)."
            )
            ratios[sistema] = {p: 1.0 / len(variants) for p in variants}
            continue

        raw: dict = {}
        for precio in variants:
            units = post[post["Individual"] == precio]["Cantidad"].sum()
            raw[precio] = float(units)

        total_r = sum(raw.values())
        ratios[sistema] = {p: v / total_r for p, v in raw.items()} if total_r > 0 else {p: 1.0 / len(variants) for p in variants}

    return ratios


# ---------------------------------------------------------------------------
# Step 4: enrichment
# ---------------------------------------------------------------------------

def _best_row(candidates: pd.DataFrame) -> pd.Series:
    """Return the candidate with the most recent fecha_desde (nulls treated as oldest)."""
    dated = candidates.dropna(subset=["fecha_desde"])
    if not dated.empty:
        return dated.sort_values("fecha_desde").iloc[-1]
    return candidates.iloc[0]


def _apply(row_dict: dict, map_row: pd.Series) -> dict:
    row_dict["Nombre Corregido"] = map_row["nombre"]
    row_dict["Categoria Real"] = map_row["categoria"]
    row_dict["Sub Categoria Real"] = map_row["subcategoria"]
    row_dict["margin_pct"] = map_row["margen_pct"]
    return row_dict


def enrich(sales: pd.DataFrame, pm: pd.DataFrame) -> pd.DataFrame:
    # Classify sistemas:
    #   disambiguation — precio_post is set AND multiple distinct nombres exist
    #                    (same system name, different products → split by price)
    #   tracking       — precio_post is set BUT all rows share the same nombre
    #                    (same product, price changed over time → no split)
    #   simple         — no precio_post at all
    #
    # For tracking/simple: try exact price match first, then fall back to
    # the most recent temporally-valid row regardless of price.
    # For disambiguation: post-cutoff rows get exact price match; pre-cutoff
    # rows (price not in map) are split proportionally across all variants.

    with_price = pm[pm["precio_post"].notna()]
    distinct_nombres = with_price.groupby("sistema")["nombre"].nunique()
    disambiguation_sistemas = set(distinct_nombres[distinct_nombres > 1].index)

    split_map = pm[pm["sistema"].isin(disambiguation_sistemas)].copy()
    simple_map = pm[~pm["sistema"].isin(disambiguation_sistemas)].copy()

    cutoffs = (split_map[split_map["precio_post"].notna()]
               .groupby("sistema")["fecha_desde"].min().to_dict())
    split_ratios = compute_split_ratios(sales, split_map[split_map["precio_post"].notna()])

    is_split = sales["Producto"].isin(disambiguation_sistemas)
    simple_sales = sales[~is_split]
    split_sales = sales[is_split]

    output: list[dict] = []
    unmatched: list[str] = []

    # --- Simple + tracking products ---
    for sistema, group in simple_sales.groupby("Producto"):
        candidates_all = simple_map[simple_map["sistema"] == sistema]

        for _, row in group.iterrows():
            valid = candidates_all[
                candidates_all["fecha_desde"].isna() | (candidates_all["fecha_desde"] <= row["Fecha"])
            ]
            r = row.to_dict()
            if valid.empty:
                unmatched.append(str(sistema))
                r.update({"Nombre Corregido": sistema, "Categoria Real": None,
                           "Sub Categoria Real": None, "margin_pct": None})
                output.append(r)
                continue

            # Try exact price match first (covers price-tracking products)
            price_match = valid[valid["precio_post"] == row["Individual"]]
            if not price_match.empty:
                r = _apply(r, _best_row(price_match))
            else:
                # Fall back: prefer price-agnostic rows, then any temporally valid row
                agnostic = valid[valid["precio_post"].isna()]
                r = _apply(r, _best_row(agnostic if not agnostic.empty else valid))
            output.append(r)

    # --- Price-disambiguation products ---
    for sistema, group in split_sales.groupby("Producto"):
        cutoff = cutoffs.get(sistema, pd.NaT)
        effective_cutoff = cutoff if not pd.isna(cutoff) else pd.Timestamp.min
        ratios = split_ratios.get(sistema, {})
        variants = split_map[(split_map["sistema"] == sistema) & split_map["precio_post"].notna()]

        post = group[group["Fecha"] >= effective_cutoff]
        pre = group[group["Fecha"] < effective_cutoff]

        # Known price → exact match
        for _, row in post.iterrows():
            valid = variants[
                (variants["precio_post"] == row["Individual"]) &
                (variants["fecha_desde"].isna() | (variants["fecha_desde"] <= row["Fecha"]))
            ]
            r = row.to_dict()
            if valid.empty:
                unmatched.append(f"{sistema} @ {row['Individual']}")
                r.update({"Nombre Corregido": f"{sistema} (precio {row['Individual']})",
                           "Categoria Real": None, "Sub Categoria Real": None, "margin_pct": None})
            else:
                r = _apply(r, _best_row(valid))
            output.append(r)

        # Unknown price (pre-cutoff or unrecognised price) → proportional split
        for _, row in pre.iterrows():
            for _, variant in variants.iterrows():
                ratio = ratios.get(variant["precio_post"], 1.0 / len(variants))
                r = row.to_dict()
                r["Cantidad"] = row["Cantidad"] * ratio
                r["Total"] = row["Total"] * ratio
                r = _apply(r, variant)
                output.append(r)

    if unmatched:
        unique_unmatched = sorted(set(unmatched))
        warnings.warn(
            f"{len(unmatched)} row(s) had no product_map match "
            f"(add them to product_map.csv): {unique_unmatched}"
        )

    return pd.DataFrame(output)


# ---------------------------------------------------------------------------
# Step 5: derive time features
# ---------------------------------------------------------------------------

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["Month"] = df["Fecha"].dt.strftime("%b")
    df["Week Day"] = df["Fecha"].dt.dayofweek.map(DAY_ES)
    hora = pd.to_datetime(
        df["Hora"] if "Hora" in df.columns else pd.Series(dtype=str),
        format="%I:%M:%S %p", errors="coerce"
    )
    df["Hour"] = hora.dt.hour
    return df


# ---------------------------------------------------------------------------
# Pure pipeline API (used by worker/run_job.py and by main() below)
# ---------------------------------------------------------------------------

def reorder_columns(enriched: pd.DataFrame) -> pd.DataFrame:
    """Columnas estándar primero, columnas extra del POS al final."""
    extras = [c for c in enriched.columns if c not in OUTPUT_COL_ORDER]
    final_cols = [c for c in OUTPUT_COL_ORDER if c in enriched.columns] + extras
    return enriched[final_cols]


def normalize(
    sales: pd.DataFrame | list[pd.DataFrame],
    product_map: pd.DataFrame,
) -> pd.DataFrame:
    """Pipeline completo sin I/O: consolida (si recibe frames), enriquece con el
    product map y deriva features de tiempo. `Fecha` queda como datetime —
    el caller decide el formato de salida.
    """
    if isinstance(sales, list):
        sales = consolidate(sales)
    pm = prepare_product_map(product_map)
    enriched = enrich(sales, pm)
    add_time_features(enriched)
    return reorder_columns(enriched)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== normalize_products.py ===\n")

    sales = load_raw_exports()
    pm = load_product_map()

    print(f"\nEnriching {len(sales):,} rows using {len(pm)} mapping rule(s)...")
    enriched = normalize(sales, pm)

    enriched["Fecha"] = enriched["Fecha"].dt.strftime("%Y-%m-%d")
    enriched.to_csv(OUTPUT_FILE, index=False)

    base_rows = sales[~sales["Producto"].isin(
        pm[pm["precio_post"].notna()]["sistema"].unique()
    )].shape[0] if len(pm) else len(sales)
    split_added = len(enriched) - len(sales)

    print(f"\nDone: {len(enriched):,} rows written to {OUTPUT_FILE.name}")
    if split_added > 0:
        print(f"  (includes {split_added:,} rows from pre-cutoff proportional splits)")


if __name__ == "__main__":
    main()
