@echo off
echo ================================================
echo 🚀 Git 업데이트 시작
echo ================================================

echo.
echo 1단계: Git 상태 확인
git status --porcelain

echo.
echo 2단계: Git add
git add .
if %errorlevel% neq 0 (
    echo ❌ Git add 실패
    pause
    exit /b 1
)
echo ✅ Git add 완료

echo.
echo 3단계: Git commit
git commit -m "feat: 자재요청 관리 시스템 기능 복원 및 iOS 26 디자인 적용"
if %errorlevel% neq 0 (
    echo ⚠️ Git commit 실패 또는 변경사항 없음
)
echo ✅ Git commit 완료

echo.
echo 4단계: Git push
git push origin main
if %errorlevel% neq 0 (
    echo ❌ Git push 실패
    pause
    exit /b 1
)
echo ✅ Git push 완료

echo.
echo ================================================
echo 🎉 Git 업데이트 완료!
echo ================================================
pause
