"use client";

import { useActionState } from "react";
import Link from "next/link";
import { ingresar, type LoginState } from "./actions";
import { buttonClass, inputClass, labelClass } from "@/components/auth-card";

export function IngresarForm() {
  const [state, action, pending] = useActionState<LoginState, FormData>(
    ingresar,
    {},
  );
  return (
    <form action={action} className="mt-6 space-y-4">
      <div>
        <label htmlFor="email" className={labelClass}>
          Correo electrÃ³nico
        </label>
        <input id="email" name="email" type="email" required className={inputClass} placeholder="tu@correo.com" />
      </div>
      <div>
        <label htmlFor="password" className={labelClass}>
          ContraseÃ±a
        </label>
        <input id="password" name="password" type="password" required className={inputClass} />
      </div>
      {state.error && (
        <p className="rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className={buttonClass}>
        {pending ? "Ingresandoâ€¦" : "Ingresar"}
      </button>
      <p className="text-center text-sm text-zinc-400">
        Â¿No tienes cuenta?{" "}
        <Link href="/registro" className="text-emerald-400 hover:underline">
          Crear cuenta gratis
        </Link>
      </p>
    </form>
  );
}
