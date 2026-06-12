"use client";

import { useMemo, useState } from "react";
import { COMMON_CATEGORIES, suggestCategory } from "@/lib/category-suggest";
import { fmtMoney } from "@/lib/format";
import { guardarMapaProductos } from "./actions";

export type EditorProduct = {
  sistema: string;
  categoria: string; // "" = sin clasificar (se guarda como "Otros")
  margenPct: number | null;
  revenue: number;
  revShare: number;
  orders: number;
};

type Props = {
  products: EditorProduct[];
  nPareto: number;
  categoryMargins: Record<string, number>;
  currency: string;
  tier: string;
  guardado: boolean;
};

export function ProductMapEditor({
  products,
  nPareto,
  categoryMargins,
  currency,
  tier,
  guardado,
}: Props) {
  const [rows, setRows] = useState(() => products.map((p) => ({ ...p })));
  const [catMargins, setCatMargins] =
    useState<Record<string, number>>(categoryMargins);
  const [dirty, setDirty] = useState(false);

  const suggestions = useMemo(
    () => new Map(products.map((p) => [p.sistema, suggestCategory(p.sistema)])),
    [products],
  );

  const setRow = (i: number, patch: Partial<EditorProduct>) => {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
    setDirty(true);
  };

  const classified = rows.filter((r) => {
    const c = r.categoria.trim();
    return c !== "" && c !== "Otros";
  }).length;

  // Categorías en uso (las asignadas + "Otros" si quedó algún producto ahí):
  // son las filas del panel de márgenes por categoría.
  const usedCategories = useMemo(() => {
    const set = new Set<string>();
    let hasOtros = false;
    for (const r of rows) {
      const c = r.categoria.trim();
      if (c && c !== "Otros") set.add(c);
      else hasOtros = true;
    }
    const sorted = [...set].sort((a, b) => a.localeCompare(b, "es"));
    return hasOtros ? [...sorted, "Otros"] : sorted;
  }, [rows]);

  const datalistCats = useMemo(() => {
    const set = new Set<string>(COMMON_CATEGORIES);
    for (const c of usedCategories) set.add(c);
    return [...set].sort((a, b) => a.localeCompare(b, "es"));
  }, [usedCategories]);

  const pendingSuggestions = rows.filter(
    (r) => !r.categoria.trim() && suggestions.get(r.sistema),
  ).length;

  const applyAllSuggestions = () => {
    setRows((prev) =>
      prev.map((r) =>
        r.categoria.trim()
          ? r
          : { ...r, categoria: suggestions.get(r.sistema) ?? r.categoria },
      ),
    );
    setDirty(true);
  };

  const setCatMargin = (cat: string, value: number | null) => {
    setCatMargins((prev) => {
      const next = { ...prev };
      if (value === null) delete next[cat];
      else next[cat] = value;
      return next;
    });
    setDirty(true);
  };

  // Solo se envían márgenes de categorías en uso (las huérfanas se limpian).
  const data = JSON.stringify({
    products: rows.map((r) => ({
      sistema: r.sistema,
      categoria: r.categoria.trim(),
      margenPct: r.margenPct,
    })),
    categoryMargins: Object.fromEntries(
      Object.entries(catMargins).filter(([cat]) => usedCategories.includes(cat)),
    ),
  });

  const parseMargin = (raw: string): number | null => {
    if (raw.trim() === "") return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return Math.min(99, Math.max(0, n));
  };

  return (
    <form action={guardarMapaProductos}>
      <input type="hidden" name="data" value={data} />
      <datalist id="categorias">
        {datalistCats.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      {/* ── Resumen + acciones rápidas ─────────────────────────────── */}
      <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
        <span className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1 text-zinc-300">
          {classified} de {rows.length} clasificados
        </span>
        {nPareto > 0 && nPareto < rows.length && (
          <span className="rounded-full border border-amber-800 bg-amber-950/60 px-3 py-1 text-amber-300">
            Los primeros {nPareto} productos concentran ~80% de tus ventas:
            empieza por ellos
          </span>
        )}
        {pendingSuggestions > 0 && (
          <button
            type="button"
            onClick={applyAllSuggestions}
            className="rounded-full border border-emerald-700 bg-emerald-950 px-3 py-1 font-medium text-emerald-300 hover:bg-emerald-900"
          >
            ✨ Aplicar {pendingSuggestions} sugerencia
            {pendingSuggestions === 1 ? "" : "s"} de categoría
          </button>
        )}
        {guardado && !dirty && (
          <span className="text-xs font-medium text-emerald-400">
            ✓ Guardado — se aplica en tu próximo análisis
          </span>
        )}
      </div>

      {/* ── Lista de productos ─────────────────────────────────────── */}
      <ul className="mt-4 divide-y divide-zinc-800 rounded-2xl border border-zinc-800 bg-zinc-900">
        {rows.map((r, i) => {
          const suggestion = suggestions.get(r.sistema);
          const catMargin = catMargins[r.categoria.trim() || "Otros"];
          return (
            <li key={r.sistema}>
              {i === nPareto && nPareto > 0 && (
                <p className="border-b border-zinc-800 bg-zinc-950/60 px-4 py-1.5 text-center text-xs text-zinc-500">
                  ── el resto (~20% de tus ventas) ──
                </p>
              )}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
                <span className="w-7 shrink-0 text-right text-xs text-zinc-600">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1 basis-52">
                  <p className="truncate text-sm text-zinc-200">{r.sistema}</p>
                  <p className="text-xs text-zinc-500">
                    {r.revenue > 0
                      ? `${fmtMoney(r.revenue, currency)} · ${r.revShare.toFixed(1)}% de tus ventas`
                      : "sin ventas en el último análisis"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <input
                    type="text"
                    list="categorias"
                    value={r.categoria}
                    onChange={(e) => setRow(i, { categoria: e.target.value })}
                    placeholder="Otros"
                    className="w-40 rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs placeholder:text-zinc-600"
                  />
                  {suggestion && !r.categoria.trim() && (
                    <button
                      type="button"
                      onClick={() => setRow(i, { categoria: suggestion })}
                      title="Aplicar sugerencia"
                      className="rounded-lg border border-emerald-800 bg-emerald-950/60 px-2 py-1.5 text-xs text-emerald-300 hover:bg-emerald-900"
                    >
                      ¿{suggestion}?
                    </button>
                  )}
                  <input
                    type="number"
                    min={0}
                    max={99}
                    step={1}
                    inputMode="numeric"
                    value={r.margenPct ?? ""}
                    onChange={(e) =>
                      setRow(i, { margenPct: parseMargin(e.target.value) })
                    }
                    placeholder={catMargin != null ? `≈${catMargin}` : "—"}
                    title="Margen % de este producto (opcional)"
                    className="w-16 rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-right text-xs placeholder:text-zinc-600"
                  />
                  <span className="text-xs text-zinc-500">%</span>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {/* ── Márgenes por categoría ─────────────────────────────────── */}
      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold">
          Margen estimado por categoría{" "}
          <span className="text-sm font-normal text-zinc-500">(opcional)</span>
        </h2>
        <p className="mt-1 text-sm text-zinc-400">
          Si no conoces el margen de cada producto, un estimado por categoría
          alcanza para empezar: se usa solo donde el producto no tiene margen
          propio y el reporte lo marca como{" "}
          <em className="text-zinc-300">margen estimado</em>.
        </p>
        {tier !== "premium" && (
          <p className="mt-2 text-xs text-amber-400">
            El análisis de rentabilidad que usa estos márgenes hace parte del
            plan Premium.
          </p>
        )}
        {usedCategories.length === 0 ? (
          <p className="mt-4 text-sm text-zinc-500">
            Clasifica algunos productos arriba y sus categorías aparecerán aquí.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {usedCategories.map((cat) => {
              const v = catMargins[cat];
              return (
                <li key={cat} className="flex items-center gap-3">
                  <span className="w-40 shrink-0 truncate text-sm text-zinc-300">
                    {cat}
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={90}
                    step={1}
                    value={v ?? 0}
                    onChange={(e) => setCatMargin(cat, Number(e.target.value))}
                    className="h-1.5 flex-1 cursor-pointer accent-emerald-500"
                  />
                  <span className="w-12 text-right text-sm tabular-nums text-zinc-300">
                    {v != null ? `${v}%` : "—"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setCatMargin(cat, null)}
                    disabled={v == null}
                    title="Quitar margen estimado"
                    className="rounded-lg border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 disabled:opacity-30"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* ── Barra de guardado ──────────────────────────────────────── */}
      <div className="sticky bottom-0 mt-6 -mx-2 rounded-t-2xl border border-zinc-800 bg-zinc-950/90 px-4 py-3 backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-zinc-500">
            {classified} clasificados ·{" "}
            {rows.filter((r) => r.margenPct !== null).length} con margen propio
            · {Object.keys(catMargins).length} categorías con margen estimado
          </p>
          <button
            type="submit"
            className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Guardar cambios
          </button>
        </div>
      </div>
    </form>
  );
}
