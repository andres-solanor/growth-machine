import { createHash, createHmac, timingSafeEqual } from "node:crypto";

// Autenticación de la API del worker (GitHub Actions): HMAC-SHA256 con
// secreto compartido sobre `ts.METHOD.path[.sha256(body)]`, tolerancia de
// reloj 5 min. Espejo exacto de worker/gha_runner.py::_signed_headers.
const MAX_SKEW_S = 300;

export function verifyWorkerRequest(
  req: Request,
  path: string,
  body?: Buffer,
): boolean {
  const secret = process.env.WORKER_SHARED_SECRET;
  if (!secret) return false;
  const ts = req.headers.get("x-worker-ts");
  const sig = req.headers.get("x-worker-sig");
  if (!ts || !sig) return false;
  const tsNum = Number(ts);
  if (!Number.isFinite(tsNum)) return false;
  if (Math.abs(Date.now() / 1000 - tsNum) > MAX_SKEW_S) return false;

  let base = `${ts}.${req.method.toUpperCase()}.${path}`;
  if (body && body.length > 0) {
    base += "." + createHash("sha256").update(body).digest("hex");
  }
  const expected = createHmac("sha256", secret).update(base).digest("hex");
  const a = Buffer.from(expected, "utf-8");
  const b = Buffer.from(sig, "utf-8");
  return a.length === b.length && timingSafeEqual(a, b);
}
