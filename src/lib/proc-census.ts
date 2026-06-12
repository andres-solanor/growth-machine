import { readdir, readFile } from "node:fs/promises";

// Censo de procesos/hilos de la cuenta de hosting, leyendo /proc (Linux).
// El límite "Max processes" de Hostinger (CloudLinux) cuenta procesos + hilos
// de TODA la cuenta: este censo muestra exactamente qué lo está consumiendo.
// Solo expone el nombre del proceso (comm), nunca el cmdline completo —
// podría contener argumentos derivados de env vars.

type ProcEntry = {
  pid: number;
  ppid: number;
  name: string;
  threads: number;
  rssMb: number;
};

export type ProcCensus =
  | { supported: false }
  | {
      supported: true;
      processCount: number;
      totalTasks: number; // suma de hilos (incluye el principal de cada
      // proceso) = tareas del kernel: lo que mide el gauge de hPanel
      self: { pid: number; threads: number };
      list: ProcEntry[];
    };

function field(status: string, key: string): string | undefined {
  const m = status.match(new RegExp(`^${key}:\\s+(.+)$`, "m"));
  return m?.[1];
}

export async function procCensus(): Promise<ProcCensus> {
  if (process.platform !== "linux" || !process.getuid) {
    return { supported: false };
  }
  const uid = String(process.getuid());
  let pids: string[];
  try {
    pids = (await readdir("/proc")).filter((d) => /^\d+$/.test(d));
  } catch {
    return { supported: false };
  }

  const list: ProcEntry[] = [];
  for (const pid of pids) {
    let status: string;
    try {
      status = await readFile(`/proc/${pid}/status`, "utf-8");
    } catch {
      continue; // el proceso terminó entre el readdir y la lectura
    }
    // Uid: real efectivo guardado fs — el primero es el real.
    if (field(status, "Uid")?.split(/\s+/)[0] !== uid) continue;
    list.push({
      pid: Number(pid),
      ppid: Number(field(status, "PPid") ?? -1),
      name: field(status, "Name") ?? "?",
      threads: Number(field(status, "Threads") ?? 1),
      rssMb:
        Math.round((parseInt(field(status, "VmRSS") ?? "0", 10) / 1024) * 10) /
        10,
    });
  }

  list.sort((a, b) => b.threads - a.threads);
  const selfEntry = list.find((p) => p.pid === process.pid);
  return {
    supported: true,
    processCount: list.length,
    totalTasks: list.reduce((sum, p) => sum + p.threads, 0),
    self: { pid: process.pid, threads: selfEntry?.threads ?? -1 },
    list,
  };
}
