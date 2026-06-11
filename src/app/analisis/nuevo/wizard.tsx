"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CANONICAL_FIELDS,
  type ColumnMapping,
  type FieldKey,
} from "@/lib/csv-detect";
import { guardarNegocio } from "./actions";

const PAISES: [string, string][] = [
  ["CO", "Colombia"],
  ["MX", "México"],
  ["PE", "Perú"],
  ["CL", "Chile"],
  ["AR", "Argentina"],
  ["EC", "Ecuador"],
  ["UY", "Uruguay"],
  ["GT", "Guatemala"],
  ["CR", "Costa Rica"],
  ["DO", "Rep. Dominicana"],
  ["BO", "Bolivia"],
  ["PY", "Paraguay"],
  ["PA", "Panamá"],
  ["US", "Estados Unidos"],
  ["ES", "España"],
];

const MONEDAS: [string, string][] = [
  ["COP", "Peso colombiano (COP)"],
  ["MXN", "Peso mexicano (MXN)"],
  ["PEN", "Sol peruano (PEN)"],
  ["CLP", "Peso chileno (CLP)"],
  ["ARS", "Peso argentino (ARS)"],
  ["USD", "Dólar (USD)"],
  ["UYU", "Peso uruguayo (UYU)"],
  ["GTQ", "Quetzal (GTQ)"],
  ["CRC", "Colón (CRC)"],
  ["DOP", "Peso dominicano (DOP)"],
  ["BOB", "Boliviano (BOB)"],
  ["PYG", "Guaraní (PYG)"],
  ["EUR", "Euro (EUR)"],
];

type UploadResult = {
  datasetId: number;
  filename: string;
  rowCount: number;
  headers: string[];
  sample: string[][];
  autoMap: ColumnMapping;
};

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none";
const labelClass = "mb-1 block text-sm font-medium text-zinc-300";
const primaryBtn =
  "rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50";

function Steps({ current }: { current: 1 | 2 | 3 }) {
  const items = ["Tu negocio", "Archivo de ventas", "Columnas"];
  return (
    <ol className="mb-8 flex gap-2 text-xs">
      {items.map((label, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        const state =
          n < current ? "done" : n === current ? "active" : "todo";
        return (
          <li
            key={label}
            className={
              "flex-1 rounded-full border px-3 py-1.5 text-center " +
              (state === "done"
                ? "border-emerald-700 bg-emerald-950 text-emerald-300"
                : state === "active"
                  ? "border-zinc-500 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 text-zinc-500")
            }
          >
            {n}. {label}
          </li>
        );
      })}
    </ol>
  );
}

export function Wizard({
  tenant,
}: {
  tenant: { name: string; country: string; currency: string };
}) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Paso 1
  const [negocio, setNegocio] = useState(tenant);

  // Paso 2
  const fileRef = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<UploadResult | null>(null);

  // Paso 3
  const [mapping, setMapping] = useState<ColumnMapping>({});

  async function submitNegocio(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await guardarNegocio(negocio);
    setBusy(false);
    if (!res.ok) {
      setError(res.error ?? "Error guardando los datos");
      return;
    }
    setStep(2);
  }

  async function submitArchivo(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Selecciona el archivo de ventas de tu POS");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/datasets", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "No pudimos subir el archivo");
        return;
      }
      setUpload(data);
      setMapping(data.autoMap);
      setStep(3);
    } catch {
      setError("Error de conexión al subir el archivo. Intenta de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  async function submitMapping(e: React.FormEvent) {
    e.preventDefault();
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ datasetId: upload.datasetId, mapping }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "No pudimos crear el análisis");
        return;
      }
      router.push(`/reportes/procesando/${data.jobId}`);
    } catch {
      setError("Error de conexión al crear el análisis. Intenta de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Tu primer análisis</h1>
      <p className="mb-6 text-sm text-zinc-400">
        Tres pasos y tu reporte estará en camino.
      </p>
      <Steps current={step} />

      {error && (
        <p className="mb-4 rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {step === 1 && (
        <form onSubmit={submitNegocio} className="space-y-4">
          <div>
            <label htmlFor="bn" className={labelClass}>
              Nombre del negocio
            </label>
            <input
              id="bn"
              className={inputClass}
              value={negocio.name}
              onChange={(e) => setNegocio({ ...negocio, name: e.target.value })}
              required
              minLength={2}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="pais" className={labelClass}>
                País
              </label>
              <select
                id="pais"
                className={inputClass}
                value={negocio.country}
                onChange={(e) =>
                  setNegocio({ ...negocio, country: e.target.value })
                }
              >
                {PAISES.map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="moneda" className={labelClass}>
                Moneda de tus ventas
              </label>
              <select
                id="moneda"
                className={inputClass}
                value={negocio.currency}
                onChange={(e) =>
                  setNegocio({ ...negocio, currency: e.target.value })
                }
              >
                {MONEDAS.map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button type="submit" disabled={busy} className={primaryBtn}>
            {busy ? "Guardando…" : "Continuar"}
          </button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={submitArchivo} className="space-y-4">
          <div className="rounded-2xl border border-dashed border-zinc-700 bg-zinc-900 p-8 text-center">
            <p className="mb-3 text-sm text-zinc-300">
              Exporta las ventas desde tu sistema POS (idealmente 2–3 meses) y
              súbelas aquí.
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xls,.xlsx"
              className="mx-auto block text-sm text-zinc-400 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-emerald-500"
            />
            <p className="mt-3 text-xs text-zinc-500">
              Formatos: .csv, .xls, .xlsx · Máximo 20 MB · Tus datos no se
              comparten con nadie
            </p>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Atrás
            </button>
            <button type="submit" disabled={busy} className={primaryBtn}>
              {busy ? "Subiendo…" : "Subir archivo"}
            </button>
          </div>
        </form>
      )}

      {step === 3 && upload && (
        <form onSubmit={submitMapping} className="space-y-6">
          <p className="text-sm text-zinc-400">
            Leímos <strong className="text-zinc-200">{upload.rowCount.toLocaleString("es-CO")}</strong>{" "}
            filas de <strong className="text-zinc-200">{upload.filename}</strong>.
            Confirma qué columna corresponde a cada dato (ya intentamos
            adivinarlo):
          </p>
          <div className="space-y-3">
            {CANONICAL_FIELDS.map((f) => (
              <div key={f.key} className="grid grid-cols-2 items-center gap-3">
                <label htmlFor={`map-${f.key}`} className="text-sm text-zinc-300">
                  {f.label}
                  {f.required ? (
                    <span className="text-emerald-400"> *</span>
                  ) : (
                    <span className="text-zinc-500"> (opcional)</span>
                  )}
                </label>
                <select
                  id={`map-${f.key}`}
                  className={inputClass}
                  value={mapping[f.key] ?? ""}
                  onChange={(e) =>
                    setMapping((m) => {
                      const next = { ...m };
                      if (e.target.value === "") delete next[f.key as FieldKey];
                      else next[f.key as FieldKey] = e.target.value;
                      return next;
                    })
                  }
                >
                  <option value="">— sin asignar —</option>
                  {upload.headers.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-900 text-zinc-400">
                <tr>
                  {upload.headers.map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {upload.sample.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-800">
                    {upload.headers.map((_, j) => (
                      <td key={j} className="px-3 py-1.5">
                        {row[j] ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Atrás
            </button>
            <button type="submit" disabled={busy} className={primaryBtn}>
              {busy ? "Creando análisis…" : "Crear mi análisis"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
