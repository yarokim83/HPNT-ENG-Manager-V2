@echo off
chcp 65001 >nul
echo ============================================================
echo 🧪 HPNT ENG Manager V2.0 - 테스트 데이터베이스 초기화
echo ============================================================
echo.

echo 📁 현재 디렉토리: %CD%
echo.

echo 🔄 기존 데이터베이스 파일 삭제 중...
if exist "material_rq.db" (
    del /f "material_rq.db"
    echo ✅ 루트 디렉토리 DB 파일 삭제 완료
)

if exist "db\material_rq.db" (
    del /f "db\material_rq.db"
    echo ✅ db 폴더 DB 파일 삭제 완료
)

echo.
echo 🚀 테스트 데이터베이스 초기화 시작...
python init_test_db.py

echo.
echo ============================================================
echo 🎯 테스트 데이터베이스 초기화 완료!
echo ============================================================
echo 📁 DB 파일 위치: db\material_rq.db
echo 🌐 서버 실행: python app_new.py
echo 🚀 또는: start_server.bat
echo ============================================================
echo.
pause 