import Link from "next/link";

export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center bg-zinc-950 px-6 py-16 text-zinc-100">
      <Link href="/" className="mb-8 text-2xl font-bold tracking-tight">
        Analytikz
      </Link>
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-8">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>
        {children}
      </div>
    </main>
  );
}

export const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-emerald-500 focus:outline-none";

export const labelClass = "mb-1 block text-sm font-medium text-zinc-300";

export const buttonClass =
  "w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50";
