@echo off
echo ================================================
echo 🚀 HPNT ENG Manager V2.0 안전 서버 시작
echo ================================================

REM 1단계: 기존 프로세스 확인 및 종료
echo [1/4] 기존 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001') do (
    if not "%%a"=="0" (
        echo 기존 프로세스 발견: PID %%a - 종료 중...
        taskkill /F /PID %%a >nul 2>&1
    )
)

REM 2단계: 포트 해제 대기
echo [2/4] 포트 해제 대기 중...
timeout /t 2 /nobreak >nul

REM 3단계: 포트 상태 최종 확인
echo [3/4] 포트 상태 최종 확인...
netstat -ano | findstr :5001 >nul
if %errorlevel% equ 0 (
    echo ❌ 경고: 5001 포트가 아직 사용 중입니다.
    echo 수동으로 프로세스를 종료하고 다시 시도해주세요.
    pause
    exit /b 1
) else (
    echo ✅ 5001 포트가 깨끗합니다.
)

REM 4단계: 새 서버 시작
echo [4/4] 새 서버 시작 중...
echo ================================================
echo 서버 시작됨: http://127.0.0.1:5001/
echo 종료하려면 Ctrl+C를 누르세요.
echo ================================================
python app_new.py

echo.
echo 서버가 종료되었습니다.
pause
