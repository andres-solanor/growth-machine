"use client";

import { useActionState } from "react";
import { enviarLead, type LeadState } from "./actions";

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-emerald-500 focus:outline-none";
const labelClass = "mb-1 block text-sm font-medium text-zinc-300";

export function LeadForm({
  defaults,
}: {
  defaults: { name: string; email: string };
}) {
  const [state, action, pending] = useActionState<LeadState, FormData>(
    enviarLead,
    {},
  );
  return (
    <form action={action} className="mt-6 space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="name" className={labelClass}>
            Tu nombre
          </label>
          <input
            id="name"
            name="name"
            required
            defaultValue={defaults.name}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="email" className={labelClass}>
            Correo
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            defaultValue={defaults.email}
            className={inputClass}
          />
        </div>
      </div>
      <div>
        <label htmlFor="phone" className={labelClass}>
          WhatsApp (opcional)
        </label>
        <input id="phone" name="phone" className={inputClass} placeholder="+57 ..." />
      </div>
      <div>
        <label htmlFor="message" className={labelClass}>
          Cuéntanos de tu negocio (opcional)
        </label>
        <textarea
          id="message"
          name="message"
          rows={4}
          className={inputClass}
          placeholder="Tipo de negocio, qué te gustaría mejorar…"
        />
      </div>
      {state.error && (
        <p className="rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {pending ? "Enviando…" : "Solicitar mi sesión"}
      </button>
    </form>
  );
}
