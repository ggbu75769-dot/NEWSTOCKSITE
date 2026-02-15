import { prisma } from "@/lib/prisma";
import { hash } from "bcryptjs";
import crypto from "crypto";
import nodemailer from "nodemailer";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const RESET_TOKEN_TTL_MS = 1000 * 60 * 60; // 1 hour

type IssueResetOptions = {
  email: string;
  requestOrigin?: string;
};

type ResetResult = "OK" | "INVALID_TOKEN" | "EXPIRED_TOKEN";

function normalizeBaseUrl(origin?: string): string {
  const base = process.env.NEXTAUTH_URL?.trim() || origin?.trim() || "http://localhost:3000";
  return base.replace(/\/+$/, "");
}

function hashToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

function makeToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

function getSmtpConfig() {
  const host = process.env.SMTP_HOST?.trim();
  const portRaw = process.env.SMTP_PORT?.trim();
  const user = process.env.SMTP_USER?.trim();
  const pass = process.env.SMTP_PASS?.trim();
  const from = process.env.SMTP_FROM?.trim();

  if (!host || !portRaw || !user || !pass || !from) {
    return null;
  }

  const port = Number(portRaw);
  if (!Number.isFinite(port)) {
    return null;
  }

  return {
    host,
    port,
    secure: port === 465,
    auth: { user, pass },
    from,
  };
}

async function sendResetEmail(email: string, resetUrl: string) {
  const smtpConfig = getSmtpConfig();
  if (!smtpConfig) {
    console.info(`[auth] password reset link for ${email}: ${resetUrl}`);
    return false;
  }

  const transporter = nodemailer.createTransport({
    host: smtpConfig.host,
    port: smtpConfig.port,
    secure: smtpConfig.secure,
    auth: smtpConfig.auth,
  });

  await transporter.sendMail({
    from: smtpConfig.from,
    to: email,
    subject: "Reset your password",
    text: `Open this link to reset your password:\n${resetUrl}\n\nThis link expires in 1 hour.`,
    html: `<p>Open this link to reset your password:</p><p><a href="${resetUrl}">${resetUrl}</a></p><p>This link expires in 1 hour.</p>`,
  });
  return true;
}

export function isValidEmail(email: string): boolean {
  return EMAIL_RE.test(email);
}

export async function issuePasswordReset({ email, requestOrigin }: IssueResetOptions) {
  const normalizedEmail = email.trim().toLowerCase();
  const user = await prisma.user.findUnique({
    where: { email: normalizedEmail },
    select: { id: true, email: true },
  });

  if (!user?.email) {
    return { ok: true, resetUrl: null };
  }

  const token = makeToken();
  const tokenHash = hashToken(token);
  const expires = new Date(Date.now() + RESET_TOKEN_TTL_MS);
  const baseUrl = normalizeBaseUrl(requestOrigin);
  const resetUrl = `${baseUrl}/reset-password?token=${encodeURIComponent(token)}`;

  await prisma.$transaction([
    prisma.passwordResetToken.deleteMany({
      where: { userId: user.id, usedAt: null },
    }),
    prisma.passwordResetToken.create({
      data: {
        userId: user.id,
        tokenHash,
        expires,
      },
    }),
  ]);

  await sendResetEmail(user.email, resetUrl);
  return { ok: true, resetUrl };
}

export async function resetPasswordByToken(token: string, newPassword: string): Promise<ResetResult> {
  const tokenHash = hashToken(token);
  const record = await prisma.passwordResetToken.findUnique({
    where: { tokenHash },
    select: {
      id: true,
      userId: true,
      expires: true,
      usedAt: true,
    },
  });

  if (!record) {
    return "INVALID_TOKEN";
  }

  if (record.usedAt || record.expires.getTime() < Date.now()) {
    return "EXPIRED_TOKEN";
  }

  const hashedPassword = await hash(newPassword, 12);
  const now = new Date();

  await prisma.$transaction([
    prisma.user.update({
      where: { id: record.userId },
      data: { hashedPassword },
    }),
    prisma.passwordResetToken.update({
      where: { id: record.id },
      data: { usedAt: now },
    }),
    prisma.passwordResetToken.updateMany({
      where: {
        userId: record.userId,
        id: { not: record.id },
        usedAt: null,
      },
      data: { usedAt: now },
    }),
  ]);

  return "OK";
}
