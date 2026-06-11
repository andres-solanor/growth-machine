"use client";

import { useEffect, useState } from "react";

type JobStatus =
  | "queued"
  | "dispatched"
  | "running"
  | "succeeded"
  | "failed"
  | "timed_out";

const LABELS: Record<JobStatus, string> = {
  queued: "En cola…",
  dispatched: "Preparando el análisis…",
  running: "Analizando tus ventas…",
  succeeded: "¡Listo!",
  failed: "Algo salió mal",
  timed_out: "El análisis tardó demasiado",
};

export function Progreso({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState(false);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
        if (!res.ok) {
          if (active) setFetchError(true);
          return;
        }
        const data = await res.json();
        if (active) {
          setStatus(data.status);
          setErrorText(data.errorText ?? null);
          setFetchError(false);
        }
      } catch {
        if (active) setFetchError(true);
      }
    }
    poll();
    const t = setInterval(poll, 3000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [jobId]);

  const terminal =
    status === "succeeded" || status === "failed" || status === "timed_out";

  return (
    <div className="flex flex-col items-center gap-5">
      {!terminal && (
        <div
          className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500"
          aria-hidden
        />
      )}
      <h1 className="text-2xl font-bold">
        {status ? LABELS[status] : "Consultando estado…"}
      </h1>

      {!terminal && (
        <p className="max-w-sm text-sm text-zinc-400">
          Tu análisis está en proceso (~1 minuto). Puedes quedarte aquí: esta
          página se actualiza sola.
        </p>
      )}

      {status === "queued" && (
        <p className="max-w-sm rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 text-xs text-zinc-500">
          Tu archivo quedó guardado y el análisis está en cola. Si tarda más de
          un minuto, lo reintentamos automáticamente.
          {errorText && (
            <span className="mt-2 block text-amber-400">{errorText}</span>
          )}
        </p>
      )}

      {status === "succeeded" && (
        <a
          href={`/reportes/${jobId}`}
          className="rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          Ver mi reporte →
        </a>
      )}

      {(status === "failed" || status === "timed_out") && (
        <div className="max-w-sm text-sm text-zinc-400">
          <p>
            {errorText ??
              "No pudimos completar el análisis. Intenta de nuevo o escríbenos."}
          </p>
        </div>
      )}

      {fetchError && (
        <p className="text-xs text-zinc-500">
          Sin conexión con el servidor, reintentando…
        </p>
      )}
    </div>
  );
}
