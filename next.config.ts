import type { NextConfig } from "next";

// Sin output:"standalone": Hostinger arranca con `next start` (incompatible
// con standalone) y su deploy corre `npm ci`, así que node_modules existe.
// Build con webpack (--webpack en scripts): Turbopack crashea en Node 24/Win.
const nextConfig: NextConfig = {};

export default nextConfig;
