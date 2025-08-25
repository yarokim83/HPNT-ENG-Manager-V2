#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPNT_ENG_Manager V2.0 - 경량화된 자재관리 시스템
iPad 및 크로스 플랫폼 지원
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, send_from_directory, Response, session, make_response
from werkzeug.utils import secure_filename
import logging
import base64

import sqlite3
import re
# psycopg2 임포트 상태 기록용
_PSYCOPG2_IMPORT_OK = False
_PSYCOPG2_IMPORT_ERR = None
try:
    import psycopg2  # optional: only needed when DATABASE_URL is set
    _PSYCOPG2_IMPORT_OK = True
except Exception as _e:
    psycopg2 = None
    _PSYCOPG2_IMPORT_OK = False
    _PSYCOPG2_IMPORT_ERR = str(_e)
    try:
        logger.warning(f"psycopg2 import failed: {_PSYCOPG2_IMPORT_ERR}")
    except Exception:
        pass

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'hpnt-manager-v2-2025'

# 브라우저 캐시 방지 설정
@app.after_request
def after_request(response):
    """브라우저 캐시 방지 헤더 추가"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    return response

# 버전 정보 (캐시 무효화용)
APP_VERSION = datetime.now().strftime('%Y%m%d_%H%M%S')

def get_app_version():
    """앱 버전 반환 (캐시 무효화용)"""
    return APP_VERSION

# Lightweight health check endpoint (no DB access)
@app.route('/healthz', methods=['GET'])
def healthz():
    """헬스체크: 외부 모니터링/스케줄러가 서비스 생존 여부를 확인할 때 사용"""
    try:
        payload = {
            "status": "ok",
            "version": get_app_version(),
        }
        return jsonify(payload), 200
    except Exception as e:
        # 어떤 오류도 500으로 노출하여 오토리커버 트리거 가능
        return jsonify({"status": "error", "message": str(e)}), 500

# Gunicorn 환경에서 __main__ 블록이 실행되지 않을 수 있어, 최초 요청에 1회 DB 초기화 보장
import threading as _th
_DB_INIT_DONE = False
_DB_INIT_LOCK = _th.Lock()

@app.before_request
def _ensure_db_initialized_once():
    global _DB_INIT_DONE
    if _DB_INIT_DONE:
        return
    with _DB_INIT_LOCK:
        if _DB_INIT_DONE:
            return
        try:
            if init_material_database():
                logger.info("✅ DB 초기화 확인/완료(before_request once)")
            _DB_INIT_DONE = True
        except Exception as e:
            logger.warning(f"⚠️ DB 초기화 시도 실패(before_request once): {e}")
            # 실패해도 요청 처리는 계속 진행

# PostgreSQL 사용 여부 감지 (Render/Neon 등)
DATABASE_URL = os.environ.get('DATABASE_URL')
# 강제 PostgreSQL 모드: 설정 시 어떤 경우에도 SQLite로 폴백하지 않음
_truthy = {"1", "true", "True", "yes", "on"}
FORCE_POSTGRES = str(os.environ.get('FORCE_POSTGRES', '')).strip() in _truthy
USE_POSTGRES = FORCE_POSTGRES or bool(DATABASE_URL)
ADMIN_DEBUG = str(os.environ.get('ADMIN_DEBUG', '')).strip() in _truthy

# sqlite3 스타일의 '?' 플레이스홀더를 psycopg2의 '%s'로 변환하는 어댑터
_qmark_pattern = re.compile(r"\?")
# 진단 로그: Render/Railway 등에서 환경변수 주입 여부 확인
try:
    logger.info(f"USE_POSTGRES={USE_POSTGRES}, FORCE_POSTGRES={FORCE_POSTGRES}, DATABASE_URL set={'yes' if DATABASE_URL else 'no'}")
except Exception:
    pass

class _PgCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        if params is None:
            return self._cursor.execute(query)
        # '?'를 '%s'로 치환 (따옴표 내 '?'는 일반적으로 쿼리에서 사용하지 않으므로 단순 변환)
        converted = _qmark_pattern.sub('%s', query)
        return self._cursor.execute(converted, params)

    def executemany(self, query, seq_of_params):
        converted = _qmark_pattern.sub('%s', query)
        return self._cursor.executemany(converted, seq_of_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class _PgConnectionAdapter:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _PgCursorAdapter(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    # sqlite3와의 호환을 위해 context manager 지원
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False

def _pg_connect_from_env():
    """환경변수에서 PostgreSQL 연결 생성 (강제 모드 지원)"""
    # DATABASE_URL은 Render/Neon 등에서 제공 (postgres:// 또는 postgresql://)
    if psycopg2 is None:
        raise ImportError("psycopg2가 설치되어 있지 않습니다. PostgreSQL 연결을 사용하려면 'psycopg2-binary'가 필요합니다.")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다. FORCE_POSTGRES가 켜져 있으면 반드시 설정되어야 합니다.")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return _PgConnectionAdapter(conn)
    except Exception as e:
        # 강제 모드에서는 실패를 숨기지 않음
        raise

# sqlite3.connect를 그대로 쓰는 기존 코드들을 변경하지 않기 위해 런타임 패치
_real_sqlite_connect = sqlite3.connect
def _smart_connect(db_path):
    # 강제 모드면 반드시 PostgreSQL만 사용
    if USE_POSTGRES:
        return _pg_connect_from_env()
    return _real_sqlite_connect(db_path)

# 이후 코드의 sqlite3.connect 호출이 자동으로 PostgreSQL을 사용하도록 대체
sqlite3.connect = _smart_connect

# 환경 감지
def detect_environment():
    """실행 환경 감지"""
    if (
        os.environ.get('RENDER') or 
        os.environ.get('RAILWAY_ENVIRONMENT') or
        os.environ.get('RAILWAY_PROJECT_ID') or
        (os.environ.get('PORT') and not os.path.exists('C:\\Windows'))
    ):
        return 'cloud'
    elif os.environ.get('RAILWAY_ENVIRONMENT'):
        return 'railway'
    elif sys.platform == 'ios':
        return 'pythonista'
    elif 'iSH' in os.environ.get('SHELL', ''):
        return 'ish'
    elif os.path.exists('/private/var/mobile'):
        return 'a-shell'
    else:
        return 'desktop'

def is_cloud_env():
    """클라우드 환경 여부 확인"""
    # detect_environment() returns 'cloud' for Render/Railway generic cloud envs
    # Include 'cloud' to ensure proper path handling (e.g., images under db/images)
    return detect_environment() in ['cloud', 'render', 'railway']

def get_material_db_path():
    """자재관리 DB 경로 결정 - OneDrive 연동"""
    # PostgreSQL 사용 시에는 경로/폴더 생성 및 로그를 남기지 않음
    if USE_POSTGRES:
        # sqlite3.connect는 어댑터를 통해 PostgreSQL로 대체되므로 경로는 의미 없음
        return os.environ.get('PG_PLACEHOLDER_PATH', '/tmp/pg.sqlite.placeholder')
    
    # 클라우드 환경에서는 앱 디렉토리 하위 db 폴더 사용
    if is_cloud_env():
        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        
        db_folder = os.path.join(current_dir, 'db')
        if not os.path.exists(db_folder):
            os.makedirs(db_folder, exist_ok=True)
            logger.info(f"클라우드 DB 폴더 생성: {db_folder}")
        
        db_path = os.path.join(db_folder, 'material_rq.db')
        logger.info(f"클라우드 DB 경로: {db_path}")
        return db_path
    
    # 로컬 환경에서는 OneDrive 경로 사용
    else:
        # OneDrive 경로 설정
        onedrive_path = os.path.join(os.path.expanduser("~"), "OneDrive", "HPNT_Manager", "db")
        
        # OneDrive db 폴더가 없으면 생성
        if not os.path.exists(onedrive_path):
            os.makedirs(onedrive_path, exist_ok=True)
            logger.info(f"OneDrive DB 폴더 생성: {onedrive_path}")
        
        db_path = os.path.join(onedrive_path, 'material_rq.db')
        logger.info(f"OneDrive DB 경로: {db_path}")
        return db_path

def get_images_dir_path():
    """이미지 폴더 경로 결정 - OneDrive 연동"""
    # 클라우드 환경에서는 기존 로컬 경로 사용
    if is_cloud_env():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(current_dir, 'db', 'images')
        if not os.path.exists(images_dir):
            os.makedirs(images_dir, exist_ok=True)
            logger.info(f"클라우드 이미지 폴더 생성: {images_dir}")
        return images_dir
    
    # 로컬 환경에서는 OneDrive 경로 사용
    else:
        onedrive_images_path = os.path.join(os.path.expanduser("~"), "OneDrive", "HPNT_Manager", "images")
        if not os.path.exists(onedrive_images_path):
            os.makedirs(onedrive_images_path, exist_ok=True)
            logger.info(f"OneDrive 이미지 폴더 생성: {onedrive_images_path}")
        return onedrive_images_path

def create_db_backup():
    """DB 백업 생성 (JSON 형태로 저장)"""
    try:
        db_path = get_material_db_path()
        if not os.path.exists(db_path):
            return None
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 모든 자재요청 데이터 조회
        cursor.execute("SELECT * FROM material_requests ORDER BY id")
        rows = cursor.fetchall()
        
        # 컬럼명 조회
        cursor.execute("PRAGMA table_info(material_requests)")
        columns = [col[1] for col in cursor.fetchall()]
        
        conn.close()
        
        # JSON 형태로 백업 데이터 생성
        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'total_records': len(rows),
            'columns': columns,
            'data': [dict(zip(columns, row)) for row in rows]
        }
        
        return backup_data
        
    except Exception as e:
        logger.error(f"DB 백업 생성 실패: {e}")
        return None

def restore_db_from_backup(backup_data):
    """백업 데이터로부터 DB 복구"""
    try:
        if not backup_data or 'data' not in backup_data:
            return False
        
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 기존 데이터 삭제
        cursor.execute("DELETE FROM material_requests")
        
        # 백업 데이터 복구
        for record in backup_data['data']:
            cursor.execute('''
                INSERT INTO material_requests 
                (id, request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.get('id'),
                record.get('request_date'),
                record.get('item_name'),
                record.get('specifications'),
                record.get('quantity'),
                record.get('urgency'),
                record.get('reason'),
                record.get('vendor'),
                record.get('status'),
                record.get('images'),
                record.get('created_at')
            ))
        
        # 시퀀스 재설정
        max_id = max([record.get('id', 0) for record in backup_data['data']], default=0)
        cursor.execute('DELETE FROM sqlite_sequence WHERE name="material_requests"')
        cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("material_requests", ?)', (max_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ DB 백업 복구 완료: {backup_data['total_records']}개 레코드")
        return True
        
    except Exception as e:
        logger.error(f"DB 백업 복구 실패: {e}")
        return False

def init_material_database():
    """자재관리 DB 초기화 (PostgreSQL 우선, 필요 시 SQLite)"""
    if USE_POSTGRES:
        # PostgreSQL 경로: 로컬 경로/파일 로그를 남기지 않음
        try:
            conn = _pg_connect_from_env()
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS material_requests (
                id SERIAL PRIMARY KEY,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                specifications TEXT,
                reason TEXT,
                urgency TEXT NOT NULL DEFAULT 'normal',
                request_date TEXT NOT NULL,
                vendor TEXT,
                status TEXT DEFAULT 'pending',
                images TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 샘플 데이터 자동 삽입 제거: 재배포 시 DB가 다시 채워지는 것을 방지
            # (의도적으로 아무 것도 하지 않음)

            conn.commit()
            conn.close()
            logger.info("✅ PostgreSQL DB 초기화/확인 완료")
            return True
        except Exception as e:
            # 강제 모드라면 실패를 숨기지 않음 → 예외 그대로 전파
            logger.error(f"❌ PostgreSQL 초기화 실패: {e}")
            if FORCE_POSTGRES:
                raise
            # 비강제 모드에서는 아래 SQLite로 폴백 가능

    # SQLite 경로 (강제 모드가 아니고, USE_POSTGRES가 False일 때만)
    db_path = get_material_db_path()
    db_exists = os.path.exists(db_path)
    
    logger.info(f"DB 경로: {db_path}")
    logger.info(f"DB 파일 존재: {db_exists}")
    
    # 데이터베이스 디렉토리 생성
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"📁 DB 디렉토리 생성: {db_dir}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS material_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            specifications TEXT,
            reason TEXT,
            urgency TEXT NOT NULL DEFAULT 'normal',
            request_date TEXT NOT NULL,
            vendor TEXT,
            status TEXT DEFAULT 'pending',
            images TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 샘플 데이터 자동 삽입 제거: 재배포 시 DB가 다시 채워지는 것을 방지
    if db_exists:
        logger.info(f"✅ 기존 자재관리 DB 연결 완료: {db_path}")
    else:
        logger.info(f"✅ 새 자재관리 DB 초기화 완료: {db_path}")
    
    # (의도적으로 아무 것도 하지 않음)
    
    conn.commit()
    conn.close()
    return True

# HTML 템플릿들
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>HPNT ENG Manager · {{ version }}</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HPNT ENG Manager">
    <meta name="theme-color" content="#007AFF">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="version" content="{{ version }}">
    <style>
        /* === iOS 26 Design System === */
        :root {
            --ios-blue: #007AFF;
            --ios-purple: #5856D6;
            --ios-green: #34C759;
            --ios-orange: #FF9500;
            --ios-red: #FF3B30;
            --ios-light-blue: #5AC8FA;
            --ios-dark: #1C1C1E;
            --ios-light: #F2F2F7;
            --ios-white: #FFFFFF;
            --ios-black: #000000;
            
            --glass-light: rgba(255,255,255,0.25);
            --glass-dark: rgba(0,0,0,0.25);
            --glass-blur: blur(20px);
            --shadow-small: 0 2px 8px rgba(0,0,0,0.1);
            --shadow-medium: 0 4px 16px rgba(0,0,0,0.15);
            --shadow-large: 0 8px 32px rgba(0,0,0,0.2);
            --shadow-glass: 0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2);
            --radius-small: 8px;
            --radius-medium: 16px;
            --radius-large: 24px;
            --radius-xl: 32px;
            --font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
            --font-size-xs: 12px;
            --font-size-sm: 14px;
            --font-size-base: 16px;
            --font-size-lg: 18px;
            --font-size-xl: 20px;
            --font-size-2xl: 24px;
            --font-size-3xl: 30px;
            --font-size-4xl: 36px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }

        body {
            font-family: var(--font-family);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            overflow-x: hidden;
            color: var(--ios-dark);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .glass-container {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: var(--radius-large);
            box-shadow: var(--shadow-glass);
            margin: 20px;
            padding: 0;
            overflow: hidden;
        }

        /* Request header layout fixes for mobile */
        .request-header { gap: 8px; }
        .request-title {
            flex: 1;
            min-width: 0; /* allow shrink */
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 700;
        }
        .request-header .ios-button { flex-shrink: 0; }
        .request-header .ios-badge { flex-shrink: 0; }
        @media (max-width: 420px) {
            .request-header .ios-button {
                padding: 6px 10px;
                min-height: 34px;
                font-size: 13px;
            }
            .request-title { max-width: 58vw; }
        }

        .ios-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 16px 32px;
            border: none;
            border-radius: var(--radius-medium);
            font-family: var(--font-family);
            font-size: var(--font-size-xl);
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            position: relative;
            overflow: hidden;
            min-height: 60px;
            width: 100%;
            margin-bottom: 20px;
        }

        .ios-button:active {
            transform: scale(0.96);
        }

        .ios-button-primary {
            background: linear-gradient(135deg, var(--ios-blue) 0%, var(--ios-purple) 100%);
            color: var(--ios-white);
            box-shadow: var(--shadow-medium);
        }

        .ios-nav {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding: 24px;
            text-align: center;
        }

        .ios-nav-title {
            font-size: var(--font-size-2xl);
            font-weight: 700;
            color: var(--ios-dark);
            margin-bottom: 8px;
        }

        .ios-nav-subtitle {
            color: rgba(0,0,0,0.6);
            font-size: var(--font-size-base);
        }

        .main-content {
            padding: 40px 24px;
            text-align: center;
        }

        /* === iOS 26 Components === */
        .ios-grid {
            display: grid;
            gap: 16px;
            margin-bottom: 24px;
        }

        .ios-grid-2 {
            grid-template-columns: repeat(2, 1fr);
        }

        .ios-grid-3 {
            grid-template-columns: repeat(3, 1fr);
        }

        .ios-grid-4 {
            grid-template-columns: repeat(4, 1fr);
        }

        .ios-card {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: var(--radius-medium);
            padding: 20px;
            text-align: center;
            box-shadow: var(--shadow-glass);
            transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .ios-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-large);
        }

        .ios-card-title {
            font-size: var(--font-size-sm);
            color: rgba(0,0,0,0.6);
            margin-bottom: 8px;
            font-weight: 500;
        }

        .ios-card-value {
            font-size: var(--font-size-2xl);
            font-weight: 700;
            color: var(--ios-dark);
            margin-bottom: 4px;
        }

        .ios-card-subtitle {
            font-size: var(--font-size-xs);
            color: rgba(0,0,0,0.4);
        }

        .ios-dynamic-island {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--ios-dark);
            color: var(--ios-white);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: var(--font-size-sm);
            font-weight: 600;
            z-index: 1000;
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            box-shadow: var(--shadow-medium);
        }

        .ios-dynamic-island.show {
            opacity: 1;
            transform: translateX(-50%) translateY(10px);
        }

        .ios-button-success {
            background: linear-gradient(135deg, var(--ios-green) 0%, #30D158 100%);
            color: var(--ios-white);
            box-shadow: var(--shadow-medium);
        }

        .ios-button-glass {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.2);
            color: var(--ios-dark);
            box-shadow: var(--shadow-glass);
        }

        .ios-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }

        .ios-button:active::before {
            left: 100%;
        }

        /* === Animations === */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        /* startEdit moved to <script> */

        @keyframes scaleIn {
            from {
                opacity: 0;
                transform: scale(0.9);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        .ios-fade-in {
            animation: fadeInUp 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .ios-scale-in {
            animation: scaleIn 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .ios-haptic {
            transition: all 0.1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .ios-haptic:active {
            transform: scale(0.95);
        }

        @media (max-width: 768px) {
            .glass-container {
                margin: 10px;
            }
            
            .ios-nav-title {
                font-size: var(--font-size-xl);
            }
            
            .main-content {
                padding: 30px 20px;
            }

            .ios-grid-2 {
                grid-template-columns: 1fr;
            }

            .ios-grid-3 {
                grid-template-columns: repeat(2, 1fr);
            }

            .ios-grid-4 {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 480px) {
            .ios-grid-3,
            .ios-grid-4 {
                grid-template-columns: 1fr;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .ios-fade-in,
            .ios-scale-in {
                animation: none;
            }
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --ios-dark: #FFFFFF;
                --ios-light: #1C1C1E;
                --glass-light: rgba(0,0,0,0.25);
            }
            
            body {
                background: linear-gradient(135deg, #1C1C1E 0%, #2C2C2E 100%);
            }
        }
    </style>
    <script>
    // Ensure any old Service Workers are unregistered to avoid stale cached JS
    (function(){
      try {
        if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
          navigator.serviceWorker.getRegistrations().then(function(regs){
            regs.forEach(function(r){ r.unregister().catch(()=>{}); });
          }).catch(()=>{});
        }
      } catch (e) { /* ignore */ }
    })();
    // Inline Edit via Double-Click (now inside <script>)
    (function(){
        window.startEdit = function(requestId) {
            try {
                if (window.__isEditing) {
                    console.debug('[startEdit] blocked by global isEditing flag for id=', requestId);
                    return;
                }
                window.__editCooldown = window.__editCooldown || {};
                const now = Date.now();
                const last = window.__editCooldown[requestId] || 0;
                if (now - last < 1500) {
                    console.debug('[startEdit] blocked by cooldown for id=', requestId, 'delta=', now - last);
                    return;
                }
                window.__editCooldown[requestId] = now;
                window.__isEditing = true;
                const cleanup = () => {
                    setTimeout(() => {
                        window.__isEditing = false;
                        console.debug('[startEdit] edit lock released for id=', requestId);
                    }, 600);
                };

                const nameEl = document.getElementById('item-name-' + requestId);
                const qtyEl = document.getElementById('quantity-' + requestId);
                const specsEl = document.getElementById('specs-' + requestId);
                const reasonEl = document.getElementById('reason-' + requestId);

                const currentName = nameEl ? nameEl.textContent.trim() : '';
                const currentQty = qtyEl ? qtyEl.textContent.trim() : '1';
                const currentSpecs = specsEl ? specsEl.textContent.trim() : '';
                const currentReason = reasonEl ? reasonEl.textContent.trim() : '';

                const newName = prompt('자재명을 입력하세요:', currentName);
                if (newName === null) { cleanup(); return; }
                let newQty = prompt('수량을 입력하세요:', currentQty);
                if (newQty === null) { cleanup(); return; }
                newQty = String(newQty).trim();
                if (!/^\d+$/.test(newQty)) {
                    alert('수량은 숫자만 입력 가능합니다.');
                    cleanup();
                    return;
                }
                const newSpecs = prompt('사양(옵션)을 입력하세요:', currentSpecs);
                if (newSpecs === null) { cleanup(); return; }
                const newReason = prompt('사유(옵션)를 입력하세요:', currentReason);
                if (newReason === null) { cleanup(); return; }

                fetch('/admin/edit/' + requestId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        item_name: newName.trim(),
                        quantity: parseInt(newQty, 10),
                        specifications: (newSpecs || '').trim(),
                        reason: (newReason || '').trim()
                    })
                })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        if (nameEl) nameEl.textContent = newName.trim();
                        if (qtyEl) qtyEl.textContent = newQty;
                        if (specsEl) specsEl.textContent = (newSpecs || '').trim();
                        if (reasonEl) reasonEl.textContent = (newReason || '').trim();
                        alert('수정되었습니다.');
                        console.debug('[startEdit] updated DOM for id=', requestId);
                    } else {
                        alert('수정 실패: ' + (d.error || '알 수 없는 오류'));
                        console.warn('[startEdit] server reported failure for id=', requestId, d);
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert('수정 중 오류가 발생했습니다.');
                })
                .finally(() => { cleanup(); });
            } catch (e) {
                console.error(e);
                alert('수정 준비 중 오류가 발생했습니다.');
                try {
                    setTimeout(() => { window.__isEditing = false; }, 600);
                } catch (ignored) {}
            }
        }
    })();
    </script>
</head>
<body>
    <!-- Dynamic Island -->
    <div class="ios-dynamic-island" id="dynamicIsland"></div>
    
    <div class="glass-container ios-fade-in">
        <!-- Navigation Header -->
        <div class="ios-nav">
            <h1 class="ios-nav-title">HPNT ENG Manager</h1>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <!-- Statistics Cards -->
            <div class="ios-grid ios-grid-4 ios-scale-in">
                <div class="ios-card ios-haptic">
                    <div class="ios-card-title">전체 요청</div>
                    <div class="ios-card-value" id="totalRequests">-</div>
                    <div class="ios-card-subtitle">총 요청 수</div>
                </div>
                <div class="ios-card ios-haptic">
                    <div class="ios-card-title">대기 중</div>
                    <div class="ios-card-value" id="pendingRequests">-</div>
                    <div class="ios-card-subtitle">승인 대기</div>
                </div>
                <div class="ios-card ios-haptic">
                    <div class="ios-card-title">진행 중</div>
                    <div class="ios-card-value" id="inProgressRequests">-</div>
                    <div class="ios-card-subtitle">처리 중</div>
                </div>
                <div class="ios-card ios-haptic">
                    <div class="ios-card-title">완료</div>
                    <div class="ios-card-value" id="completedRequests">-</div>
                    <div class="ios-card-subtitle">처리 완료</div>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="ios-scale-in">
                <a href="/requests?v={{ version }}" class="ios-button ios-button-primary ios-haptic">
                    📋 자재요청 목록
                </a>
                
                <!-- 보안 게이트 버튼 (사용자 클릭) -->
                <button id="featureAccessBtn" type="button" class="ios-button ios-button-glass ios-haptic">
                    🧠 신규기능 (AI 검색)
                </button>
                <!-- 실제 위젯 트리거는 숨김 처리 -->
                <button id="searchWidgetRealTrigger" type="button" style="display:none"></button>
            </div>

            

            <!-- Refresh Button -->
            <button onclick="refreshData()" class="ios-button ios-button-glass ios-haptic" style="margin-top: 16px;">
                🔄 새로고침
            </button>
        </div>
    </div>
    
    <script>
        // Prevent inline handler ReferenceError by ensuring global binding after DOM ready
        (function(){
            if (typeof window.copyRequest === 'undefined') {
                window.copyRequest = function(){ console.warn('copyRequest not ready'); };
            }
            if (typeof window.updateRequest === 'undefined') {
                window.updateRequest = function(){ console.warn('updateRequest not ready'); };
            }
            if (typeof window.deleteRequest === 'undefined') {
                window.deleteRequest = function(){ console.warn('deleteRequest not ready'); };
            }
            if (typeof window.onPickImage === 'undefined') {
                window.onPickImage = function(){ console.warn('onPickImage not ready'); };
            }
            if (typeof window.deleteImage === 'undefined') {
                window.deleteImage = function(){ console.warn('deleteImage not ready'); };
            }
        })();
        // PWA 등록 (옵트인: ?sw=1 일 때만 등록)
        if ('serviceWorker' in navigator) {
            const swParam = new URLSearchParams(location.search).get('sw');
            if (swParam === '1') {
                navigator.serviceWorker.register('/sw.js')
                    .then(reg => console.log('SW registered'))
                    .catch(err => console.log('SW registration failed'));
            } else {
                // 기본은 등록 해제(기존 등록분이 있으면 제거)
                if (navigator.serviceWorker.getRegistrations) {
                    navigator.serviceWorker.getRegistrations()
                        .then(regs => regs.forEach(r => r.unregister().catch(()=>{})))
                        .catch(()=>{});
                }
                console.log('SW not registered (add ?sw=1 to enable)');
            }
        }

        // === iOS 26 JavaScript Functions ===
        
        // 햅틱 피드백 시뮬레이션
        function hapticFeedback() {
            if (navigator.vibrate) {
                navigator.vibrate(10);
            }
        }

        // 다이나믹 아일랜드 표시
        function showDynamicIsland(message, duration = 3000) {
            const island = document.getElementById('dynamicIsland');
            island.textContent = message;
            island.classList.add('show');
            
            setTimeout(() => {
                island.classList.remove('show');
            }, duration);
        }

        // 페이지 로드 애니메이션
        function pageLoadAnimation() {
            const elements = document.querySelectorAll('.ios-fade-in, .ios-scale-in');
            elements.forEach((el, index) => {
                setTimeout(() => {
                    el.style.opacity = '1';
                }, index * 100);
            });
        }

        // 통계 데이터 로드
        async function loadStats() {
            try {
                const response = await fetch('/api/stats?v={{ version }}');
                const data = await response.json();
                
                const totalEl = document.getElementById('totalRequests');
                if (totalEl) totalEl.textContent = data.total || 0;
                const pendingEl = document.getElementById('pendingRequests');
                if (pendingEl) pendingEl.textContent = data.pending || 0;
                const progEl = document.getElementById('inProgressRequests');
                if (progEl) progEl.textContent = data.in_progress || 0;
                const compEl = document.getElementById('completedRequests');
                if (compEl) compEl.textContent = data.completed || 0;
                
                // 환경 정보 업데이트
                const envEl = document.getElementById('environment');
                if (envEl) envEl.textContent = data.environment || '로컬';
                const dbEl = document.getElementById('database');
                if (dbEl) dbEl.textContent = data.database || 'SQLite';
                
                showDynamicIsland('✅ 데이터 로드 완료');
            } catch (error) {
                console.error('통계 로드 실패:', error);
                showDynamicIsland('❌ 데이터 로드 실패');
            }
        }

        // 데이터 새로고침
        function refreshData() {
            hapticFeedback();
            showDynamicIsland('🔄 새로고침 중...');
            loadStats();
        }

        // 모든 버튼에 햅틱 피드백 추가
        function addHapticFeedback() {
            const buttons = document.querySelectorAll('.ios-haptic');
            buttons.forEach(button => {
                button.addEventListener('click', hapticFeedback);
            });
        }

        // 페이지 로드 시 초기화
        document.addEventListener('DOMContentLoaded', function() {
            pageLoadAnimation();
            addHapticFeedback();
            loadStats();
            
            // 다이나믹 아일랜드 초기 메시지
            setTimeout(() => {
                showDynamicIsland('HPNT ENG Manager V2.0');
            }, 500);

            // 신규 기능 보안 게이트: 비밀번호 확인 후 위젯 오픈
            const accessBtn = document.getElementById('featureAccessBtn');
            const realTrigger = document.getElementById('searchWidgetRealTrigger');
            if (accessBtn && realTrigger) {
                accessBtn.addEventListener('click', async () => {
                    try {
                        const msg = [
                            '신규 기능 접근 비밀번호를 입력하세요',
                            '',
                            'Render 설정 방법:',
                            'Dashboard > Services > 해당 서비스 > Environment 탭 > Add Environment Variable',
                            'Key: FEATURE_PASSWORD, Value: 원하는 비밀번호'
                        ].join('\\n');
                        const pwd = prompt(msg);
                        if (pwd === null) return; // 취소
                        const resp = await fetch('/feature-auth', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ password: pwd })
                        });
                        const data = await resp.json().catch(() => ({}));
                        if (resp.ok && data && data.success) {
                            // 인증 성공: 위젯 스크립트를 지연 로드 후 위젯 생성 및 트리거
                            const ensureWidgetLoaded = () => new Promise((resolve, reject) => {
                                try {
                                    if (window.customElements && window.customElements.get && window.customElements.get('gen-search-widget')) {
                                        resolve();
                                        return;
                                    }
                                    const existing = document.querySelector('script[data-gen-app-builder]');
                                    if (existing) {
                                        existing.addEventListener('load', () => resolve());
                                        existing.addEventListener('error', () => reject(new Error('위젯 스크립트 로드 실패')));
                                        return;
                                    }
                                    const s = document.createElement('script');
                                    s.async = true;
                                    s.src = 'https://cloud.google.com/ai/gen-app-builder/client?hl=ko';
                                    s.setAttribute('data-gen-app-builder', '1');
                                    s.onload = () => resolve();
                                    s.onerror = () => reject(new Error('위젯 스크립트 로드 실패'));
                                    document.head.appendChild(s);
                                } catch (err) { reject(err); }
                            });

                            await ensureWidgetLoaded();

                            // 위젯 요소가 없으면 동적으로 추가
                            let widget = document.querySelector('gen-search-widget');
                            if (!widget) {
                                widget = document.createElement('gen-search-widget');
                                widget.setAttribute('configId', 'dfa50f94-fdb2-4b07-81bb-433c1844f9d1');
                                widget.setAttribute('triggerId', 'searchWidgetRealTrigger');
                                document.body.appendChild(widget);
                            }
                            // 실제 트리거 클릭으로 위젯 열기
                            realTrigger.click();
                        } else {
                            try {
                                if (resp.status === 401) {
                                    alert('비밀번호가 올바르지 않습니다.');
                                } else if (resp.status >= 500) {
                                    alert('서버 오류가 발생했습니다. 잠시 후 다시 시도하세요.');
                                } else {
                                    alert('요청이 처리되지 않았습니다. 네트워크 또는 보안 설정을 확인하세요.');
                                }
                                console.warn('[feature-auth] status=', resp.status, 'data=', data);
                            } catch (ignored) {
                                alert('요청 처리 중 알 수 없는 오류가 발생했습니다.');
                            }
                        }
                    } catch (e) {
                        console.error(e);
                        alert('인증 중 오류가 발생했습니다.');
                    }
                });
            }
        });

        // 페이지 가시성 변경 시 데이터 새로고침
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                loadStats();
            }
        });
    </script>
    <!-- Vertex AI Search Widget Integration: 동적 로드 (인증 후) -->
</body>
</html>
'''

# 안전 모드 홈 (스크립트 최소화, 파싱 오류 진단용)
SAFE_HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HPNT ENG Manager - Safe</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; max-width: 680px; margin: 0 auto }
    .row { margin: 12px 0 }
    .btn { padding: 10px 14px; border-radius: 10px; border: 1px solid #ccc; background:#f7f7f7; cursor:pointer }
  </style>
  <script>
    window.addEventListener('DOMContentLoaded', function(){
      console.log('[SAFE_HOME] loaded OK');
      document.getElementById('aiBtn').addEventListener('click', function(){
        alert('AI 기능은 안전 모드에서 비활성화되었습니다. URL의 ?safe=1을 제거해주세요.');
      });
    });
  </script>
  <!-- 안전 모드: 외부 스크립트/스타일 없음 -->
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"> 
  
  
</head>
<body>
  <div class="card">
    <h2>HPNT ENG Manager - Safe Mode</h2>
    <div class="row">이 페이지는 파싱 오류 진단을 위한 최소 구성입니다.</div>
    <div class="row">
      <a class="btn" href="/">일반 모드로 이동</a>
      <button id="aiBtn" class="btn">🧠 신규기능 (AI 검색)</button>
      <a class="btn" href="/requests">📋 자재요청 목록</a>
    </div>
  </div>
</body>
</html>
'''

REQUESTS_TEMPLATE = r'''
<!DOCTYPE html>                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>📋 자재요청 목록 - HPNT Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HPNT Manager">
    <meta name="theme-color" content="#007AFF">
    <style>
        /* === iOS 26 Design System === */
        :root {
            /* iOS 26 Color Palette */
            --ios-blue: #007AFF;
            --ios-purple: #5856D6;
            --ios-green: #34C759;
            --ios-orange: #FF9500;
            --ios-red: #FF3B30;
            --ios-light-blue: #5AC8FA;
            --ios-dark: #1C1C1E;
            --ios-light: #F2F2F7;
            --ios-white: #FFFFFF;
            --ios-black: #000000;
            
            /* Glass Effects */
            --glass-light: rgba(255,255,255,0.25);
            --glass-dark: rgba(0,0,0,0.25);
            --glass-blur: blur(20px);
            
            /* Shadows */
            --shadow-small: 0 2px 8px rgba(0,0,0,0.1);
            --shadow-medium: 0 4px 16px rgba(0,0,0,0.15);
            --shadow-large: 0 8px 32px rgba(0,0,0,0.2);
            --shadow-glass: 0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2);
            
            /* Border Radius */
            --radius-small: 8px;
            --radius-medium: 16px;
            --radius-large: 24px;
            --radius-xl: 32px;
            
            /* Typography */
            --font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
            --font-size-xs: 12px;
            --font-size-sm: 14px;
            --font-size-base: 16px;
            --font-size-lg: 18px;
            --font-size-xl: 20px;
            --font-size-2xl: 24px;
            --font-size-3xl: 32px;
            --font-size-4xl: 48px;
        }

        /* === Global Reset === */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }

        body {
            font-family: var(--font-family);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            overflow-x: hidden;
            color: var(--ios-dark);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* === iOS 26 Glass Morphism === */
        .glass-container {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: var(--radius-large);
            box-shadow: var(--shadow-glass);
            margin: 20px;
            padding: 0;
            overflow: hidden;
        }

        .glass-card {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: var(--radius-medium);
            box-shadow: var(--shadow-medium);
            transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .glass-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-large);
            border-color: rgba(255,255,255,0.4);
        }

        /* === iOS 26 Buttons === */
        .ios-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 12px 24px;
            border: none;
            border-radius: var(--radius-medium);
            font-family: var(--font-family);
            font-size: var(--font-size-base);
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            position: relative;
            overflow: hidden;
            min-height: 44px; /* iOS Touch Target */
        }

        .ios-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }

        .ios-button:hover::before {
            left: 100%;
        }

        .ios-button:active {
            transform: scale(0.96);
        }

        .ios-button-primary {
            background: linear-gradient(135deg, var(--ios-blue) 0%, var(--ios-purple) 100%);
            color: var(--ios-white);
            box-shadow: var(--shadow-medium);
        }

        .ios-button-success {
            background: linear-gradient(135deg, var(--ios-green) 0%, #30D158 100%);
            color: var(--ios-white);
            box-shadow: var(--shadow-medium);
        }

        .ios-button-glass {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.3);
            color: var(--ios-dark);
            box-shadow: var(--shadow-glass);
        }

        /* === iOS 26 Navigation === */
        .ios-nav {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding: 16px 24px;
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .ios-nav-title {
            font-size: var(--font-size-2xl);
            font-weight: 700;
            color: var(--ios-dark);
            text-align: center;
        }

        /* === iOS 26 Form Elements === */
        .ios-input {
            width: 100%;
            padding: 16px 20px;
            border: 2px solid rgba(0,0,0,0.1);
            border-radius: var(--radius-medium);
            font-family: var(--font-family);
            font-size: var(--font-size-base);
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            color: var(--ios-dark);
            transition: all 0.3s ease;
            outline: none;
        }

        .ios-input:focus {
            border-color: var(--ios-blue);
            box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
            background: rgba(255,255,255,0.3);
        }

        .ios-select {
            width: 100%;
            padding: 16px 20px;
            border: 2px solid rgba(0,0,0,0.1);
            border-radius: var(--radius-medium);
            font-family: var(--font-family);
            font-size: var(--font-size-base);
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            color: var(--ios-dark);
            transition: all 0.3s ease;
            outline: none;
            cursor: pointer;
        }

        .ios-select:focus {
            border-color: var(--ios-blue);
            box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
            background: rgba(255,255,255,0.3);
        }

        /* === iOS 26 Cards === */
        .ios-card {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: var(--radius-large);
            padding: 24px;
            box-shadow: var(--shadow-medium);
            transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            margin-bottom: 16px;
        }

        .ios-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-large);
        }

        /* === iOS 26 Status Badges === */
        .ios-badge {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: var(--radius-small);
            font-size: var(--font-size-sm);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .ios-badge-pending {
            background: rgba(255,149,0,0.2);
            color: var(--ios-orange);
            border: 1px solid rgba(255,149,0,0.3);
        }

        .ios-badge-approved {
            background: rgba(52,199,89,0.2);
            color: var(--ios-green);
            border: 1px solid rgba(52,199,89,0.3);
        }

        .ios-badge-ordered {
            background: rgba(0,122,255,0.2);
            color: var(--ios-blue);
            border: 1px solid rgba(0,122,255,0.3);
        }

        .ios-badge-received {
            background: rgba(88,86,214,0.2);
            color: var(--ios-purple);
            border: 1px solid rgba(88,86,214,0.3);
        }

        .ios-badge-rejected {
            background: rgba(255,59,48,0.2);
            color: var(--ios-red);
            border: 1px solid rgba(255,59,48,0.3);
        }

        /* === iOS 26 Grid System === */
        .ios-grid {
            display: grid;
            gap: 20px;
        }

        .ios-grid-2 {
            grid-template-columns: repeat(2, 1fr);
        }

        .ios-grid-3 {
            grid-template-columns: repeat(3, 1fr);
        }

        .ios-grid-4 {
            grid-template-columns: repeat(4, 1fr);
        }

        /* === iOS 26 Animations === */
        @keyframes ios-fade-in {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes ios-scale-in {
            from {
                opacity: 0;
                transform: scale(0.9);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        .ios-fade-in {
            animation: ios-fade-in 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .ios-scale-in {
            animation: ios-scale-in 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        /* === iOS 26 Haptic Feedback Simulation === */
        .ios-haptic {
            transition: transform 0.1s ease;
        }

        .ios-haptic:active {
            transform: scale(0.95);
        }

        /* === iOS 26 Responsive Design === */
        @media (max-width: 768px) {
            .ios-grid-2,
            .ios-grid-3,
            .ios-grid-4 {
                grid-template-columns: 1fr;
            }
            
            .ios-card {
                padding: 20px;
            }
            
            .ios-button {
                width: 100%;
                margin-bottom: 12px;
            }
            
            .ios-nav-title {
                font-size: var(--font-size-xl);
            }
            
            .glass-container {
                margin: 10px;
            }
            
            .search-controls {
                flex-direction: column;
                gap: 12px;
            }
        }

        @media (max-width: 480px) {
            .ios-card {
                padding: 16px;
                border-radius: var(--radius-medium);
            }
            
            .ios-input,
            .ios-select {
                padding: 14px 16px;
                font-size: var(--font-size-base);
            }
        }

        /* === iOS 26 Dark Mode Support === */
        @media (prefers-color-scheme: dark) {
            :root {
                --ios-dark: #FFFFFF;
                --ios-light: #1C1C1E;
                --glass-light: rgba(0,0,0,0.25);
                --glass-dark: rgba(255,255,255,0.25);
            }
            
            body {
                background: linear-gradient(135deg, #1C1C1E 0%, #2C2C2E 100%);
            }
            
            .ios-input,
            .ios-select {
                color: var(--ios-white);
                background: var(--glass-dark);
            }
            
            .ios-input:focus,
            .ios-select:focus {
                background: rgba(0,0,0,0.3);
            }
        }

        /* === iOS 26 Accessibility === */
        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }

        /* === iOS 26 Focus Indicators === */
        .ios-button:focus-visible,
        .ios-input:focus-visible,
        .ios-select:focus-visible {
            outline: 2px solid var(--ios-blue);
            outline-offset: 2px;
        }

        /* === Search Controls === */
        .search-controls {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            align-items: center;
            flex-wrap: wrap;
        }

        .search-controls form {
            display: flex;
            gap: 12px;
            flex: 1;
            align-items: center;
        }

        /* === Request Card Content === */
        .request-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            gap: 12px;
        }

        .request-title {
            font-size: var(--font-size-lg);
            font-weight: 600;
            color: var(--ios-dark);
            flex: 1;
        }

        .request-details {
            display: grid;
            gap: 8px;
            margin-bottom: 16px;
        }

        .detail-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: var(--font-size-sm);
            color: rgba(0,0,0,0.7);
        }

        .detail-label {
            font-weight: 600;
            min-width: 60px;
        }

        .request-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .request-actions .ios-button {
            font-size: var(--font-size-sm);
            padding: 8px 16px;
            min-height: 36px;
        }

        /* === Request Image === */
        .request-image { margin: 12px 0; }
        .request-image-thumb {
            max-width: 100%;
            border-radius: var(--radius-small);
            box-shadow: var(--shadow-small);
        }

        /* === Empty State === */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: rgba(0,0,0,0.6);
        }

        .empty-state h3 {
            font-size: var(--font-size-xl);
            margin-bottom: 12px;
            color: var(--ios-dark);
        }

        .empty-state p {
            font-size: var(--font-size-base);
            margin-bottom: 24px;
        }

        /* === Status Dashboard === */
        .status-dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }

        .status-card {
            background: var(--glass-light);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: var(--radius-medium);
            padding: 16px;
            text-align: center;
            transition: all 0.3s ease;
        }

        .status-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-medium);
        }

        .status-number {
            font-size: var(--font-size-2xl);
            font-weight: 700;
            margin-bottom: 4px;
        }

        .status-label {
            font-size: var(--font-size-sm);
            color: rgba(0,0,0,0.7);
            font-weight: 600;
        }

        .status-total .status-number { color: var(--ios-blue); }
        .status-pending .status-number { color: var(--ios-orange); }
        .status-approved .status-number { color: var(--ios-green); }
        .status-ordered .status-number { color: var(--ios-blue); }
        .status-received .status-number { color: var(--ios-purple); }
        .status-rejected .status-number { color: var(--ios-red); }
    </style>
</head>
<body>
    <script>
        // Early minimal implementations to survive later script parse failures
        (function(){
            if (!window.updateRequest) {
                window.updateRequest = function(requestId){
                    try {
                        const vendorEl = document.getElementById('vendor-' + requestId);
                        const statusEl = document.getElementById('status-' + requestId);
                        const vendor = vendorEl ? vendorEl.value : '';
                        const status = statusEl ? statusEl.value : 'pending';
                        fetch('/admin/update/' + requestId, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ vendor, status })
                        })
                        .then(r => r.json())
                        .then(d => {
                            if (d && d.success) {
                                alert('저장되었습니다.');
                                location.reload();
                            } else {
                                alert('저장 실패: ' + ((d && d.error) || '알 수 없는 오류'));
                            }
                        })
                        .catch(err => { console.error(err); alert('저장 중 오류가 발생했습니다.'); });
                    } catch (e) {
                        console.error(e);
                        alert('페이지 스크립트 로드 오류로 저장을 수행할 수 없습니다. 새로고침 해주세요.');
                    }
                };
            }
            if (!window.copyRequest) {
                window.copyRequest = function(requestId){
                    try {
                        if (!confirm('이 요청을 복사하시겠습니까?')) return;
                        fetch('/admin/copy/' + requestId, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        })
                        .then(r => r.json())
                        .then(d => {
                            if (d && d.success) { alert('요청이 복사되었습니다!'); location.reload(); }
                            else { alert('복사 실패: ' + ((d && d.error) || '알 수 없는 오류')); }
                        })
                        .catch(err => { console.error(err); alert('복사 중 오류가 발생했습니다.'); });
                    } catch (e) {
                        console.error(e);
                        alert('페이지 스크립트 로드 오류로 복사를 수행할 수 없습니다. 새로고침 해주세요.');
                    }
                };
            }
            if (!window.deleteRequest) {
                window.deleteRequest = function(requestId){
                    try {
                        if (!confirm('이 요청을 삭제하시겠습니까?' + '\\n\\n' + '이 작업은 되돌릴 수 없습니다.')) return;
                        fetch('/admin/delete/' + requestId, {
                            method: 'DELETE',
                            headers: { 'Content-Type': 'application/json' }
                        })
                        .then(r => r.json())
                        .then(d => {
                            if (d && d.success) { alert('요청이 삭제되었습니다!'); location.reload(); }
                            else { alert('삭제 실패: ' + ((d && d.error) || '알 수 없는 오류')); }
                        })
                        .catch(err => { console.error(err); alert('삭제 중 오류가 발생했습니다.'); });
                    } catch (e) {
                        console.error(e);
                        alert('페이지 스크립트 로드 오류로 삭제를 수행할 수 없습니다. 새로고침 해주세요.');
                    }
                };
            }
        })();
    </script>
    <!-- Image Preview Modal -->
    <div id="imgPreview" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:9999; align-items:center; justify-content:center;">
        <div style="position:relative; max-width:95%; max-height:95%;">
            <img id="imgPreviewImg" src="" alt="미리보기" referrerpolicy="no-referrer" style="max-width:100%; max-height:100%; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
            <button type="button" onclick="closePreview()" style="position:absolute; top:-10px; right:-10px; background:#fff; border:none; border-radius:999px; width:36px; height:36px; box-shadow:0 2px 10px rgba(0,0,0,0.3); cursor:pointer;">✕</button>
        </div>
    </div>
    <div class="glass-container">
        <!-- iOS 26 Navigation -->
        <div class="ios-nav">
            <h1 class="ios-nav-title">📋 자재요청 목록</h1>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 32px;">
            <!-- Search Controls -->
            <div class="search-controls">
                <a href="/" class="ios-button ios-button-glass ios-haptic">
                    🏠 홈으로
                </a>
                <a href="/add" class="ios-button ios-button-success ios-haptic">
                    ➕ 새 요청
                </a>
                {% if admin_debug %}
                <a href="/admin/db/download" class="ios-button ios-button-glass ios-haptic" title="DB를 JSON으로 내보내기">
                    ⬇️ DB 내보내기
                </a>
                {% endif %}
                
                <form method="GET" style="flex: 1;">
                    <input type="text" name="search" class="ios-input" 
                           placeholder="🔍 자재명, 사양, 사유로 검색..." 
                           value="{{ search_query }}">
                    
                    <select name="status" class="ios-select" onchange="this.form.submit()">
                        <option value="all" {% if status_filter == 'all' %}selected{% endif %}>전체 상태</option>
                        <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>대기중</option>
                        <option value="approved" {% if status_filter == 'approved' %}selected{% endif %}>승인됨</option>
                        <option value="ordered" {% if status_filter == 'ordered' %}selected{% endif %}>발주됨</option>
                        <option value="received" {% if status_filter == 'received' %}selected{% endif %}>입고됨</option>
                        <option value="rejected" {% if status_filter == 'rejected' %}selected{% endif %}>반려됨</option>
                    </select>
                    
                    <button type="submit" class="ios-button ios-button-primary ios-haptic">
                        검색
                    </button>
                </form>
            </div>
            
            <!-- Status Dashboard -->
            <div class="status-dashboard">
                <div class="status-card status-total ios-scale-in">
                    <div class="status-number">{{ total_count }}</div>
                    <div class="status-label">전체</div>
                </div>
                <div class="status-card status-pending ios-scale-in">
                    <div class="status-number">{{ status_counts.get('pending', 0) }}</div>
                    <div class="status-label">대기중</div>
                </div>
                <div class="status-card status-approved ios-scale-in">
                    <div class="status-number">{{ status_counts.get('approved', 0) }}</div>
                    <div class="status-label">승인됨</div>
                </div>
                <div class="status-card status-ordered ios-scale-in">
                    <div class="status-number">{{ status_counts.get('ordered', 0) }}</div>
                    <div class="status-label">발주됨</div>
                </div>
                <div class="status-card status-received ios-scale-in">
                    <div class="status-number">{{ status_counts.get('received', 0) }}</div>
                    <div class="status-label">입고됨</div>
                </div>
                <div class="status-card status-rejected ios-scale-in">
                    <div class="status-number">{{ status_counts.get('rejected', 0) }}</div>
                    <div class="status-label">반려됨</div>
                </div>
            </div>
            
            {% if requests %}
            <!-- Request Cards -->
            <div class="requests-list">
                {% for req in requests %}
                <div class="ios-card ios-fade-in request-card" data-request-id="{{ req[0] }}" data-status="{{ req[8] }}" title="상단 편집 버튼으로 수정">
                    <div class="request-header" style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                        <div class="request-title" id="item-name-{{ req[0] }}">{{ req[1] }}</div>
                        <div class="ios-badge ios-badge-{{ req[8] }}">
                            {% if req[8] == 'pending' %}대기중
                            {% elif req[8] == 'approved' %}승인됨
                            {% elif req[8] == 'ordered' %}발주됨
                            {% elif req[8] == 'received' %}입고됨
                            {% elif req[8] == 'rejected' %}반려됨
                            {% endif %}
                        </div>
                        <button type="button" class="ios-button ios-button-glass ios-haptic" style="padding:6px 10px; min-height:36px; font-size:14px;" onclick="startEdit({{ req[0] }})" ondblclick="event.preventDefault(); event.stopPropagation(); return false;">편집</button>
                    </div>
                    
                    <div class="request-details">
                        <div class="detail-item">
                            <span class="detail-label">📦 수량:</span>
                            <span id="quantity-{{ req[0] }}">{{ req[2] }}</span>개
                        </div>
                        {% if req[3] %}
                        <div class="detail-item">
                            <span class="detail-label">📋 사양:</span>
                            <span id="specs-{{ req[0] }}">{{ req[3] }}</span>
                        </div>
                        {% endif %}
                        {% if req[4] %}
                        <div class="detail-item">
                            <span class="detail-label">📝 사유:</span>
                            <span id="reason-{{ req[0] }}">{{ req[4] }}</span>
                        </div>
                        {% endif %}
                        {% if req[7] %}
                        <div class="detail-item">
                            <span class="detail-label">🏢 업체:</span>
                            <span>{{ req[7] }}</span>
                        </div>
                        {% endif %}
                        <div class="detail-item">
                            <span class="detail-label">⚡ 긴급도:</span>
                            <span>
                                {% if req[5] == 'high' %}🔴 높음
                                {% elif req[5] == 'normal' %}🟡 보통
                                {% else %}🟢 낮음
                                {% endif %}
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">📅 등록일:</span>
                            <span>{{ req[10] }}</span>
                        </div>
                    </div>
                 
                 <!-- Inline Vendor/Status Editor -->
                 <div class="ios-grid ios-grid-2" style="margin-bottom: 12px;">
                     <input id="vendor-{{ req[0] }}" type="text" class="ios-input" placeholder="발주업체"
                            value="{{ req[7] or '' }}">
                     <select id="status-{{ req[0] }}" class="ios-select">
                         <option value="pending" {% if req[8] == 'pending' %}selected{% endif %}>대기중</option>
                         <option value="approved" {% if req[8] == 'approved' %}selected{% endif %}>승인됨</option>
                         <option value="ordered" {% if req[8] == 'ordered' %}selected{% endif %}>발주됨</option>
                         <option value="received" {% if req[8] == 'received' %}selected{% endif %}>입고됨</option>
                         <option value="rejected" {% if req[8] == 'rejected' %}selected{% endif %}>반려됨</option>
                     </select>
                 </div>
                    <!-- Image Section -->
                    <div class="request-image">
                        {% if req[9] %}
                        {% set img_url = req[9] if req[9].startswith('http') else '/images/' + req[9] %}
                        <img src="{{ img_url }}" class="request-image-thumb" alt="이미지" referrerpolicy="no-referrer" onerror="(function(img, url, raw){ try { img.onerror = function(){ try { img.onerror=null; var a=document.createElement('a'); a.href = (raw||url); a.textContent='링크 클릭'; a.target='_blank'; a.rel='noopener noreferrer'; img.replaceWith(a); } catch(_e) { img.onerror=null; img.replaceWith(document.createTextNode('링크 클릭: ' + (raw||url))); } }; img.src = '/proxy-img?u=' + encodeURIComponent(url); } catch(e){ try { img.onerror=null; var a=document.createElement('a'); a.href=(raw||url); a.textContent='링크 클릭'; a.target='_blank'; a.rel='noopener noreferrer'; img.replaceWith(a); } catch(_e2) { img.onerror=null; img.replaceWith(document.createTextNode('링크 클릭: ' + (raw||url))); } })(this, '{{ img_url }}', '{{ req[9] }}');">
                        <div class="detail-item" style="margin-top:4px; color:#666; font-size:12px;">
                            {% if req[9].startswith('http') %}
                                이미지 URL: <a href="{{ req[9] }}" target="_blank" rel="noopener noreferrer">{{ req[9] }}</a>
                            {% else %}
                                파일명: <a href="/images/{{ req[9] }}" target="_blank" rel="noopener noreferrer">{{ req[9] }}</a>
                            {% endif %}
                        </div>
                        <div class="request-actions" style="margin-top: 8px;">
                            <button type="button" onclick="deleteImage({{ req[0] }})" class="ios-button ios-button-glass ios-haptic">이미지 삭제</button>
                        </div>
                        {% else %}
                        <div class="detail-item">🖼️ 이미지 없음</div>
                        {% endif %}
                        <div style="margin-top: 8px;">
                            <input type="file" accept="image/*" onchange="onPickImage({{ req[0] }}, this)">
                        </div>
                        <div style="margin-top: 8px; display:flex; gap:6px; align-items:center;">
                            <input id="img-url-{{ req[0] }}" type="url" placeholder="https:// 예) 외부 이미지 URL 붙여넣기" style="flex:1; padding:8px; border:1px solid #ddd; border-radius:8px;">
                            <button type="button" onclick="setImageUrl({{ req[0] }})" class="ios-button ios-button-glass ios-haptic">외부 URL로 연결</button>
                        </div>
                    </div>

                    <div class="request-actions">
                     <button type="button" onclick="updateRequest({{ req[0] }})" class="ios-button ios-button-success ios-haptic">
                         저장
                     </button>
                        
                        <button type="button" onclick="copyRequest({{ req[0] }})" class="ios-button ios-button-glass ios-haptic">
                            복사
                        </button>
                        <button type="button" onclick="deleteRequest({{ req[0] }})" class="ios-button ios-button-glass ios-haptic">
                            삭제
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <!-- Empty State -->
            <div class="empty-state ios-fade-in">
                <h3>📭 등록된 자재요청이 없습니다</h3>
                <p>새로운 자재요청을 등록해보세요!</p>
                <a href="/add" class="ios-button ios-button-success ios-haptic">
                    ➕ 첫 요청 등록하기
                </a>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        // iOS 26 Haptic Feedback Simulation
        function iosHapticFeedback() {
            if (navigator.vibrate) {
                navigator.vibrate(10);
            }
        }
        
        // Add haptic feedback to all interactive elements
        document.querySelectorAll('.ios-haptic').forEach(element => {
            element.addEventListener('touchstart', iosHapticFeedback);
            element.addEventListener('click', iosHapticFeedback);
        });
        
        // Copy Request Function
        function copyRequest(requestId) {
            if (confirm('이 요청을 복사하시겠습니까?')) {
                fetch('/admin/copy/' + requestId, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('요청이 복사되었습니다!');
                        location.reload();
                    } else {
                        alert('복사 실패: ' + (data.error || '알 수 없는 오류'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('복사 중 오류가 발생했습니다.');
                });
            }
        }
        
        // Update Vendor/Status Inline
        function updateRequest(requestId) {
            const vendor = document.getElementById('vendor-' + requestId).value;
            const status = document.getElementById('status-' + requestId).value;
            fetch('/admin/update/' + requestId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vendor, status })
            })
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    alert('저장되었습니다.');
                    location.reload();
                } else {
                    alert('저장 실패: ' + (d.error || '알 수 없는 오류'));
                }
            })
            .catch(err => {
                console.error(err);
                alert('저장 중 오류가 발생했습니다.');
            });
        }

        // Image Upload/Delete
        function onPickImage(requestId, inputEl) {
            const file = inputEl.files && inputEl.files[0];
            if (!file) return;
            uploadImage(requestId, file);
        }

        function uploadImage(requestId, file) {
            const formData = new FormData();
            formData.append('image', file);
            fetch('/admin/image/' + requestId, { method: 'POST', body: formData })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        alert('이미지가 업로드되었습니다.');
                        location.reload();
                    } else {
                        alert('업로드 실패: ' + (d.error || '알 수 없는 오류'));
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert('업로드 중 오류가 발생했습니다.');
                });
        }

        function deleteImage(requestId) {
            if (!confirm('이미지를 삭제하시겠습니까?')) return;
            fetch('/admin/image/' + requestId, { method: 'DELETE' })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        alert('이미지가 삭제되었습니다.');
                        location.reload();
                    } else {
                        alert('삭제 실패: ' + (d.error || '알 수 없는 오류'));
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert('삭제 중 오류가 발생했습니다.');
                });
        }

        // Image Preview (Lightbox)
        function openPreview(ev, anchor){
            try { if (ev) ev.preventDefault(); } catch(e){}
            try {
                var url = anchor && anchor.href ? anchor.href : (anchor && anchor.getAttribute ? anchor.getAttribute('href') : '');
                if (!url) return false;
                // 6초 타임아웃: 미리보기 지연 시 새 탭 폴백
                var modal = document.getElementById('imgPreview');
                if (modal) {
                    if (modal._previewTimer) { clearTimeout(modal._previewTimer); }
                    modal._previewTimer = setTimeout(function(){
                        try { closePreview(); } catch(e){}
                        try { window.open(url, '_blank'); } catch(e){}
                    }, 6000);
                }
                previewImage(url);
            } catch(e){ console.error(e); }
            return false;
        }
        function previewImage(url) {
            try {
                var modal = document.getElementById('imgPreview');
                var img = document.getElementById('imgPreviewImg');
                if (!modal || !img) return;
                // 1차: 원본 URL 시도, 실패 시 2차: 프록시 시도, 그래도 실패 시 새 탭
                img.onload = function(){
                    try {
                        var modalEl = document.getElementById('imgPreview');
                        if (modalEl && modalEl._previewTimer) { clearTimeout(modalEl._previewTimer); modalEl._previewTimer = null; }
                    } catch(e){}
                };
                img.onerror = function(){
                    try {
                        img.onerror = function(){
                            try { closePreview(); } catch(e){}
                            try { window.open(url, '_blank'); } catch(e){ console.error(e); }
                        };
                        img.src = '/proxy-img?u=' + encodeURIComponent(url);
                    } catch(e){
                        try { closePreview(); } catch(_){ }
                        try { window.open(url, '_blank'); } catch(_){ }
                    }
                };
                img.src = url;
                modal.style.display = 'flex';
                // ESC로 닫기
                document.addEventListener('keydown', escCloseOnce);
                // 배경 클릭으로 닫기
                modal.onclick = function(e){ if (e.target === modal) { closePreview(); } };
            } catch (e) { console.error(e); }
        }
        function escCloseOnce(e){ if (e.key === 'Escape') { closePreview(); document.removeEventListener('keydown', escCloseOnce); } }
        function closePreview() {
            try {
                var modal = document.getElementById('imgPreview');
                var img = document.getElementById('imgPreviewImg');
                if (modal) modal.style.display = 'none';
                if (modal && modal._previewTimer) { clearTimeout(modal._previewTimer); modal._previewTimer = null; }
                if (img) img.src = '';
            } catch (e) { console.error(e); }
        }

        // Set external image URL (S3/GCS/OneDrive public URL)
        function setImageUrl(requestId) {
            var input = document.getElementById('img-url-' + requestId);
            if (!input) return alert('입력 필드를 찾을 수 없습니다.');
            var url = (input.value || '').trim();
            if (!url) return alert('URL을 입력해주세요.');
            if (!(url.startsWith('http://') || url.startsWith('https://'))) {
                return alert('http/https로 시작하는 올바른 URL을 입력해주세요.');
            }
            fetch('/admin/image-url/' + requestId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    alert('외부 이미지 URL이 저장되었습니다.');
                    location.reload();
                } else {
                    alert('저장 실패: ' + (d.error || '알 수 없는 오류'));
                }
            })
            .catch(err => {
                console.error(err);
                alert('저장 중 오류가 발생했습니다.');
            });
        }

        // Delete Request Function
        function deleteRequest(requestId) {
            if (confirm('이 요청을 삭제하시겠습니까?' + '\\n\\n' + '이 작업은 되돌릴 수 없습니다.')) {
                fetch('/admin/delete/' + requestId, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 해당 카드만 제거하고, 통계는 비동기 갱신
                        const card = document.querySelector('.request-card[data-request-id="' + requestId + '"]');
                        if (card) card.remove();
                        try {
                            if (typeof loadStats === 'function') {
                                loadStats();
                            }
                        } catch (e) { /* no-op */ }
                        if (typeof showDynamicIsland === 'function') {
                            showDynamicIsland('✅ 삭제되었습니다');
                        } else {
                            alert('요청이 삭제되었습니다!');
                        }
                    } else {
                        alert('삭제 실패: ' + (data.error || '알 수 없는 오류'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('삭제 중 오류가 발생했습니다.');
                });
            }
        }
        // Ensure global binding for inline onclick handlers
        window.deleteRequest = deleteRequest;

        // Edit via Button Only (REQUESTS page)
        function startEdit(requestId) {
            try {
                // re-entrancy and dblclick guard
                if (window.__isEditing) {
                    return;
                }
                window.__editCooldown = window.__editCooldown || {};
                const now = Date.now();
                const last = window.__editCooldown[requestId] || 0;
                if (now - last < 1200) {
                    return;
                }
                window.__editCooldown[requestId] = now;
                window.__isEditing = true;
                const release = () => setTimeout(() => { window.__isEditing = false; }, 500);

                const nameEl = document.getElementById('item-name-' + requestId);
                const qtyEl = document.getElementById('quantity-' + requestId);
                const specsEl = document.getElementById('specs-' + requestId);
                const reasonEl = document.getElementById('reason-' + requestId);

                const currentName = nameEl ? nameEl.textContent.trim() : '';
                const currentQty = qtyEl ? qtyEl.textContent.trim() : '1';
                const currentSpecs = specsEl ? specsEl.textContent.trim() : '';
                const currentReason = reasonEl ? reasonEl.textContent.trim() : '';

                const newName = prompt('자재명을 입력하세요:', currentName);
                if (newName === null) { release(); return; }
                let newQty = prompt('수량을 입력하세요:', currentQty);
                if (newQty === null) { release(); return; }
                newQty = String(newQty).trim();
                if (!/^\d+$/.test(newQty)) {
                    alert('수량은 숫자만 입력 가능합니다.');
                    release();
                    return;
                }
                const newSpecs = prompt('사양(옵션)을 입력하세요:', currentSpecs);
                if (newSpecs === null) { release(); return; }
                const newReason = prompt('사유(옵션)를 입력하세요:', currentReason);
                if (newReason === null) { release(); return; }

                fetch('/admin/edit/' + requestId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        item_name: newName.trim(),
                        quantity: parseInt(newQty, 10),
                        specifications: (newSpecs || '').trim(),
                        reason: (newReason || '').trim()
                    })
                })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        if (nameEl) nameEl.textContent = newName.trim();
                        if (qtyEl) qtyEl.textContent = newQty;
                        if (specsEl) specsEl.textContent = (newSpecs || '').trim();
                        if (reasonEl) reasonEl.textContent = (newReason || '').trim();
                        alert('수정되었습니다.');
                    } else {
                        alert('수정 실패: ' + (d.error || '알 수 없는 오류'));
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert('수정 중 오류가 발생했습니다.');
                })
                .finally(() => { release(); });
            } catch (e) {
                console.error(e);
                setTimeout(() => { try { window.__isEditing = false; } catch(_){} }, 500);
                alert('수정 준비 중 오류가 발생했습니다.');
            }
        }

        // Expose functions to global scope for inline handlers
        window.copyRequest = copyRequest;
        window.updateRequest = updateRequest;
        window.deleteRequest = deleteRequest;
        window.onPickImage = onPickImage;
        window.deleteImage = deleteImage;
        
        // Page Load Animation
        document.addEventListener('DOMContentLoaded', function() {
            document.body.style.opacity = '0';
            document.body.style.transition = 'opacity 0.3s ease';
            
            setTimeout(() => {
                document.body.style.opacity = '1';
            }, 100);

            // Block any accidental dblclicks on the list
            const listEl = document.querySelector('.requests-list');
            if (listEl) {
                listEl.addEventListener('dblclick', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                }, true);
            }

            // Additionally block dblclicks globally on this page
            document.addEventListener('dblclick', (e) => {
                if (e.target && e.target.closest && e.target.closest('.requests-list')) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            }, true);

            // Expose for debugging
            window.startEdit = startEdit;

        });
    </script>
</body>
</html>
'''

ADD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>➕ 새 요청 등록 - HPNT Manager V2.0</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header { text-align: center; margin-bottom: 40px; }
        h1 { font-size: 2.5em; color: #333; margin-bottom: 10px; }
        .form-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        .required { color: #dc3545; }
        .form-control { 
            width: 100%; 
            padding: 12px; 
            border: 2px solid #e9ecef; 
            border-radius: 8px; 
            font-size: 16px;
            transition: border-color 0.3s ease;
        }
        .form-control:focus { border-color: #667eea; outline: none; }
        .textarea { min-height: 100px; resize: vertical; }
        .form-help { font-size: 0.9em; color: #666; margin-top: 5px; }
        .form-row { display: flex; gap: 20px; }
        .form-row .form-group { flex: 1; }
        .urgency-options { display: flex; gap: 15px; margin-top: 10px; }
        .urgency-option { display: flex; align-items: center; gap: 8px; }
        .urgency-option input[type="radio"] { margin: 0; }
        .btn { 
            padding: 15px 30px; 
            margin: 10px; 
            border: none; 
            border-radius: 10px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        
        /* 이미지 붙여넣기 영역 스타일 */
        .image-paste-area {
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            background: #f8f9fa;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        }
        .image-paste-area:hover {
            border-color: #667eea;
            background: #e3f2fd;
        }
        .image-paste-area.dragover {
            border-color: #28a745;
            background: #d4edda;
        }
        .paste-icon {
            font-size: 3em;
            color: #666;
            margin-bottom: 15px;
        }
        .paste-text {
            color: #666;
            font-size: 1.1em;
            margin-bottom: 10px;
        }
        .paste-help {
            color: #999;
            font-size: 0.9em;
        }
        .image-preview {
            margin-top: 20px;
            text-align: left;
        }
        .preview-image {
            max-width: 100%;
            max-height: 300px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 10px;
        }
        .image-info {
            background: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            font-size: 0.9em;
            color: #666;
        }
        .remove-image {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.8em;
            margin-top: 10px;
        }
        .remove-image:hover {
            background: #c82333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>➕ 새 요청 등록</h1>
            <p>필요한 자재를 요청해보세요</p>
            <a href="/requests" class="btn btn-secondary">취소</a>
        </div>
        
        <div class="content">
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            
            <form method="POST" enctype="multipart/form-data" onsubmit="return validateBeforeSubmit()">
                <div class="form-group">
                    <label for="item_name">자재명 <span class="required">*</span></label>
                    <input type="text" id="item_name" name="item_name" class="form-control" 
                           placeholder="예: 볼트, 너트, 와이어로프 등" required>
                    <div class="form-help">요청할 자재의 정확한 명칭을 입력하세요</div>
                </div>
                
                <div class="form-group">
                    <label for="specifications">사양 및 규격</label>
                    <textarea id="specifications" name="specifications" class="form-control textarea" 
                              placeholder="예: M12x50, SUS304, 6mm 두께 등"></textarea>
                    <div class="form-help">자재의 상세 사양, 규격, 재질 등을 입력하세요</div>
                </div>
                
                <div class="form-group">
                    <label>📷 참고 이미지</label>
                    <div class="image-paste-area" id="imagePasteArea" tabindex="0" role="button" aria-label="이미지 붙여넣기 영역">
                        <div class="paste-icon">📋</div>
                        <div class="paste-text">스크린샷을 캡쳐한 후 여기에 붙여넣기 (Ctrl+V)</div>
                        <div class="paste-help">또는 이 영역을 클릭해서 이미지를 붙여넣으세요</div>
                    </div>
                    <div class="image-preview" id="imagePreview" style="display: none;"></div>
                    <textarea id="pasteCatcher" style="position:fixed; left:-9999px; top:-9999px; width:1px; height:1px; opacity:0;" aria-hidden="true" tabindex="-1"></textarea>
                    <input type="hidden" id="imageData" name="image_data">
                    <div class="form-help">자재의 모습이나 설치 위치 등을 캡쳐해서 붙여넣으면 요청 처리에 도움이 됩니다</div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="quantity">수량 <span class="required">*</span></label>
                        <input type="number" id="quantity" name="quantity" class="form-control" 
                               min="1" value="1" required>
                        <div class="form-help">필요한 수량을 입력하세요</div>
                    </div>
                    
                    <div class="form-group">
                        <label>긴급도 <span class="required">*</span></label>
                        <div class="urgency-options">
                            <div class="urgency-option">
                                <input type="radio" id="urgency_low" name="urgency" value="low">
                                <label for="urgency_low">🟢 낮음</label>
                            </div>
                            <div class="urgency-option">
                                <input type="radio" id="urgency_normal" name="urgency" value="normal" checked>
                                <label for="urgency_normal">🟡 보통</label>
                            </div>
                            <div class="urgency-option">
                                <input type="radio" id="urgency_high" name="urgency" value="high">
                                <label for="urgency_high">🔴 높음</label>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="reason">요청 사유</label>
                    <textarea id="reason" name="reason" class="form-control textarea" 
                              placeholder="예: 정기 교체, 고장 수리, 신규 설치 등"></textarea>
                    <div class="form-help">자재가 필요한 이유나 용도를 설명해주세요</div>
                </div>
                
                <div class="form-group">
                    <label for="vendor">선호 업체</label>
                    <input type="text" id="vendor" name="vendor" class="form-control" 
                           placeholder="예: ABC 상사, XYZ 공업 등">
                    <div class="form-help">특정 업체가 있다면 입력하세요 (선택사항)</div>
                </div>
                
                <div style="margin-top: 40px; text-align: center;">
                    <a href="/requests" class="btn btn-secondary">취소</a>
                    <button type="submit" class="btn btn-success">📝 요청 등록</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        console.log('[ADD_TEMPLATE] v' + (typeof get_app_version === 'function' ? get_app_version() : 'dev') + ' - 2025-08-10T11:01');
        // 이미지 붙여넣기 기능
        const imagePasteArea = document.getElementById('imagePasteArea');
        const imagePreview = document.getElementById('imagePreview');
        const imageDataInput = document.getElementById('imageData');
        const pasteCatcher = document.getElementById('pasteCatcher');
        
        // 클립보드에서 이미지 붙여넣기
        function handlePaste(e) {
            const cd = e.clipboardData;
            if (!cd) return;
            const items = cd.items || [];
            let handled = false;

            // 1) 표준 image item 처리
            for (let i = 0; i < items.length; i++) {
                if (items[i] && items[i].type && items[i].type.indexOf('image') !== -1) {
                    e.preventDefault(); // contenteditable 기본 삽입 방지
                    const blob = items[i].getAsFile();
                    if (blob) handleImageFile(blob);
                    handled = true;
                    break;
                }
            }

            // 2) Fallback: clipboardData.files
            if (!handled && cd.files && cd.files.length > 0) {
                const file = cd.files[0];
                if (file && file.type && file.type.startsWith('image/')) {
                    e.preventDefault();
                    handleImageFile(file);
                    handled = true;
                }
            }

            // 3) Fallback: text/html 안의 <img src="data:image/..."> 처리
            if (!handled) {
                const html = cd.getData && cd.getData('text/html');
                if (html && html.indexOf('data:image') !== -1) {
                    try {
                        const m = html.match(/<img[^>]+src=["'](data:image\/[a-zA-Z0-9+.-]+;base64,[^"']+)["']/i);
                        if (m && m[1]) {
                            e.preventDefault();
                            // 프리뷰와 hidden 입력에 직접 세팅
                            const dataUrl = m[1];
                            imagePreview.innerHTML = `
                                <img src="${dataUrl}" class="preview-image" alt="미리보기">
                                <div class="image-info">
                                    📁 파일명: 붙여넣기 이미지<br>
                                    🖼️ 형식: data URL
                                </div>
                                <button type="button" class="remove-image" onclick="removeImage()">🗑️ 이미지 제거</button>
                            `;
                            imagePreview.style.display = 'block';
                            imageDataInput.value = dataUrl;
                            imagePasteArea.style.display = 'none';
                            handled = true;
                        }
                    } catch (_) {}
                }
            }

            // contenteditable 영역 내부에 브라우저가 노드를 삽입하지 않도록 정리
            if (handled) {
                imagePasteArea.innerHTML = `
                    <div class="paste-icon">📋</div>
                    <div class="paste-text">스크린샷을 캡쳐한 후 여기에 붙여넣기 (Ctrl+V)</div>
                    <div class="paste-help">또는 이 영역을 클릭해서 이미지를 붙여넣으세요</div>
                `;
            }
        }
        
        // 이미지 파일 처리
        function handleImageFile(file) {
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드 가능합니다.');
                return;
            }
            
            const reader = new FileReader();
            reader.onload = function(e) {
                const imageData = e.target.result;
                
                // 이미지 미리보기 표시
                imagePreview.innerHTML = `
                    <img src="${imageData}" class="preview-image" alt="미리보기">
                    <div class="image-info">
                        📁 파일명: ${file.name || '붙여넣기 이미지'}<br>
                        📏 크기: ${(file.size / 1024).toFixed(1)} KB<br>
                        🖼️ 형식: ${file.type}
                    </div>
                    <button type="button" class="remove-image" onclick="removeImage()">🗑️ 이미지 제거</button>
                `;
                imagePreview.style.display = 'block';
                
                // Base64 데이터를 hidden input에 저장
                imageDataInput.value = imageData;
                
                // 붙여넣기 영역 숨기기
                imagePasteArea.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
        
        // 이미지 제거
        function removeImage() {
            imagePreview.style.display = 'none';
            imagePreview.innerHTML = '';
            imageDataInput.value = '';
            imagePasteArea.style.display = 'block';
        }

        // 제출 전 검증: 미리보기 노출인데 hidden 값이 비어있으면 방지
        function validateBeforeSubmit() {
            const previewVisible = imagePreview.style.display !== 'none' && imagePreview.innerHTML.trim() !== '';
            const hasData = imageDataInput.value && imageDataInput.value.startsWith('data:image/');
            if (previewVisible && !hasData) {
                alert('이미지 미리보기는 보이지만 데이터가 비어 있습니다. 다시 붙여넣기 후 시도해주세요.');
                return false;
            }
            return true;
        }
        
        // ID 재정렬 기능
        function reindexIds() {
            if (confirm(`현재 모든 자재요청의 ID를 #1부터 순차적으로 재정렬하시겠습니까?\n\n주의: 이 작업은 모든 데이터를 재구성하므로 시간이 걸릴 수 있습니다.`)) {
                const button = document.querySelector('.reindex-btn');
                if (button) {
                    button.disabled = true;
                    button.textContent = '재정렬 중...';
                }
                
                fetch('/admin/reindex-ids', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ ' + data.message);
                        location.reload();
                    } else {
                        alert('❌ ID 재정렬 실패: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('❌ ID 재정렬 중 오류가 발생했습니다.');
                })
                .finally(() => {
                    if (button) {
                        button.disabled = false;
                        button.textContent = '🔄 ID 재정렬';
                    }
                });
            }
        }
        
        // 이벤트 리스너 등록
        // 전역 캡처 단계에서 paste를 가로채어, 폼 필드 외에서는 기본 삽입을 차단하고 우리 로직만 수행
        document.addEventListener('paste', function(e){
            const t = e.target;
            const tag = (t && t.tagName) ? t.tagName.toUpperCase() : '';
            const isFormField = tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable);
            if (!isFormField) {
                e.preventDefault();
                handlePaste(e);
            }
        }, true);
        // contenteditable이 아니므로, 항상 기본 동작 차단 후 우리 로직 수행
        imagePasteArea.addEventListener('paste', function(e){
            e.preventDefault();
            handlePaste(e);
        });
        imagePasteArea.addEventListener('beforeinput', function(e){
            if (e.inputType === 'insertFromPaste') {
                e.preventDefault();
            }
        });
        imagePasteArea.addEventListener('click', function() {
            // 클릭 시 숨김 textarea에 포커스 -> 클립보드 이벤트 수신
            if (pasteCatcher) pasteCatcher.focus();
        });
        
        // 드래그 앤 드롭 방지 (붙여넣기만 허용)
        imagePasteArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('dragover');
        });
        
        imagePasteArea.addEventListener('dragleave', function(e) {
            this.classList.remove('dragover');
        });
        
        imagePasteArea.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            // 드롭은 허용하지 않고 붙여넣기만 허용
            alert('파일을 직접 드롭할 수 없습니다. 스크린샷을 캡쳐한 후 Ctrl+V로 붙여넣어 주세요.');
        });
        
        // 키보드 단축키 안내
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'v') {
                // Ctrl+V 감지 시 붙여넣기 영역에 포커스
                if (imagePasteArea.style.display !== 'none') {
                    imagePasteArea.focus();
                }
            }
        });
    </script>
</body>
</html>
'''

# Flask 라우트 함수들
@app.route('/')
def home():
    """메인 홈페이지 - 안전 모드 지원 및 통계 표시"""
    # 안전 모드: 스크립트 최소화 페이지로 렌더
    if request.args.get('safe') == '1':
        resp = make_response(render_template_string(SAFE_HOME_TEMPLATE))
        resp.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'"
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    try:
        env = detect_environment().upper()
        db_location = "로컬 DB (프로젝트/db)"
        
        # 통계 데이터 가져오기
        stats = {}
        try:
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 전체 카운트
            cursor.execute("SELECT COUNT(*) FROM material_requests")
            stats['total'] = cursor.fetchone()[0]
            
            # 상태별 카운트
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM material_requests 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            stats.update({
                'pending': status_counts.get('pending', 0),
                'approved': status_counts.get('approved', 0),
                'ordered': status_counts.get('ordered', 0),
                'received': status_counts.get('received', 0),
                'rejected': status_counts.get('rejected', 0),
                'completed': status_counts.get('completed', 0)
            })
            
            conn.close()
        except Exception as e:
            logger.error(f"통계 데이터 로드 실패: {e}")
            stats = {
                'total': 0,
                'pending': 0,
                'approved': 0,
                'ordered': 0,
                'received': 0,
                'rejected': 0,
                'completed': 0
            }
        
        resp = make_response(render_template_string(HOME_TEMPLATE, 
                                    environment=env,
                                    db_location=db_location,
                                    version=APP_VERSION,
                                    stats=stats,
                                    get_app_version=get_app_version))
        # 기본 CSP: 위젯 지연 로드 허용, 그 외는 self 위주
        resp.headers['Content-Security-Policy'] = (
            "default-src 'self' https://cloud.google.com https://fonts.googleapis.com https://fonts.gstatic.com https://www.gstatic.com https://www.google.com https://www.googletagmanager.com; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cloud.google.com https://www.gstatic.com https://www.google.com https://www.googletagmanager.com https://www.google-analytics.com https://apis.google.com https://www.recaptcha.net; "
            "script-src-elem 'self' 'unsafe-inline' 'unsafe-eval' https://cloud.google.com https://www.gstatic.com https://www.google.com https://www.googletagmanager.com https://www.google-analytics.com https://apis.google.com https://www.recaptcha.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://www.gstatic.com https://www.google.com; "
            "connect-src 'self' https://cloud.google.com https://www.googleapis.com https://www.gstatic.com https://content-ucs.googleapis.com https://*.googleapis.com https://www.google-analytics.com https://www.googletagmanager.com https://www.google.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-src 'self' https://cloud.google.com https://www.gstatic.com https://www.google.com https://www.recaptcha.net; "
            "worker-src 'self' blob:;"
        )
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        logger.error(f"홈페이지 로드 실패: {e}")
        return f"<h1>❌ 오류</h1><p>페이지를 불러올 수 없습니다: {e}</p>"

# 신규 기능(위젯) 접근 인증 엔드포인트
@app.route('/feature-auth', methods=['POST'])
def feature_auth():
    try:
        payload = request.get_json(silent=True) or {}
        password = (payload.get('password') or '').strip()
        # 비밀번호는 환경변수 우선, 없으면 기본값 사용
        _env_pwd = os.environ.get('FEATURE_PASSWORD') or os.environ.get('NEW_FEATURE_PASSWORD')
        expected = _env_pwd or 'hpnt-ai-2025'
        admin_debug = str(os.environ.get('ADMIN_DEBUG', '')).strip() in ('1','true','True','yes','on')
        source = 'env' if _env_pwd else 'default'

        # 최소 진단 로그(비밀번호 값은 로그에 남기지 않음)
        try:
            logger.info(f"feature_auth attempt: admin_debug={admin_debug}, source={source}")
        except Exception:
            pass

        if password and password == expected:
            session['feature_unlocked'] = True
            resp = {"success": True}
            if admin_debug:
                resp["source"] = source
            return jsonify(resp), 200
        resp = {"success": False, "error": "invalid_password"}
        if admin_debug:
            resp["source"] = source
        return jsonify(resp), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/requests')
def requests_page():
    try:
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        admin_debug = os.getenv('ADMIN_DEBUG', '0') in ('1','true','True')

        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 상태별 카운트 계산
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM material_requests 
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())
        total_count = sum(status_counts.values())
        
        # PostgreSQL과 동일한 컴럼 순서로 명시적 SELECT
        query = "SELECT id, item_name, quantity, specifications, reason, urgency, request_date, vendor, status, images, created_at FROM material_requests WHERE 1=1"
        params = []
        
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        
        if search_query:
            query += " AND ("
            query += "LOWER(item_name) LIKE LOWER(?) OR "
            query += "LOWER(specifications) LIKE LOWER(?) OR "
            query += "LOWER(reason) LIKE LOWER(?) OR "
            query += "LOWER(vendor) LIKE LOWER(?)"
            query += ")"
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param, search_param, search_param])
        
        query += " ORDER BY id DESC"
        
        cursor.execute(query, params)
        requests = cursor.fetchall()
        conn.close()
        
        return render_template_string(REQUESTS_TEMPLATE, 
                                     requests=requests,
                                     status_filter=status_filter,
                                     search_query=search_query,
                                     status_counts=status_counts,
                                     total_count=total_count,
                                     admin_debug=admin_debug,
                                     get_app_version=get_app_version)
    except Exception as e:
        logger.error(f"자재요청 목록 조회 실패: {e}")
        return f"<h1>❌ 오류</h1><p>목록을 불러올 수 없습니다: {e}</p><a href='/'></a>"

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    """새 자재요청 등록 페이지"""
    if request.method == 'POST':
        try:
            item_name = request.form.get('item_name', '').strip()
            specifications = request.form.get('specifications', '').strip()
            quantity = int(request.form.get('quantity', 1))
            urgency = request.form.get('urgency', 'normal')
            reason = request.form.get('reason', '').strip()
            vendor = request.form.get('vendor', '').strip()
            image_data = request.form.get('image_data', '').strip()
            try:
                logger.info(f"[ADD] image_data len={len(image_data)} head={image_data[:30] if image_data else ''}")
            except Exception:
                pass
            
            if not item_name:
                return render_template_string(ADD_TEMPLATE, error="자재명은 필수 입력 항목입니다.", get_app_version=get_app_version)
            
            if quantity <= 0:
                return render_template_string(ADD_TEMPLATE, error="수량은 1 이상이어야 합니다.", get_app_version=get_app_version)
            
            # 이미지 처리
            image_filename = None
            if image_data and image_data.startswith('data:image/'):
                try:
                    # Base64 이미지 데이터 파싱
                    header, encoded = image_data.split(',', 1)
                    image_format = header.split(';')[0].split('/')[1]  # png, jpeg 등
                    
                    # 이미지 저장 폴더 생성 (OneDrive 연동)
                    images_dir = get_images_dir_path()
                    logger.info(f"[ADD] images_dir={images_dir}")
                    
                    # 고유한 파일명 생성 (타임스탬프 + 자재명)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_item_name = ''.join(c for c in item_name if c.isalnum() or c in (' ', '-', '_')).strip()[:20]
                    image_filename = f"{timestamp}_{safe_item_name}.{image_format}"
                    image_path = os.path.join(images_dir, image_filename)
                    
                    # Base64 디코딩 후 파일 저장
                    import base64
                    with open(image_path, 'wb') as f:
                        f.write(base64.b64decode(encoded))
                    
                    logger.info(f"[ADD] 이미지 저장 완료: {image_filename} size={len(encoded)}B (base64)")
                    
                except Exception as img_error:
                    logger.warning(f"[ADD] 이미지 저장 실패: {img_error}")
                    # 이미지 저장 실패해도 요청 등록은 계속 진행
                    image_filename = None
            else:
                if image_data:
                    logger.warning("[ADD] image_data는 존재하지만 data:image/로 시작하지 않음")
                else:
                    logger.info("[ADD] image_data 비어 있음 (이미지 없음)")
            
            # 데이터베이스에 자재요청 추가
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # DB 테이블 구조에 맞게 INSERT (새 스키마 컴럼 순서)
            cursor.execute('''
                INSERT INTO material_requests 
                (item_name, quantity, specifications, reason, urgency, request_date, vendor, status, images)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', (item_name, quantity, specifications, reason, urgency, datetime.now().strftime('%Y-%m-%d'), vendor, image_filename))
            
            inserted_id = cursor.lastrowid
            conn.commit()
            try:
                # Verify saved images value
                cursor.execute('SELECT images FROM material_requests WHERE id = ?', (inserted_id,))
                saved_img = cursor.fetchone()
                logger.info(f"[ADD] INSERTED id={inserted_id}, images_in_db={saved_img[0] if saved_img else None}")
            except Exception as verify_err:
                logger.warning(f"[ADD] INSERT verify read failed: {verify_err}")
            finally:
                conn.close()
            
            logger.info(f"[ADD] 새 자재요청 등록: {item_name} x {quantity} (이미지: {'있음' if image_filename else '없음'}) 저장된파일명={image_filename}")
            return redirect('/requests')
            
        except ValueError:
            return render_template_string(ADD_TEMPLATE, error="수량은 숫자로 입력해주세요.", get_app_version=get_app_version)
        except Exception as e:
            logger.error(f"자재요청 등록 실패: {e}")
            return render_template_string(ADD_TEMPLATE, error=f"등록 중 오류가 발생했습니다: {e}", get_app_version=get_app_version)
    
    return render_template_string(ADD_TEMPLATE, get_app_version=get_app_version)

# 중복된 통계 페이지 라우트 제거 (아래에서 이미 정의됨)
@app.route('/favicon.ico')
def favicon():
    """브라우저 파비콘 요청 404 방지 (아이콘 미제공시 204 반환)"""
    return "", 204

@app.route('/images/<filename>')
def serve_image(filename):
    """이미지 파일 서빙 - OneDrive 연동"""
    try:
        images_dir = get_images_dir_path()
        return send_from_directory(images_dir, filename)
    except Exception as e:
        logger.error(f"이미지 서빙 실패: {e}")
        return "", 404

@app.route('/admin/db/download', methods=['GET'])
def admin_download_db():
    """material_requests 테이블을 JSON 파일로 다운로드 (ADMIN_DEBUG가 켜져 있을 때만)"""
    admin_debug = os.getenv('ADMIN_DEBUG', '0') in ('1','true','True')
    if not admin_debug:
        return "Forbidden", 403
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, item_name, quantity, specifications, reason, urgency, request_date, vendor, status, images, created_at
            FROM material_requests
            ORDER BY id
        """)
        rows = cursor.fetchall()
        conn.close()

        cols = ['id','item_name','quantity','specifications','reason','urgency','request_date','vendor','status','images','created_at']
        data = [dict(zip(cols, r)) for r in rows]
        payload = json.dumps({
            'exported_at': datetime.now().isoformat(),
            'count': len(data),
            'rows': data
        }, ensure_ascii=False, default=str)

        resp = app.response_class(payload, mimetype='application/json; charset=utf-8')
        filename = f"material_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        logger.error(f"DB 내보내기 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/edit/<int:request_id>', methods=['POST'])
