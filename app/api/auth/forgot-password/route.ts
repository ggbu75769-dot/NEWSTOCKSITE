import { isValidEmail, issuePasswordReset } from "@/lib/passwordReset";
import { checkRateLimit, readClientIdentifier } from "@/lib/rateLimit";
import { NextResponse } from "next/server";

type ForgotPasswordPayload = {
  email?: string;
};

export async function POST(request: Request) {
  const clientId = readClientIdentifier(request);
  const rateLimit = checkRateLimit({
    scope: "auth-forgot-password",
    identifier: clientId,
    limit: 8,
    windowMs: 10 * 60 * 1000,
  });

  if (!rateLimit.ok) {
    return NextResponse.json(
      { error: "RATE_LIMITED", retryAfter: rateLimit.retryAfterSeconds },
      { status: 429, headers: { "Retry-After": String(rateLimit.retryAfterSeconds) } }
    );
  }

  let payload: ForgotPasswordPayload;
  try {
    payload = (await request.json()) as ForgotPasswordPayload;
  } catch {
    return NextResponse.json({ error: "INVALID_PAYLOAD" }, { status: 400 });
  }

  const email = payload.email?.trim().toLowerCase() ?? "";
  if (!email || !isValidEmail(email)) {
    return NextResponse.json({ error: "EMAIL_INVALID" }, { status: 400 });
  }

  const requestOrigin = new URL(request.url).origin;
  const result = await issuePasswordReset({ email, requestOrigin });

  const shouldExposeDebugLink =
    process.env.NODE_ENV !== "production" && process.env.AUTH_DEBUG_RESET_LINK === "true";

  if (shouldExposeDebugLink) {
    return NextResponse.json({ ok: true, debugResetUrl: result.resetUrl }, { status: 200 });
  }

  return NextResponse.json({ ok: true }, { status: 200 });
}
