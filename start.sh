#!/bin/bash
# Render 배포용 시작 스크립트

# 환경 변수 설정
export FLASK_APP=app_new.py
export FLASK_ENV=production

# 데이터베이스 초기화
python app_new.py &

# Gunicorn으로 앱 실행
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app_new:app
