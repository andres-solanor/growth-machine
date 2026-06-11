"use client";

import { useActionState } from "react";
import Link from "next/link";
import { registrar, type RegistroState } from "./actions";
import { buttonClass, inputClass, labelClass } from "../_components/auth-card";

export function RegistroForm() {
  const [state, action, pending] = useActionState<RegistroState, FormData>(
    registrar,
    {},
  );
  return (
    <form action={action} className="mt-6 space-y-4">
      <div>
        <label htmlFor="name" className={labelClass}>
          Tu nombre
        </label>
        <input id="name" name="name" required className={inputClass} placeholder="Andrés Solano" />
      </div>
      <div>
        <label htmlFor="businessName" className={labelClass}>
          Nombre de tu negocio
        </label>
        <input id="businessName" name="businessName" required className={inputClass} placeholder="Panadería La Espiga" />
      </div>
      <div>
        <label htmlFor="email" className={labelClass}>
          Correo electrónico
        </label>
        <input id="email" name="email" type="email" required className={inputClass} placeholder="tu@correo.com" />
      </div>
      <div>
        <label htmlFor="password" className={labelClass}>
          Contraseña
        </label>
        <input
          id="password"
          name="password"
          type="password"
          required
          minLength={8}
          className={inputClass}
          placeholder="Mínimo 8 caracteres"
        />
      </div>
      {state.error && (
        <p className="rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className={buttonClass}>
        {pending ? "Creando cuenta…" : "Crear cuenta gratis"}
      </button>
      <p className="text-center text-sm text-zinc-400">
        ¿Ya tienes cuenta?{" "}
        <Link href="/ingresar" className="text-emerald-400 hover:underline">
          Ingresar
        </Link>
      </p>
    </form>
  );
}
