# Google Login + User DB Setup

## 1) Required Environment Variables

Set these in `.env.local` (or deployment secrets):

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=replace-with-long-random-secret

GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret

DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME?schema=public
VS_DATA_DIR=./data
VS_LOGS_DIR=./logs

# Optional: password reset email delivery (SMTP)
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASS=your-smtp-pass
SMTP_FROM=no-reply@your-domain.com

# Optional: show reset URL in API response during local development
AUTH_DEBUG_RESET_LINK=false
```

## 2) Google OAuth Redirect URI

In Google Cloud Console OAuth Client settings, add:

```txt
http://localhost:3000/api/auth/callback/google
```

For production, add your real domain callback URI too.

## 3) Initialize Prisma DB

```bash
npm run prisma:generate
npm run prisma:migrate:dev -- --name init_auth
```

Production migration:

```bash
npm run prisma:migrate
```

## 4) Flow Summary

- `/login` -> Email/Password sign-in or Google sign-in
- `/forgot-password` -> reset link request
- `/reset-password?token=...` -> set new password
- Auth callback handled by `app/api/auth/[...nextauth]/route.ts`
- Email/password signup handled by `app/api/auth/register/route.ts`
- Password reset handled by `app/api/auth/forgot-password/route.ts` and `app/api/auth/reset-password/route.ts`
- User/account/session stored in DB via Prisma adapter
- `/dashboard`, `/recommendations` are login-protected
- Auth APIs apply basic rate limiting for register/forgot/reset endpoints

## 5) Deployment Secrets (Vercel Example)

Copy required values from your local env to shell env first, then sync to Vercel.

PowerShell:

```powershell
$env:DATABASE_URL='postgresql://...'
$env:NEXTAUTH_URL='https://your-domain.com'
$env:NEXTAUTH_SECRET='...'
$env:GOOGLE_CLIENT_ID='...'
$env:GOOGLE_CLIENT_SECRET='...'

# Optional for non-interactive CI
$env:VERCEL_TOKEN='...'

powershell -ExecutionPolicy Bypass -File scripts/set-vercel-env.ps1
```

If your repo is not linked yet, run `npx vercel login` and `npx vercel link` once before syncing secrets.
