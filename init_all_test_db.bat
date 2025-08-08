@echo off
chcp 65001 >nul
echo ============================================================
echo 🧪 HPNT ENG Manager V2.0 - 전체 테스트 데이터베이스 초기화
echo ============================================================
echo.

echo 📁 현재 디렉토리: %CD%
echo.

echo 🔄 기존 데이터베이스 파일 삭제 중...
echo.

echo 📂 로컬 DB 파일 삭제...
if exist "material_rq.db" (
    del /f "material_rq.db"
    echo ✅ 루트 디렉토리 DB 파일 삭제 완료
)

if exist "db\material_rq.db" (
    del /f "db\material_rq.db"
    echo ✅ db 폴더 DB 파일 삭제 완료
)

echo.
echo ☁️ OneDrive DB 파일 삭제...
if exist "%USERPROFILE%\OneDrive\HPNT_Manager\db\material_rq.db" (
    del /f "%USERPROFILE%\OneDrive\HPNT_Manager\db\material_rq.db"
    echo ✅ OneDrive DB 파일 삭제 완료
) else (
    echo ℹ️ OneDrive DB 파일이 존재하지 않습니다
)

echo.
echo 🚀 전체 테스트 데이터베이스 초기화 시작...
python init_all_test_db.py

echo.
echo ============================================================
echo 🎯 전체 테스트 데이터베이스 초기화 완료!
echo ============================================================
echo 📁 데이터베이스 위치:
echo   📂 로컬: db\material_rq.db
echo   ☁️ OneDrive: %USERPROFILE%\OneDrive\HPNT_Manager\db\material_rq.db
echo.
echo 🌐 서버 실행: python app_new.py
echo 🚀 또는: start_server.bat
echo.
echo 📝 참고:
echo   - 로컬 환경에서는 OneDrive DB가 우선 사용됩니다
echo   - 클라우드 환경에서는 로컬 DB가 사용됩니다
echo ============================================================
echo.
pause 