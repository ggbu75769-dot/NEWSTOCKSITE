param(
  [string[]]$Environments = @("production", "preview", "development")
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
  throw "npx command not found"
}

$requiredKeys = @(
  "DATABASE_URL",
  "NEXTAUTH_URL",
  "NEXTAUTH_SECRET",
  "GOOGLE_CLIENT_ID",
  "GOOGLE_CLIENT_SECRET"
)

foreach ($key in $requiredKeys) {
  $currentValue = [Environment]::GetEnvironmentVariable($key)
  if (-not $currentValue) {
    throw "$key is not set in current shell environment"
  }
}

function Invoke-VercelCommand {
  param(
    [string[]]$CmdArgs,
    [string]$InputValue,
    [switch]$AllowFailure
  )

  if ($null -ne $InputValue) {
    if ($env:VERCEL_TOKEN) {
      $InputValue | & npx vercel @CmdArgs --token $env:VERCEL_TOKEN | Out-Null
    } else {
      $InputValue | & npx vercel @CmdArgs | Out-Null
    }
  } else {
    if ($env:VERCEL_TOKEN) {
      & npx vercel @CmdArgs --token $env:VERCEL_TOKEN | Out-Null
    } else {
      & npx vercel @CmdArgs | Out-Null
    }
  }

  if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
    throw "Vercel command failed: vercel $($CmdArgs -join ' ')"
  }
}

foreach ($environment in $Environments) {
  foreach ($key in $requiredKeys) {
    Write-Host "Syncing $key to $environment..."
    Invoke-VercelCommand -CmdArgs @("env", "rm", $key, $environment, "-y") -AllowFailure

    $value = [Environment]::GetEnvironmentVariable($key)
    Invoke-VercelCommand -CmdArgs @("env", "add", $key, $environment) -InputValue $value
  }
}

Write-Host "Vercel environment variable sync complete."
