# Visual Stock 백그라운드 작업 런북

기준일시: 2026-02-14 00:30:51  
작업 디렉터리: `c:\Users\nj970\Downloads\OpenCode`

## 1) 오늘 실행한 백그라운드 작업 요약

| 작업 | 실행 대상 | 실행 시간/주기 | 상태 | 핵심 결과 | 산출물 |
|---|---|---|---|---|---|
| AutoQuant 1시간 탐색 | `auto_quant_squad.py` | 60분 (2026-02-13 23:22:29 ~ 2026-02-14 00:22:53) | 완료 | QA 게이트 통과 전략 0건 | `logs/auto_quant_run_20260213_232229.log`, `logs/best_logic_20260213_232229.json` |
| 10분 모니터링 | `monitor_best_logic.py` | 10분 간격 (PID 감시) | 완료 | 10분 단위 요약 기록, 대상 PID 종료 후 자동 중단 | `logs/auto_quant_10min_summary_20260213_232229.log`, `logs/auto_quant_monitor_20260213_232229.out.log` |
| 격리 코드 감사 에이전트 | `continuous_audit_agent.py` (격리 워크트리) | 120초 주기, 총 1시간 | 진행 중 | cycle 20까지 typecheck/test/py_compile 전부 OK | `logs/isolated_audit_checkpoints_20260213_235011.log`, `logs/isolated_audit_results_20260213_235011.json` |
| 오프라인 분산(variance) 리포트 | `strategy_variance_explorer_report.py` | 1회 실행 | 완료 | 후보 130개 점수 재평가, 상위/버킷 리포트 생성 | `logs/strategy_variance_candidates_20260213_235144.csv`, `logs/strategy_variance_summary_20260213_235144.json`, `logs/strategy_variance_report_20260213_235144.md` |

## 2) 오늘 결과 핵심 포인트

1. AutoQuant 결과
- 최종 파일 `logs/best_logic_20260213_232229.json` 기준 `strategies: []`.
- 마지막 상태: `iteration=242334`, `elapsed_seconds=3600.0`.
- 현재 코드 기준 추가 산출물:
  - `logs/best_logic_<TS>_analysis.json`
  - `logs/best_logic_<TS>_analysis.md`
  - 전략 0건이어도 `거절 사유/근접 후보/다음 액션`이 자동 기록됨.

2. 모니터링 결과
- 10분마다 요약 로그 정상 기록.
- `2026-02-14 00:25:09`에 대상 PID 종료 감지 후 모니터 자동 종료.

3. 감사 에이전트 결과(중간)
- `logs/isolated_audit_checkpoints_20260213_235011.log`에서 cycle 1~20 모두 `verdict: OK`.
- typecheck/test/py_compile 실패 없음.

4. 경쟁 서비스 비교/갭 분석
- 정리 문서: `AUDIT_COMPETITIVE_GAP_20260213.md`.
- 무영향 적용 항목 중심으로 정리 완료.

## 3) 재사용 실행 템플릿 (PowerShell)

