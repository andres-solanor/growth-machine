"use client";

import { useCallback, useEffect, useState } from "react";

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

function isTerminal(s: JobStatus | null): boolean {
  return s === "succeeded" || s === "failed" || s === "timed_out";
}

// Sondeo ACOTADO: 3 s durante el primer medio minuto, 10 s hasta los 3 min y
// luego se detiene del todo (el correo de "reporte listo" es el aviso
// principal). Un sondeo infinito mantenía vivos los procesos del servidor y
// agotaba el límite de procesos del hosting.
const FAST_MS = 3_000;
const SLOW_MS = 10_000;
const FAST_UNTIL_MS = 30_000;
const STOP_AFTER_MS = 180_000;

export function Progreso({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [checking, setChecking] = useState(false);

  const checkStatus = useCallback(async (): Promise<JobStatus | null> => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
      if (!res.ok) {
        setFetchError(true);
        return null;
      }
      const data = await res.json();
      setStatus(data.status);
      setErrorText(data.errorText ?? null);
      setFetchError(false);
      return data.status as JobStatus;
    } catch {
      setFetchError(true);
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();

    async function tick() {
      if (!active) return;
      // Pestaña en segundo plano: no consultar (cero costo en el servidor),
      // pero seguir agendando por si el usuario vuelve antes del tope.
      const latest = document.hidden ? null : await checkStatus();
      if (!active || isTerminal(latest)) return;
      const elapsed = Date.now() - startedAt;
      if (elapsed >= STOP_AFTER_MS) {
        setStopped(true);
        return;
      }
      timer = setTimeout(tick, elapsed < FAST_UNTIL_MS ? FAST_MS : SLOW_MS);
    }

    tick();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [checkStatus]);

  async function manualCheck() {
    setChecking(true);
    await checkStatus();
    setChecking(false);
  }

  const terminal = isTerminal(status);

  return (
    <div className="flex flex-col items-center gap-5">
      {!terminal && !stopped && (
        <div
          className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500"
          aria-hidden
        />
      )}
      <h1 className="text-2xl font-bold">
        {status ? LABELS[status] : "Consultando estado…"}
      </h1>

      {!terminal && !stopped && (
        <p className="max-w-sm text-sm text-zinc-400">
          Tu análisis está en proceso (~1 minuto). Puedes quedarte aquí: esta
          página se actualiza sola.
        </p>
      )}

      {!terminal && stopped && (
        <div className="flex max-w-sm flex-col items-center gap-4">
          <p className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-400">
            Esto está tardando más de lo normal. Te avisaremos por correo
            cuando tu reporte esté listo — no necesitas dejar esta página
            abierta.
          </p>
          <button
            onClick={manualCheck}
            disabled={checking}
            className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-semibold text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
          >
            {checking ? "Consultando…" : "Actualizar estado"}
          </button>
        </div>
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
