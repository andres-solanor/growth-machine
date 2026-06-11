// Despacho de jobs al worker: repository_dispatch en el repo de GitHub.
// Env requeridas (panel de Hostinger):
//   GITHUB_REPO            p. ej. andres-solanor/growth-machine
//   GITHUB_DISPATCH_TOKEN  PAT fine-grained con permiso Contents: read/write
export async function dispatchAnalysisJob(
  jobId: number,
): Promise<{ ok: boolean; error?: string }> {
  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!repo || !token) {
    return { ok: false, error: "Worker no configurado (faltan GITHUB_REPO / GITHUB_DISPATCH_TOKEN)" };
  }
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: "analysis-job",
        client_payload: { job_id: jobId },
      }),
    });
    if (res.status === 204) return { ok: true };
    return { ok: false, error: `GitHub dispatch HTTP ${res.status}` };
  } catch (err) {
    return {
      ok: false,
      error: `GitHub dispatch: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}
