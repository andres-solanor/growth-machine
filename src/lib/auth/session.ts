import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

// Sesión = JWT firmado (HS256) en cookie httpOnly. Sin estado en servidor:
// sobrevive redeploys de Hostinger sin tabla de sesiones.
const COOKIE = "analytikz_session";
const DURATION_S = 60 * 60 * 24 * 30; // 30 días

function getSecret(): Uint8Array {
  const s = process.env.AUTH_SECRET;
  if (!s) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("AUTH_SECRET no está definida en las variables de entorno");
    }
    return new TextEncoder().encode("dev-secret-solo-para-local");
  }
  return new TextEncoder().encode(s);
}

export async function createSession(userId: number): Promise<void> {
  const token = await new SignJWT({ uid: userId })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${DURATION_S}s`)
    .sign(getSecret());
  (await cookies()).set(COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: DURATION_S,
    path: "/",
  });
}

export async function getSessionUserId(): Promise<number | null> {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, getSecret());
    return typeof payload.uid === "number" ? payload.uid : null;
  } catch {
    return null; // token inválido o expirado: tratar como no autenticado
  }
}

export async function destroySession(): Promise<void> {
  (await cookies()).delete(COOKIE);
}
