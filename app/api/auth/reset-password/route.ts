import { resetPasswordByToken } from "@/lib/passwordReset";
import { checkRateLimit, readClientIdentifier } from "@/lib/rateLimit";
import { NextResponse } from "next/server";

type ResetPasswordPayload = {
  token?: string;
  password?: string;
};

const MIN_PASSWORD_LENGTH = 8;

export async function POST(request: Request) {
  const clientId = readClientIdentifier(request);
  const rateLimit = checkRateLimit({
    scope: "auth-reset-password",
    identifier: clientId,
    limit: 12,
    windowMs: 10 * 60 * 1000,
  });

  if (!rateLimit.ok) {
    return NextResponse.json(
      { error: "RATE_LIMITED", retryAfter: rateLimit.retryAfterSeconds },
      { status: 429, headers: { "Retry-After": String(rateLimit.retryAfterSeconds) } }
    );
  }

  let payload: ResetPasswordPayload;
  try {
    payload = (await request.json()) as ResetPasswordPayload;
  } catch {
    return NextResponse.json({ error: "INVALID_PAYLOAD" }, { status: 400 });
  }

  const token = payload.token?.trim() ?? "";
  const password = payload.password ?? "";

  if (!token) {
    return NextResponse.json({ error: "TOKEN_REQUIRED" }, { status: 400 });
  }

  if (password.length < MIN_PASSWORD_LENGTH) {
    return NextResponse.json({ error: "PASSWORD_TOO_SHORT" }, { status: 400 });
  }

  const result = await resetPasswordByToken(token, password);
  if (result === "INVALID_TOKEN") {
    return NextResponse.json({ error: "INVALID_TOKEN" }, { status: 400 });
  }
  if (result === "EXPIRED_TOKEN") {
    return NextResponse.json({ error: "EXPIRED_TOKEN" }, { status: 400 });
  }

  return NextResponse.json({ ok: true }, { status: 200 });
}
