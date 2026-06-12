import nodemailer from "nodemailer";
import type { Transporter } from "nodemailer";

// Email transaccional vía el buzón no-reply de Hostinger.
// Config 100% por variables de entorno (panel de Hostinger, nunca en el repo):
//   SMTP_USER     no-reply@analytikz.com.co
//   SMTP_PASS     contraseña del buzón
//   APP_BASE_URL  https://analytikz.com.co (sin slash final)
// Opcionales: SMTP_HOST (smtp.hostinger.com), SMTP_PORT (465), MAIL_FROM.
// Si falta config, los correos se desactivan con un aviso en consola — el
// registro y los reportes NUNCA fallan por culpa del correo.

function baseUrl(): string | null {
  const raw = process.env.APP_BASE_URL;
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
}

let cached: Transporter | null | undefined;

function getTransport(): Transporter | null {
  if (cached !== undefined) return cached;
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!user || !pass || !baseUrl()) {
    console.warn(
      "[email] SMTP_USER/SMTP_PASS/APP_BASE_URL sin configurar — correos desactivados",
    );
    cached = null;
    return cached;
  }
  const port = Number(process.env.SMTP_PORT ?? 465);
  cached = nodemailer.createTransport({
    host: process.env.SMTP_HOST ?? "smtp.hostinger.com",
    port,
    secure: port === 465,
    auth: { user, pass },
  });
  return cached;
}

function fromAddress(): string {
  return process.env.MAIL_FROM ?? `Analytikz <${process.env.SMTP_USER}>`;
}

// Plantilla común: fondo claro, estilos inline (los clientes de correo no
// cargan hojas de estilo), botón verde de marca.
function layout(title: string, bodyHtml: string): string {
  return `<!doctype html>
<html lang="es">
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:12px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 24px;font-size:18px;font-weight:bold;color:#18181b;">Analytikz</p>
          <h1 style="margin:0 0 16px;font-size:20px;color:#18181b;">${title}</h1>
          ${bodyHtml}
        </td></tr>
      </table>
      <p style="margin:16px 0 0;font-size:12px;color:#a1a1aa;">
        Analytikz · análisis de ventas para negocios de LatAm<br>
        Este buzón no recibe respuestas.
      </p>
    </td></tr>
  </table>
</body>
</html>`;
}

function button(href: string, label: string): string {
  return `<p style="margin:24px 0;">
    <a href="${href}" style="display:inline-block;background:#059669;color:#ffffff;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 24px;border-radius:8px;">${label}</a>
  </p>
  <p style="margin:0 0 8px;font-size:12px;color:#71717a;">Si el botón no funciona, copia y pega este enlace:</p>
  <p style="margin:0;font-size:12px;color:#71717a;word-break:break-all;">${href}</p>`;
}

async function send(to: string, subject: string, html: string): Promise<boolean> {
  const transport = getTransport();
  if (!transport) return false;
  try {
    await transport.sendMail({ from: fromAddress(), to, subject, html });
    return true;
  } catch (err) {
    console.error(`[email] fallo enviando "${subject}" a ${to}:`, err);
    return false;
  }
}

export async function sendVerificationEmail(
  to: string,
  name: string,
  token: string,
): Promise<boolean> {
  const base = baseUrl();
  if (!base) return false;
  const link = `${base}/verificar?token=${token}`;
  const html = layout(
    "Confirma tu correo",
    `<p style="margin:0 0 8px;font-size:14px;color:#3f3f46;">Hola ${name},</p>
     <p style="margin:0;font-size:14px;color:#3f3f46;">
       Gracias por crear tu cuenta en Analytikz. Confirma tu correo para que
       podamos avisarte cuando tus reportes estén listos.
     </p>
     ${button(link, "Confirmar mi correo")}`,
  );
  return send(to, "Confirma tu correo — Analytikz", html);
}

export async function sendReportReadyEmail(
  to: string,
  name: string,
  jobId: number,
  resumen: { storeName: string; totalRevenue: string; totalOrders: string; dateRange: string },
): Promise<boolean> {
  const base = baseUrl();
  if (!base) return false;
  const link = `${base}/reportes/${jobId}`;
  const html = layout(
    "Tu reporte está listo 🎉",
    `<p style="margin:0 0 8px;font-size:14px;color:#3f3f46;">Hola ${name},</p>
     <p style="margin:0 0 16px;font-size:14px;color:#3f3f46;">
       Ya analizamos las ventas de <strong>${resumen.storeName}</strong>
       (${resumen.dateRange}):
     </p>
     <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#f4f4f5;border-radius:8px;">
       <tr>
         <td style="padding:16px;text-align:center;">
           <p style="margin:0;font-size:12px;color:#71717a;">Ventas</p>
           <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#18181b;">${resumen.totalRevenue}</p>
         </td>
         <td style="padding:16px;text-align:center;">
           <p style="margin:0;font-size:12px;color:#71717a;">Órdenes</p>
           <p style="margin:4px 0 0;font-size:16px;font-weight:bold;color:#18181b;">${resumen.totalOrders}</p>
         </td>
       </tr>
     </table>
     ${button(link, "Ver mi reporte")}`,
  );
  return send(to, `Tu reporte de ${resumen.storeName} está listo — Analytikz`, html);
}
