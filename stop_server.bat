@echo off
echo ================================================
echo 🛑 HPNT ENG Manager V2.0 서버 안전 종료
echo ================================================

REM 1단계: 5001 포트 사용 프로세스 확인
echo [1/3] 5001 포트 사용 프로세스 확인 중...
netstat -ano | findstr :5001 > temp_port_check.txt

if %errorlevel% equ 0 (
    echo 발견된 프로세스들:
    type temp_port_check.txt
    echo.
    
    REM 2단계: 프로세스 종료
    echo [2/3] 프로세스 종료 중...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001') do (
        if not "%%a"=="0" (
            echo 프로세스 PID %%a 종료 중...
            taskkill /F /PID %%a >nul 2>&1
            if %errorlevel% equ 0 (
                echo ✅ PID %%a 종료 완료
            ) else (
                echo ⚠️ PID %%a 종료 실패
            )
        )
    )
) else (
    echo ✅ 5001 포트를 사용하는 프로세스가 없습니다.
)

REM 임시 파일 정리
if exist temp_port_check.txt del temp_port_check.txt

REM 3단계: 최종 확인
echo [3/3] 최종 상태 확인...
timeout /t 2 /nobreak >nul
netstat -ano | findstr :5001 >nul
if %errorlevel% equ 0 (
    echo ⚠️ 일부 프로세스가 아직 실행 중일 수 있습니다.
    echo 수동으로 확인해주세요: netstat -ano ^| findstr :5001
) else (
    echo ✅ 모든 프로세스가 정상적으로 종료되었습니다.
)

echo ================================================
echo 서버 종료 완료
echo ================================================
pause
