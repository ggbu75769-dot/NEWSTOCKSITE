param(
    [string]$TaskPrefix = "OpenCode",
    [string]$PythonExe = "python",
    [string]$Tickers = "AAPL,MSFT,NVDA,AMZN,GOOGL",
    [string]$DailyTime = "18:30",
    [string]$AnalyticsTime = "18:40",
    [string]$AnalyticsQuery = "high_low_52_week",
    [switch]$CreateAnalyticsTask = $true
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$EodLog = Join-Path $LogDir "daily_update.log"
$AnalyticsLog = Join-Path $LogDir "analytics.log"

$EodTaskName = "${TaskPrefix}_DailyUpdate"
$AnalyticsTaskName = "${TaskPrefix}_Analytics"

# cmd /c 를 사용해 리다이렉션(>>) 적용
$EodCommand = "cd /d `"$Root`" && `"$PythonExe`" run_data_pipeline.py --mode daily_update --tickers `"$Tickers`" >> `"$EodLog`" 2>&1"
$AnalyticsCommand = "cd /d `"$Root`" && `"$PythonExe`" run_data_pipeline.py --mode analytics --analytics-query `"$AnalyticsQuery`" >> `"$AnalyticsLog`" 2>&1"

Write-Host "[등록] $EodTaskName ($DailyTime)"
schtasks /Create /F /SC DAILY /ST $DailyTime /TN $EodTaskName /TR "cmd /c $EodCommand" | Out-Null

if ($CreateAnalyticsTask) {
    Write-Host "[등록] $AnalyticsTaskName ($AnalyticsTime)"
    schtasks /Create /F /SC DAILY /ST $AnalyticsTime /TN $AnalyticsTaskName /TR "cmd /c $AnalyticsCommand" | Out-Null
}

Write-Host "[완료] 작업 스케줄러 등록이 끝났습니다."
Write-Host " - EOD 작업: $EodTaskName"
if ($CreateAnalyticsTask) {
    Write-Host " - 분석 작업: $AnalyticsTaskName"
}
Write-Host ""
Write-Host "즉시 테스트 실행:"
Write-Host "  schtasks /Run /TN `"$EodTaskName`""
if ($CreateAnalyticsTask) {
    Write-Host "  schtasks /Run /TN `"$AnalyticsTaskName`""
}