def admin_edit_material_info(request_id):
    """관리자 자재 정보 수정 (모달 인라인 편집)"""
    try:
        data = request.get_json()
        item_name = data.get('item_name', '').strip()
        quantity = data.get('quantity', 1)
        specifications = data.get('specifications', '').strip()
        reason = data.get('reason', '').strip()
        
        # 필수 필드 검증
        if not item_name:
            return jsonify({'success': False, 'error': '자재명은 필수 입력 항목입니다.'}), 400
        
        if quantity < 1:
            return jsonify({'success': False, 'error': '수량은 1 이상이어야 합니다.'}), 400
        
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE material_requests 
            SET item_name = ?, quantity = ?, specifications = ?, reason = ?
            WHERE id = ?
        """, (item_name, quantity, specifications, reason, request_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"자재 정보 수정: 요청 ID {request_id}, 자재명: {item_name}, 수량: {quantity}")
        return jsonify({'success': True, 'message': '자재 정보가 성공적으로 수정되었습니다.'})
        
    except Exception as e:
        logger.error(f"자재 정보 수정 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/update/<int:request_id>', methods=['POST'])
def admin_update_request(request_id):
    """관리자 자재요청 업데이트"""
    try:
        data = request.get_json()
        vendor = data.get('vendor', '')
        status = data.get('status', 'pending')
        is_active = data.get('is_active', False)
        
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 자재요청 업데이트
        cursor.execute(
            "UPDATE material_requests SET vendor = ?, status = ? WHERE id = ?", 
            (vendor, status, request_id)
        )
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"관리자 업데이트: 요청 ID {request_id}, 업체: {vendor}, 상태: {status}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"관리자 업데이트 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def reindex_material_request_ids():
    """자재요청 ID를 1번부터 연속적으로 재정렬"""
    try:
        # PostgreSQL에서는 SERIAL/IDENTITY 시퀀스를 수동으로 재정렬할 필요가 없으며
        # 아래 로직은 SQLite 전용(sqlite_sequence)을 사용합니다. Postgres에서는 건너뜁니다.
        if USE_POSTGRES:
            logger.info("PostgreSQL 환경: ID 재정렬은 생략합니다.")
            return
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 모든 데이터를 ID 순서대로 조회 (ID 제외)
        cursor.execute('''
            SELECT request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images, created_at
            FROM material_requests 
            ORDER BY id
        ''')
        all_data = cursor.fetchall()
        
        # 기존 데이터 전체 삭제
        cursor.execute('DELETE FROM material_requests')
        
        if not all_data:
            # 모든 데이터가 삭제된 경우, AUTOINCREMENT 시퀀스를 0으로 재설정
            cursor.execute('DELETE FROM sqlite_sequence WHERE name="material_requests"')
            cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("material_requests", 0)')
            conn.commit()
            conn.close()
            logger.info("ID 재정렬: 전체 삭제 후 시퀀스 1부터 재시작")
            return
        
        # ID를 1번부터 다시 삽입
        for i, row in enumerate(all_data, 1):
            cursor.execute('''
                INSERT INTO material_requests 
                (id, request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (i,) + row)
        
        # SQLite의 AUTOINCREMENT 시퀀스 재설정
        cursor.execute('DELETE FROM sqlite_sequence WHERE name="material_requests"')
        cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("material_requests", ?)', (len(all_data),))
        
        conn.commit()
        conn.close()
        
        logger.info(f"ID 재정렬 완료: {len(all_data)}개 항목")
    except Exception as e:
        logger.error(f"ID 재정렬 실패: {e}")
        raise e


@app.route('/admin/image/<int:request_id>', methods=['POST', 'DELETE'])
def admin_edit_image(request_id):
    """관리자 이미지 업로드/삭제"""
    try:
        if request.method == 'POST':
            # 이미지 업로드
            if 'image' not in request.files:
                return jsonify({'success': False, 'error': '이미지 파일이 없습니다.'}), 400
            
            file = request.files['image']
            if file.filename == '':
                return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다.'}), 400
            
            # 파일 크기 체크 (5MB 제한)
            file.seek(0, 2)  # 파일 끝으로 이동
            file_size = file.tell()
            file.seek(0)  # 파일 처음으로 되돌리기
            
            if file_size > 5 * 1024 * 1024:
                return jsonify({'success': False, 'error': '파일 크기는 5MB 이하여야 합니다.'}), 400
            
            # 이미지 파일 형식 체크
            if not file.content_type.startswith('image/'):
                return jsonify({'success': False, 'error': '이미지 파일만 업로드 가능합니다.'}), 400
            
            # 기존 이미지 파일 삭제 및 새 이미지 저장
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT images FROM material_requests WHERE id = ?", (request_id,))
            result = cursor.fetchone()
            if result and result[0]:
                # 기존 값이 외부 URL이면 파일 삭제 스킵
                if not (isinstance(result[0], str) and (result[0].startswith('http://') or result[0].startswith('https://'))):
                    old_image_path = os.path.join(get_images_dir_path(), result[0])
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                        logger.info(f"기존 이미지 삭제: {result[0]}")
            conn.close()
            
            # 새 이미지 파일 저장
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
            filename = f"material_{request_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
            
            images_dir = get_images_dir_path()
            if not os.path.exists(images_dir):
                os.makedirs(images_dir, exist_ok=True)
            
            file_path = os.path.join(images_dir, filename)
            file.save(file_path)
            
            # DB 업데이트
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE material_requests SET images = ? WHERE id = ?", (filename, request_id))
            conn.commit()
            conn.close()
            
            logger.info(f"이미지 업로드: ID {request_id} - {filename}")
            return jsonify({'success': True, 'filename': filename})
            
        elif request.method == 'DELETE':
            # 이미지 삭제
            image_filename = None
            
            # 이미지 파일명 조회 (삭제를 위해)
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT images FROM material_requests WHERE id = ?", (request_id,))
            result = cursor.fetchone()
            image_filename = result[0] if result and result[0] else None
            conn.close()
            
            if not image_filename:
                return jsonify({'success': False, 'error': '삭제할 이미지가 없습니다.'}), 400
            
            # 외부 URL이 아닌 경우에만 로컬 파일 삭제
            if not (isinstance(image_filename, str) and (image_filename.startswith('http://') or image_filename.startswith('https://'))):
                image_path = os.path.join(get_images_dir_path(), image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.info(f"이미지 파일 삭제: {image_filename}")
            
            # DB에서 이미지 정보 제거
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE material_requests SET images = NULL WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            
            logger.info(f"이미지 삭제: ID {request_id}")
            return jsonify({'success': True})
            
    except Exception as e:
        logger.error(f"이미지 처리 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 중복된 admin_edit_material_info 라우트 제거됨 (다른 위치에 이미 정의되어 있음)

# 외부 이미지 프록시 라우트 (핫링크/리퍼러/CORS 회피용 경량 프록시)
@app.route('/proxy-img')
def proxy_img():
    try:
        target = (request.args.get('u') or '').strip()
        if not target or not (target.startswith('http://') or target.startswith('https://')):
            return ('잘못된 URL', 400)
        # urllib으로 간단히 프록시 (의존성 추가 없이)
        import urllib.request
        import socket
        MAX_SIZE = 10 * 1024 * 1024  # 10MB 안전 한도
        req = urllib.request.Request(
            target,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
            }
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            # 너무 큰 응답 사전 차단
            clen = resp.headers.get('Content-Length')
            if clen and clen.isdigit() and int(clen) > MAX_SIZE:
                return ('이미지 파일이 너무 큽니다.', 413)
            # 최대 10MB까지만 읽기
            data = resp.read(MAX_SIZE + 1)
            if len(data) > MAX_SIZE:
                return ('이미지 파일이 너무 큽니다.', 413)
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            return Response(data, mimetype=content_type)
    except socket.timeout:
        logger.error("proxy-img 타임아웃")
        return ('프록시 타임아웃', 504)
    except Exception as e:
        logger.error(f"proxy-img 실패: {e}")
        return ('이미지를 가져올 수 없습니다.', 502)

# 외부 이미지 URL 저장 라우트
@app.route('/admin/image-url/<int:request_id>', methods=['POST'])
def admin_set_image_url(request_id):
    """외부 공개 URL(S3/GCS/OneDrive 등)을 images 컬럼에 그대로 저장"""
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'URL이 비어있습니다.'}), 400
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'success': False, 'error': 'http/https URL만 허용됩니다.'}), 400

        # 기존 로컬 파일이 있었다면 정리(옵션): 여기서는 덮어쓰기만 수행, 파일 삭제는 하지 않음
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('UPDATE material_requests SET images = ? WHERE id = ?', (url, request_id))
        conn.commit()
        conn.close()
        logger.info(f"외부 이미지 URL 저장: ID {request_id} - {url}")
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        logger.error(f"외부 이미지 URL 저장 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/copy/<int:request_id>', methods=['POST'])
def admin_copy_request(request_id):
    """관리자 자재요청 복사"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 기존 자재요청 정보 조회
        cursor.execute("""
            SELECT item_name, specifications, quantity, urgency, reason, images
            FROM material_requests WHERE id = ?
        """, (request_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'success': False, 'error': '복사할 요청을 찾을 수 없습니다.'}), 404
        
        item_name, specifications, quantity, urgency, reason, images = result
        
        # 새로운 자재요청으로 등록 (상태는 pending, 발주업체는 비움) - 새 스키마 컴럼 순서
        cursor.execute("""
            INSERT INTO material_requests 
            (item_name, quantity, specifications, reason, urgency, request_date, vendor, status, images)
            VALUES (?, ?, ?, ?, ?, ?, '', 'pending', ?)
        """, (item_name, quantity, specifications, reason, urgency, datetime.now().strftime('%Y-%m-%d'), images))
        
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"자재요청 복사: ID {request_id} → 새 ID {new_id} ({item_name})")
        return jsonify({'success': True, 'new_id': new_id})
        
    except Exception as e:
        logger.error(f"자재요청 복사 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/delete/<int:request_id>', methods=['DELETE'])
def admin_delete_request(request_id):
    """관리자 자재요청 삭제"""
    try:
        logger.info(f"관리자 삭제 요청 수신: ID={request_id}")
        image_filename = None
        
        # SQLite 사용 (기존 로직)
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 이미지 파일명 조회 (삭제를 위해)
        cursor.execute("SELECT images FROM material_requests WHERE id = ?", (request_id,))
        result = cursor.fetchone()
        image_filename = result[0] if result and result[0] else None
        
        # 자재요청 삭제
        cursor.execute("DELETE FROM material_requests WHERE id = ?", (request_id,))
        logger.info(f"관리자 삭제 실행: rowcount={cursor.rowcount}")
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        # SQLite에서만 ID 재정렬 수행 (PostgreSQL은 불필요)
        if not USE_POSTGRES:
            reindex_material_request_ids()
        
        # 이미지 파일도 삭제 (OneDrive 연동)
        if image_filename:
            try:
                images_dir = get_images_dir_path()
                image_path = os.path.join(images_dir, image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.info(f"이미지 파일 삭제: {image_filename}")
            except Exception as img_error:
                logger.warning(f"이미지 파일 삭제 실패: {img_error}")
        
        logger.info(f"관리자 삭제 및 ID 재정렬: 요청 ID {request_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"관리자 삭제 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/debug/ids', methods=['GET'])
def admin_debug_ids():
    """현재 DB의 material_requests ID 목록을 조회 (읽기 전용, 임시 진단용)"""
    try:
        if not ADMIN_DEBUG:
            return jsonify({'success': False, 'error': 'disabled'}), 403
        conn = sqlite3.connect(get_material_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_name, status FROM material_requests ORDER BY id LIMIT 100")
        rows = cursor.fetchall()
        conn.close()
        return jsonify({
            'use_postgres': USE_POSTGRES,
            'count': len(rows),
            'rows': rows
        })
    except Exception as e:
        logger.error(f"ID 목록 조회 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Railway 헬스체크용 라우트
@app.route('/health')
def health_check():
    """Railway 헬스체크용 간단한 응답"""
    return {'status': 'healthy', 'message': 'HPNT ENG Manager V2.0 is running'}, 200

# PWA 서비스 워커 비활성화 (캐시 문제 해결)
@app.route('/sw.js')
def service_worker():
    """서비스 워커 비활성화 - 기존 캐시 제거"""
    sw_content = '''
// 기존 서비스 워커 비활성화 및 캐시 제거
self.addEventListener('install', function(event) {
    // 기존 캐시 제거
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    console.log('캐시 제거:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        })
    );
    // 즉시 활성화
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    // 모든 클라이언트 제어
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function(event) {
    // 캐시 사용 안 함 - 항상 네트워크에서 가져오기
    event.respondWith(fetch(event.request));
});

// 서비스 워커 자체 제거
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
'''
    return sw_content, 200, {'Content-Type': 'application/javascript'}

# ====== DB 수동 업로드/다운로드 라우트 (무료, 관리자용) ======
from flask import send_file

@app.route('/admin/reindex-ids', methods=['POST'])
def admin_reindex_ids():
    """관리자: ID 재정렬 (#1부터 순차적으로)"""
    try:
        if USE_POSTGRES:
            return jsonify({
                'success': True,
                'message': 'PostgreSQL 환경에서는 ID 재정렬이 필요하지 않습니다.'
            })
        # SQLite ID 재정렬
        reindex_material_request_ids()
        return jsonify({
            'success': True, 
            'message': 'SQLite ID 재정렬이 완료되었습니다. 페이지를 새로고침해주세요.'
        })
        
    except Exception as e:
        logger.error(f"ID 재정렬 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/db-upload', methods=['GET', 'POST'])
def db_upload():
    """관리자: DB 파일 업로드 (OneDrive→서버)"""
    if request.method == 'POST':
        file = request.files['dbfile']
        db_path = get_material_db_path()
        file.save(db_path)
        return '<h3>DB 업로드 완료! <a href="/">홈으로</a></h3>'
    return '''
        <h2>DB 파일 업로드</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="dbfile" required>
            <input type="submit" value="업로드">
        </form>
        <a href="/">← 홈으로</a>
    '''

@app.route('/admin/db-download')
def db_download():
    """관리자: DB 파일 다운로드 (서버→OneDrive)"""
    db_path = get_material_db_path()
    return send_file(db_path, as_attachment=True)


from flask import send_file
import zipfile
import io

@app.route('/admin/images-download')
def images_download():
    """관리자: 이미지 전체 zip 다운로드"""
    try:
        import zipfile
        import tempfile
        
        images_dir = get_images_dir_path()
        
        # 임시 zip 파일 생성
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 이미지 폴더의 모든 파일을 zip에 추가
            if os.path.exists(images_dir):
                for filename in os.listdir(images_dir):
                    file_path = os.path.join(images_dir, filename)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, filename)
        
        # zip 파일 다운로드 제공
        return send_file(temp_zip.name, 
                        as_attachment=True, 
                        download_name=f'hpnt_images_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                        mimetype='application/zip')
        
    except Exception as e:
        logger.error(f"이미지 다운로드 실패: {e}")
        return f'<h3>❌ 이미지 다운로드 실패: {e}</h3><a href="/">홈으로</a>'

@app.route('/admin/backup-create')
def backup_create():
    """관리자: DB 백업 생성 및 환경 변수용 JSON 출력"""
    try:
        backup_data = create_db_backup()
        if backup_data:
            import json
            backup_json = json.dumps(backup_data, ensure_ascii=False, separators=(',', ':'), default=str)
            
            # HTML 형태로 결과 표시
            html_content = f'''
            <h2>🔄 DB 백업 생성 완료</h2>
            <p><strong>백업 일시:</strong> {backup_data['backup_date']}</p>
            <p><strong>총 레코드:</strong> {backup_data['total_records']}개</p>
            
            <h3>📋 Render 환경 변수 설정</h3>
            <p>Render 대시보드에서 다음 환경 변수를 설정하세요:</p>
            <ul>
                <li><strong>변수명:</strong> <code>DB_BACKUP_JSON</code></li>
                <li><strong>값:</strong> 아래 JSON 데이터 전체 복사</li>
            </ul>
            
            <h4>🔗 JSON 백업 데이터:</h4>
            <textarea readonly style="width:100%; height:200px; font-family:monospace; font-size:12px;">{backup_json}</textarea>
            
            <br><br>
            <a href="/" class="btn">← 홈으로</a>
            <a href="/admin/backup-create" class="btn">🔄 새로고침</a>
            '''
            
            return html_content
        else:
            return '<h3>❌ DB 백업 생성 실패</h3><a href="/">홈으로</a>'
            
    except Exception as e:
        logger.error(f"DB 백업 생성 실패: {e}")
        return f'<h3>❌ DB 백업 생성 실패: {e}</h3><a href="/">홈으로</a>'

@app.route('/admin/force-init-db')
def force_init_db():
    """관리자: Railway 환경 DB 강제 초기화"""
    try:
        # 환경 정보 출력
        env = detect_environment()
        is_railway = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID')
        db_path = get_material_db_path()
        
        html_content = f'''
        <h2>🚂 Railway DB 강제 초기화</h2>
        <p><strong>환경:</strong> {env}</p>
        <p><strong>Railway 감지:</strong> {bool(is_railway)}</p>
        <p><strong>DB 경로:</strong> {db_path}</p>
        <p><strong>DB 파일 존재:</strong> {os.path.exists(db_path)}</p>
        
        <h3>🔄 강제 초기화 실행:</h3>
        '''
        
        # 강제 DB 초기화 실행
        if init_material_database():
            html_content += '<p style="color: green;">✅ DB 초기화 성공!</p>'
            
            # 데이터 확인
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM material_requests")
                count = cursor.fetchone()[0]
                conn.close()
                
                html_content += f'<p><strong>현재 레코드 수:</strong> {count}개</p>'
                
                if count > 0:
                    html_content += '<p style="color: green;">✅ 샘플 데이터 삽입 성공!</p>'
                else:
                    html_content += '<p style="color: red;">❌ 샘플 데이터 삽입 실패</p>'
                    
            except Exception as db_error:
                html_content += f'<p style="color: red;">❌ DB 연결 오류: {db_error}</p>'
        else:
            html_content += '<p style="color: red;">❌ DB 초기화 실패!</p>'
        
        html_content += '''
        <br>
        <a href="/requests" class="btn">📋 자재요청 목록</a>
        <a href="/" class="btn">← 홈으로</a>
        '''
        
        return html_content
        
    except Exception as e:
        logger.error(f"DB 강제 초기화 실패: {e}")
        return f'<h3>❌ DB 강제 초기화 실패: {e}</h3><a href="/">홈으로</a>'

@app.route('/admin/backup-test')
def backup_test():
    """관리자: 환경 변수 백업 복구 테스트"""
    try:
        backup_json = os.environ.get('DB_BACKUP_JSON')
        if backup_json:
            import json
            backup_data = json.loads(backup_json)
            
            html_content = f'''
            <h2>🧪 백업 복구 테스트</h2>
            <p><strong>환경 변수 백업 발견:</strong> ✅</p>
            <p><strong>백업 일시:</strong> {backup_data.get('backup_date', 'N/A')}</p>
            <p><strong>총 레코드:</strong> {backup_data.get('total_records', 0)}개</p>
            
            <h3>📋 백업 데이터 미리보기:</h3>
            <ul>
            '''
            
            # 처음 3개 레코드만 미리보기
            for i, record in enumerate(backup_data.get('data', [])[:3]):
                html_content += f"<li>ID {record.get('id')}: {record.get('item_name')} (수량: {record.get('quantity')})</li>"
            
            if backup_data.get('total_records', 0) > 3:
                html_content += f"<li>... 외 {backup_data.get('total_records') - 3}개 더</li>"
            
            html_content += '''</ul>
            </div>
            '''
            
            return html_content
        
    except Exception as e:
        logger.error(f"DB 백업 미리보기 실패: {e}")
        return f"<div class='alert alert-danger'>백업 미리보기 실패: {str(e)}</div>"
    
    return "<div class='alert alert-warning'>백업 데이터가 없습니다.</div>"

@app.route('/api/stats')
def api_stats():
    """API 통계 엔드포인트"""
    try:
        # SQLite 사용
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 전체 카운트
        cursor.execute("SELECT COUNT(*) FROM material_requests")
        total = cursor.fetchone()[0]
        
        # 상태별 카운트
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM material_requests 
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())
        
        stats = {
            'total': total,
            'pending': status_counts.get('pending', 0),
            'approved': status_counts.get('approved', 0),
            'ordered': status_counts.get('ordered', 0),
            'received': status_counts.get('received', 0),
            'rejected': status_counts.get('rejected', 0),
            'completed': status_counts.get('completed', 0),
            'in_progress': status_counts.get('in_progress', 0),
            'environment': detect_environment(),
            'database': 'PostgreSQL' if USE_POSTGRES else 'SQLite'
        }
        
        conn.close()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"API 통계 로드 실패: {e}")
        return jsonify({
            'total': 0,
            'pending': 0,
            'approved': 0,
            'ordered': 0,
            'received': 0,
            'rejected': 0,
            'completed': 0,
            'error': str(e)
        }), 500

@app.route('/stats')
def stats_page():
    """통계 페이지"""
    return "<h1>📊 통계</h1><p>곧 구현될 예정입니다!</p><a href='/'>← 홈으로</a>"

@app.route('/health')
def health():
    return "ok", 200

@app.route('/env')
def env_info():
    try:
        from urllib.parse import urlparse
    except Exception:
        urlparse = None
    host = None
    scheme = None
    try:
        if DATABASE_URL and urlparse:
            p = urlparse(DATABASE_URL)
            host = p.hostname
            scheme = p.scheme
    except Exception:
        pass
    return jsonify({
        'use_postgres': USE_POSTGRES,
        'has_database_url': bool(DATABASE_URL),
        'db_scheme': scheme,
        'db_host': host,
        'psycopg2_import_ok': _PSYCOPG2_IMPORT_OK,
        'psycopg2_import_err': _PSYCOPG2_IMPORT_ERR,
        'environment': detect_environment(),
    })


if __name__ == '__main__':
    try:
        print("=" * 50)
        print("🚀 HPNT ENG Manager V2.0 시작")
        print("=" * 50)

        # 실행 환경 정보 출력
        env = detect_environment()
        print(f"실행 환경: {env}")
        
        # DB 초기화 (실패해도 서버 시작)
        try:
            if init_material_database():
                db_path = get_material_db_path()
                print(f"✅ SQLite DB 초기화 완료: {db_path}")
            else:
                print("⚠️ DB 초기화 실패 - 서버는 계속 시작")
        except Exception as db_error:
            print(f"⚠️ DB 초기화 오류: {db_error} - 서버는 계속 시작")

        # 포트 설정
        port = int(os.environ.get('PORT', 5001))
        host = '0.0.0.0'  # Railway에서는 모든 인터페이스에서 수신해야 함
        
        # 사전 포트 점유 확인(중복 실행 방지)
        try:
            import socket as _sock
            with _sock.create_connection(("127.0.0.1", port), timeout=0.5) as _s:
                # 연결에 성공했다는 것은 이미 누군가(아마 이전 인스턴스)가 리슨 중
                print(f"⚠️ 포트 {port}가 이미 사용 중입니다. 기존 서버 프로세스가 실행 중일 수 있습니다. 새 인스턴스를 시작하지 않습니다.")
                print("포트를 비우려면 기존 프로세스를 종료하세요. (Windows: netstat/taskkill 또는 Stop-Process)")
                raise SystemExit(1)
        except Exception:
            # 연결 실패면 사용 중이 아님 → 계속 진행
            pass

        print(f"🌐 서버 시작: {host}:{port}")
        print(f"🟢 헬스체크: /health")
        print("=" * 50)
        
        # Flask 앱 실행
        app.run(
            host=host,
            port=port,
            debug=False,  # 프로덕션 환경에서는 debug=False
            use_reloader=False
        )
        
    except Exception as startup_error:
        print(f"❌ 서버 시작 실패: {startup_error}")
        import traceback
        traceback.print_exc()
        # Railway에서 오류 로그를 볼 수 있도록 잠시 대기
        import time
        time.sleep(5)
        raise
