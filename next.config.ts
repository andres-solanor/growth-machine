import type { NextConfig } from "next";

// Sin output:"standalone": Hostinger arranca con `next start` (incompatible
// con standalone) y su deploy corre `npm ci`, así que node_modules existe.
// Build con webpack (--webpack en scripts): Turbopack crashea en Node 24/Win.
// cpus: 2 limita los workers del build — evita agotar la memoria en máquinas
// con poco margen (Windows local y el build de Hostinger con 3 GB).
const nextConfig: NextConfig = {
  experimental: { cpus: 2 },
};

export default nextConfig;
