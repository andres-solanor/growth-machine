#!/usr/bin/env python3
"""
worker/gha_runner.py — shell HTTP del worker en GitHub Actions.

Flujo: pide el spec del job a la app (HMAC), descarga el dataset, ejecuta
run_job.py y devuelve el payload (gzip) o el error. Nunca imprime datos de
ventas: solo estados y conteos.

Env requeridas: APP_BASE_URL, WORKER_SHARED_SECRET, JOB_ID
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ["APP_BASE_URL"].rstrip("/")
SECRET = os.environ["WORKER_SHARED_SECRET"].encode("utf-8")
JOB_ID = os.environ["JOB_ID"]

REPO_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"job-{JOB_ID}"


def _signed_headers(method: str, path: str, body: bytes | None) -> dict:
    ts = str(int(time.time()))
    base = f"{ts}.{method}.{path}"
    if body:
        base += "." + hashlib.sha256(body).hexdigest()
    sig = hmac.new(SECRET, base.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"X-Worker-Ts": ts, "X-Worker-Sig": sig}


# El hosting (LiteSpeed) corta conexiones SIN respuesta HTTP cuando llega al
# límite de procesos → RemoteDisconnected/URLError aquí. Reintentar con
# backoff exponencial; sin esto, una conexión cortada mata un job ya calculado.
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def _request(method: str, path: str, body: bytes | None = None,
             content_type: str | None = None, attempts: int = 4) -> bytes:
    for attempt in range(1, attempts + 1):
        # Firma fresca por intento: el timestamp HMAC caduca entre esperas.
        headers = _signed_headers(method, path, body)
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(BASE + path, data=body, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP or attempt == attempts:
                raise
            reason = f"HTTP {exc.code}"
        except (urllib.error.URLError, http.client.HTTPException,
                ConnectionError, TimeoutError) as exc:
            if attempt == attempts:
                raise
            reason = type(exc).__name__
        wait = 2 ** attempt
        print(f"[runner] {method} {path}: {reason}; "
              f"reintento {attempt}/{attempts - 1} en {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise AssertionError("unreachable")


def _post_failure(error: str) -> None:
    body = json.dumps({"ok": False, "error": error[:2000]}).encode("utf-8")
    try:
        _request("POST", f"/api/worker/jobs/{JOB_ID}/result", body,
                 "application/json", attempts=3)
    except Exception as exc:  # ya estamos reportando un fallo; solo log
        print(f"[runner] no se pudo reportar el fallo: {exc}", file=sys.stderr)


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[runner] job {JOB_ID}: pidiendo spec...")
    spec_app = json.loads(_request("GET", f"/api/worker/jobs/{JOB_ID}/spec"))

    filename = spec_app.get("dataset_filename") or "dataset.csv"
    print(f"[runner] descargando dataset ({filename})...")
    ds_gz = _request("GET", f"/api/worker/jobs/{JOB_ID}/dataset")
    input_path = WORK_DIR / Path(filename).name
    input_path.write_bytes(gzip.decompress(ds_gz))

    job_spec = {
        "job_id": str(spec_app["job_id"]),
        "type": spec_app.get("type", "report"),
        "input_files": [str(input_path)],
        "column_mapping": spec_app.get("column_mapping"),
        "tenant_config": spec_app.get("tenant_config") or {},
        "product_map": spec_app.get("product_map"),
        "delta_config": spec_app.get("delta_config"),
    }
    spec_path = WORK_DIR / "job_spec.json"
    spec_path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")

    print("[runner] ejecutando motor de analisis...")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "worker" / "run_job.py"),
         "--spec", str(spec_path), "--out-dir", str(WORK_DIR)],
        capture_output=True, text=True, timeout=480,
    )
    # stdout/stderr del motor: solo conteos y errores, sin filas de datos
    if proc.stdout:
        print(proc.stdout[-2000:])
    if proc.returncode != 0:
        err = "el motor de analisis fallo"
        result_file = WORK_DIR / "job_result.json"
        if result_file.exists():
            try:
                err = json.loads(result_file.read_text(encoding="utf-8")).get("error", err)
            except Exception:
                pass
        if proc.stderr:
            print(proc.stderr[-2000:], file=sys.stderr)
        _post_failure(err)
        return 1

    payload_path = WORK_DIR / "payload.json"
    payload_gz = gzip.compress(payload_path.read_bytes())
    print(f"[runner] enviando payload ({len(payload_gz):,} bytes gzip)...")
    # El paso más crítico: el análisis ya está hecho, solo falta entregarlo.
    _request("POST", f"/api/worker/jobs/{JOB_ID}/result", payload_gz,
             "application/gzip", attempts=6)
    print("[runner] OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        print(f"[runner] HTTP {exc.code} en {exc.url}: {detail}", file=sys.stderr)
        _post_failure(f"runner HTTP {exc.code}: {detail}")
        sys.exit(1)
    except Exception as exc:
        print(f"[runner] error: {type(exc).__name__}: {exc}", file=sys.stderr)
        _post_failure(f"{type(exc).__name__}: {exc}")
        sys.exit(1)