### A. AutoQuant 1시간 실행 (백그라운드)

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "logs/auto_quant_run_$ts.log"
$err = "logs/auto_quant_run_$ts.err.log"
$json = "logs/best_logic_$ts.json"
$args = @(
  "auto_quant_squad.py",
  "--data-dir","data",
  "--output",$json,
  "--start-date","2021-01-01",
  "--end-date","2025-12-31",
  "--runtime-minutes","60",
  "--batch-size","48",
  "--max-symbols","120",
  "--max-scan-files","1200",
  "--min-bars","400",
  "--seed","7"
)
$p = Start-Process -FilePath python -ArgumentList $args -WorkingDirectory (Get-Location) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
$p.Id
```

AutoQuant 종료 후 확인:

```powershell
Get-Content "logs/best_logic_<SAME_TS>_analysis.md"
Get-Content "logs/best_logic_<SAME_TS>_analysis.json"
```

### B. 10분 단위 모니터링 실행

```powershell
$targetPid = <AUTO_QUANT_PID>
$json = "logs/best_logic_<SAME_TS>.json"
$out = "logs/auto_quant_10min_summary_<SAME_TS>.log"
$monOut = "logs/auto_quant_monitor_<SAME_TS>.out.log"
$monErr = "logs/auto_quant_monitor_<SAME_TS>.err.log"
$args = @(
  "monitor_best_logic.py",
  "--json",$json,
  "--out",$out,
  "--interval-sec","600",
  "--pid",$targetPid
)
Start-Process -FilePath python -ArgumentList $args -WorkingDirectory (Get-Location) -RedirectStandardOutput $monOut -RedirectStandardError $monErr -PassThru
```

### C. 격리 워크트리 감사 에이전트 1시간 실행

```powershell
$main = "C:\Users\nj970\Downloads\OpenCode"
$audit = "C:\Users\nj970\Downloads\OpenCode_audit_agent"
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$ckpt = "$main\logs\isolated_audit_checkpoints_$ts.log"
$json = "$main\logs\isolated_audit_results_$ts.json"
$out = "$main\logs\isolated_audit_stdout_$ts.log"
$err = "$main\logs\isolated_audit_stderr_$ts.log"
$args = @(
  "continuous_audit_agent.py",
  "--repo",$audit,
  "--duration-sec","3600",
  "--interval-sec","120",
  "--checkpoint",$ckpt,
  "--json",$json,
  "--competitor-report","AUDIT_COMPETITIVE_GAP.md"
)
$p = Start-Process -FilePath python -ArgumentList $args -WorkingDirectory $audit -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
$p.PriorityClass = "BelowNormal"
$p.Id
```

### D. 오프라인 분산 리포트 생성

```powershell
python strategy_variance_explorer_report.py --logs-dir logs --top-n 40
```

## 4) 운영 점검 명령

### 프로세스 확인

```powershell
Get-Process python | Select-Object Id,StartTime,PriorityClass,CPU | Sort-Object StartTime
```

### 최근 로그 확인

```powershell
Get-ChildItem logs | Sort-Object LastWriteTime -Descending | Select-Object -First 20 Name,LastWriteTime
```

### 감사 체크포인트 tail

```powershell
Get-Content logs/isolated_audit_checkpoints_<TS>.log -Tail 40
```

## 5) 알려진 이슈와 대응

1. `best_logic_*.json` 파일 접근 경합
- 증상: `WinError 5` 또는 모니터 `parse_error=[Errno 13] Permission denied`.
- 원인: 작성/읽기 타이밍 충돌(Windows 파일 잠금).
- 대응:
  - 모니터는 에러 1회 발생 후 다음 주기에 자동 회복됨.
  - 장기적으로는 `auto_quant_squad.py` 저장 로직에 재시도(retry/backoff) 적용 권장.

2. Next.js 빌드 로그의 `DYNAMIC_SERVER_USAGE`
- `/dashboard`, `/login`, `/recommendations`의 `cookies` 사용으로 발생.
- 현재 빌드 실패 원인은 아님(동적 렌더링 경고 성격).

## 6) 종료/정리 절차

### 특정 PID 종료

```powershell
Stop-Process -Id <PID> -Force
```

### 격리 워크트리 확인

```powershell
git worktree list
```

현재:
- `C:/Users/nj970/Downloads/OpenCode` (`main`)
- `C:/Users/nj970/Downloads/OpenCode_audit_agent` (`audit-agent-20260213`)

## 7) 내일 바로 실행 체크리스트

1. `logs/` 디렉터리 용량/정리 확인.
2. AutoQuant 실행 전 `data/` 업데이트 여부 확인.
3. AutoQuant 시작 후 모니터를 반드시 함께 실행.
4. 감사 에이전트는 항상 격리 워크트리에서만 실행.
5. 실행 종료 후 아래 4개 문서/로그를 묶어서 회고:
- `logs/best_logic_<TS>.json`
- `logs/auto_quant_10min_summary_<TS>.log`
- `logs/isolated_audit_checkpoints_<TS>.log`
- `logs/strategy_variance_report_<TS>.md`
