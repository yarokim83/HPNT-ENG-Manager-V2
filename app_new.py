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
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import logging
import base64

# PostgreSQL 데이터베이스 모듈 import
try:
    from db_postgres import (
        init_postgres_database, insert_sample_data, get_all_material_requests,
        add_material_request, update_material_request_status, delete_material_request,
        update_material_info, update_material_image, get_status_counts, backup_to_json,
        get_postgres_connection
    )
    USE_POSTGRES = True
except ImportError:
    # PostgreSQL 사용 불가시 SQLite 사용
    import sqlite3
    USE_POSTGRES = False

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
    return detect_environment() in ['render', 'railway']

def get_material_db_path():
    """자재관리 DB 경로 결정 - OneDrive 연동"""
    # 클라우드 환경에서는 기존 로컬 경로 사용
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
    """자재관리 데이터베이스 초기화 - PostgreSQL/SQLite 자동 선택"""
    env = detect_environment()
    is_railway = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID')
    
    logger.info(f"🚀 DB 초기화 시작 - 환경: {env}, Railway: {bool(is_railway)}")
    logger.info(f"PostgreSQL 사용: {USE_POSTGRES}")
    
    try:
        if USE_POSTGRES:
            # PostgreSQL 초기화
            logger.info("📊 PostgreSQL 데이터베이스 초기화 중...")
            if init_postgres_database():
                logger.info("✅ PostgreSQL 테이블 생성 완료")
                
                # 샘플 데이터 삽입
                if insert_sample_data():
                    logger.info("✅ PostgreSQL 샘플 데이터 삽입 완료")
                else:
                    logger.info("ℹ️ PostgreSQL 기존 데이터 존재")
                
                return True
            else:
                logger.error("❌ PostgreSQL 초기화 실패")
                return False
        
        else:
            # SQLite 초기화 (기존 로직)
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
        
        # 자재요청 테이블 생성
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS material_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_date TEXT NOT NULL,
            item_name TEXT NOT NULL,
            specifications TEXT,
            quantity INTEGER NOT NULL,
            urgency TEXT NOT NULL DEFAULT 'normal',
            reason TEXT,
            vendor TEXT,
            status TEXT DEFAULT 'pending',
            images TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 🔥 Railway/Render 환경에서 DB 파일이 새로 생성된 경우 다단계 자동 복구 시도
        if (is_cloud_env() or is_railway) and not db_exists:
            logger.warning(f"🚨 {env} 환경에서 DB 파일이 없어 새로 생성됨 - 다단계 자동 복구 시도")
            
            recovery_success = False
            
            # 1단계: 환경 변수에서 백업 데이터 복구 시도
            backup_json = os.environ.get('DB_BACKUP_JSON')
            if backup_json:
                try:
                    import json
                    backup_data = json.loads(backup_json)
                    if restore_db_from_backup(backup_data):
                        logger.info("✅ 환경 변수 백업으로부터 DB 자동 복구 성공")
                        recovery_success = True
                    else:
                        raise Exception("백업 복구 실패")
                except Exception as backup_error:
                    logger.error(f"환경 변수 백업 복구 실패: {backup_error}")
            
            # 2단계: GitHub 저장소에서 기본 백업 다운로드 시도 (미래 확장용)
            if not recovery_success:
                try:
                    # GitHub 또는 외부 URL에서 기본 백업 다운로드 로직 (미래 구현)
                    logger.info("🔍 외부 백업 소스 확인 중... (미래 구현 예정)")
                except Exception as external_error:
                    logger.warning(f"외부 백업 소스 접근 실패: {external_error}")
            
            # 3단계: 모든 복구 시도 실패 시 샘플 데이터 삽입
            if not recovery_success:
                insert_sample_data = True
            
            # 샘플 데이터 삽입 (백업 복구 실패 시 또는 백업이 없을 때)
            if 'insert_sample_data' in locals() and insert_sample_data:
                logger.info("📝 샘플 데이터 자동 삽입 시작")
                sample_data = [
                    ('2025-01-06', '안전모', '흰색, CE 인증', 10, 'high', '현장 안전 강화를 위해 필요', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    ('2025-01-06', '작업장갑', '면장갑, L사이즈', 20, 'normal', '작업자 보호용', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    ('2025-01-05', '전선', '2.5sq, 100m', 3, 'normal', '전기 배선 작업용', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                ]
                
                cursor.executemany('''
                    INSERT INTO material_requests 
                    (request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_data)
                
                logger.info(f"✅ {env} 환경 샘플 데이터 {len(sample_data)}개 자동 삽입 완료")
        
        # 🚂 Railway 환경에서는 항상 샘플 데이터 확인 및 강제 삽입
        if is_railway:
            cursor.execute("SELECT COUNT(*) FROM material_requests")
            record_count = cursor.fetchone()[0]
            logger.info(f"🔍 현재 DB 레코드 수: {record_count}개")
            
            if record_count == 0:
                logger.info("🚂 Railway 환경 - 빈 DB 감지, 샘플 데이터 강제 삽입")
                sample_data = [
                    ('2025-08-06', '🚂 Railway 테스트', 'Railway 배포 테스트용', 1, 'high', 'Railway 환경 DB 테스트', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    ('2025-08-06', '안전모', '흰색, CE 인증', 10, 'normal', '현장 안전용', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    ('2025-08-06', '작업장갑', '면장갑, L사이즈', 20, 'normal', '작업자 보호용', '', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                ]
                
                cursor.executemany('''
                    INSERT INTO material_requests 
                    (request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sample_data)
                
                logger.info(f"✅ Railway 환경 샘플 데이터 {len(sample_data)}개 강제 삽입 완료")
        
        conn.commit()
        conn.close()
        
        if db_exists:
            logger.info(f"✅ 기존 자재관리 DB 연결 완료: {db_path}")
        else:
            logger.info(f"✅ 새 자재관리 DB 초기화 완료: {db_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 자재관리 DB 초기화 실패: {e}")
        return False

# HTML 템플릿들
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>HPNT ENG Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="version" content="{{ version }}">
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
        .version-badge { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 20px;
        }
        h1 { font-size: 2.5em; color: #333; margin-bottom: 10px; }
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
        .btn-info { background: linear-gradient(135deg, #17a2b8 0%, #138496 100%); color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="version-badge">V2.0</div>
            <h1>HPNT ENG Manager</h1>
        </div>
        
        <div style="text-align: center;">
            <a href="/requests?v={{ version }}" class="btn btn-primary">📋 자재요청 목록</a>
            <a href="/stats?v={{ version }}" class="btn btn-info">📊 통계 보기</a>
        </div>
    </div>
</body>
</html>
'''

REQUESTS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>📋 자재요청 목록 - HPNT Manager V2.0</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header { text-align: center; margin-bottom: 40px; }
        h1 { font-size: 2.5em; color: #333; margin-bottom: 10px; }
        .btn { 
            padding: 12px 24px; 
            margin: 5px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .request-card { 
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .request-card:hover { 
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.15);
        }
        .image-thumbnail {
            width: 80px;
            height: 80px;
            border-radius: 8px;
            object-fit: cover;
            border: 2px solid #e9ecef;
            margin-right: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .image-thumbnail:hover {
            border-color: #667eea;
            transform: scale(1.05);
        }
        .request-content {
            display: flex;
            align-items: flex-start;
            gap: 15px;
        }
        .request-details {
            flex: 1;
        }
        .admin-panel {
            width: 300px;
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-left: 20px;
            border: 1px solid #e9ecef;
        }
        .admin-section {
            margin-bottom: 20px;
        }
        .admin-section h4 {
            color: #495057;
            font-size: 0.9em;
            margin-bottom: 10px;
            font-weight: 600;
        }
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 24px;
        }
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 24px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #28a745;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .admin-select {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ced4da;
            border-radius: 5px;
            font-size: 14px;
            background: white;
        }
        .admin-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: background 0.3s ease;
        }
        .admin-btn:hover {
            background: #0056b3;
        }
        .admin-btn.delete {
            background: #dc3545;
            margin-left: 5px;
        }
        .admin-btn.delete:hover {
            background: #c82333;
        }
        .main-content {
            display: flex;
            gap: 20px;
        }
        .requests-container {
            flex: 1;
        }
        .status-badge { 
            padding: 6px 12px; 
            border-radius: 15px; 
            font-size: 0.9em; 
            font-weight: 600;
            display: inline-block;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-approved { background: #d4edda; color: #155724; }
        .status-ordered { background: #cce5ff; color: #004085; }
        .status-received { background: #e2e3e5; color: #383d41; }
        .status-rejected { background: #f8d7da; color: #721c24; }
        .empty-state { text-align: center; padding: 60px 20px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 자재요청 목록</h1>
            <div style="margin-top: 20px;">
                <a href="/" class="btn btn-primary">🏠 홈으로</a>
                <a href="/add" class="btn btn-success">➕ 새 요청</a>
            </div>
        </div>
        
        <!-- 상태별 현황 대시보드 -->
        <div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3 style="margin-bottom: 10px; color: #333; font-size: 16px;">📊 상태별 현황</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px;">
                <div style="background: #f8f9fa; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #6c757d;">
                    <div style="font-size: 20px; font-weight: bold; color: #6c757d; margin-bottom: 2px;">{{ total_count }}</div>
                    <div style="font-size: 12px; color: #666;">📝 전체</div>
                </div>
                <div style="background: #fff3cd; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #856404;">
                    <div style="font-size: 20px; font-weight: bold; color: #856404; margin-bottom: 2px;">{{ status_counts.get('pending', 0) }}</div>
                    <div style="font-size: 12px; color: #856404;">🕰️ 대기중</div>
                </div>
                <div style="background: #d4edda; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #155724;">
                    <div style="font-size: 20px; font-weight: bold; color: #155724; margin-bottom: 2px;">{{ status_counts.get('approved', 0) }}</div>
                    <div style="font-size: 12px; color: #155724;">✅ 승인됨</div>
                </div>
                <div style="background: #cce5ff; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #004085;">
                    <div style="font-size: 20px; font-weight: bold; color: #004085; margin-bottom: 2px;">{{ status_counts.get('ordered', 0) }}</div>
                    <div style="font-size: 12px; color: #004085;">📦 발주완료</div>
                </div>
                <div style="background: #e2e3e5; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #383d41;">
                    <div style="font-size: 20px; font-weight: bold; color: #383d41; margin-bottom: 2px;">{{ status_counts.get('received', 0) }}</div>
                    <div style="font-size: 12px; color: #383d41;">✓ 입고완료</div>
                </div>
                <div style="background: #f8d7da; border-radius: 6px; padding: 10px; text-align: center; border-left: 3px solid #721c24;">
                    <div style="font-size: 20px; font-weight: bold; color: #721c24; margin-bottom: 2px;">{{ status_counts.get('rejected', 0) }}</div>
                    <div style="font-size: 12px; color: #721c24;">❌ 반려</div>
                </div>
            </div>
        </div>
        
        <div class="content">
            {% if requests %}
            <div class="requests-list">
                <div style="display: flex; justify-content: flex-end; align-items: center; margin-bottom: 20px;">
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <form method="GET" action="/requests" style="display: flex; gap: 10px; align-items: center;">
                            <input type="text" name="search" 
                                   value="{{ search_query if search_query else '' }}" 
                                   placeholder="자재명, 사양, 사유로 검색..." 
                                   style="padding: 8px 12px; border: 1px solid #ced4da; border-radius: 5px; width: 250px; font-size: 14px;">
                            <button type="submit" class="btn btn-secondary" style="padding: 8px 15px;">
                                🔍 검색
                            </button>
                            {% if search_query %}
                            <a href="/requests" class="btn btn-outline-secondary" style="padding: 8px 15px;">
                                ❌ 초기화
                            </a>
                            {% endif %}
                        </form>
                    </div>
                </div>
                
                {% if search_query %}
                <div style="background: #e3f2fd; padding: 10px 15px; border-radius: 5px; margin-bottom: 15px; color: #1565c0;">
                    🔍 검색 결과: "{{ search_query }}" (총 {{ requests|length }}건)
                </div>
                {% endif %}
                
                <!-- 간단한 헤더 -->
                <div style="background: #f8f9fa; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; font-weight: bold; color: #495057; border: 1px solid #dee2e6;">
                    <div style="display: grid; grid-template-columns: 50px 1fr 100px 100px 80px 170px 130px 80px; gap: 8px; align-items: center;">
                        <div>ID</div>
                        <div>자재 정보</div>
                        <div>상태</div>
                        <div>이미지</div>
                        <div>긴급도</div>
                        <div>발주업체</div>
                        <div>관리</div>
                        <div>삭제</div>
                    </div>
                </div>
                
                {% for req in requests %}
                <div class="request-item" style="background: white; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 15px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="display: grid; grid-template-columns: 50px 1fr 100px 100px 80px 170px 130px 80px; gap: 8px; align-items: center;">
                        
                        <!-- ID -->
                        <div style="font-weight: bold; color: #007bff; font-size: 16px;">
                            #{{ req[0] }}
                        </div>
                        
                        <!-- 자재 정보 -->
                        <div id="material_info_{{ req[0] }}" ondblclick="editMaterialInfo({{ req[0] }})" style="cursor: pointer;" title="더블클릭하여 수정">
                            <div id="display_mode_{{ req[0] }}">
                                <div style="font-weight: bold; font-size: 16px; color: #333; margin-bottom: 5px;">
                                    🔧 <span id="item_name_display_{{ req[0] }}">{{ req[2] }}</span>
                                </div>
                                <div style="color: #666; font-size: 13px; margin-bottom: 3px;">
                                    📅 {{ req[1] }} | 📦 <span id="quantity_display_{{ req[0] }}">{{ req[4] }}</span>개
                                </div>
                                {% if req[3] %}
                                <div style="color: #666; font-size: 12px; margin-bottom: 3px;">
                                    📋 <span id="specifications_display_{{ req[0] }}">{{ req[3] }}</span>
                                </div>
                                {% endif %}
                                {% if req[6] %}
                                <div style="color: #666; font-size: 12px;">
                                    📝 <span id="reason_display_{{ req[0] }}">{{ req[6] }}</span>
                                </div>
                                {% endif %}
                            </div>
                            
                            <div id="edit_mode_{{ req[0] }}" style="display: none;">
                                <div style="margin-bottom: 8px;">
                                    <label style="font-size: 12px; font-weight: bold; color: #333;">자재명:</label>
                                    <input type="text" id="item_name_edit_{{ req[0] }}" value="{{ req[2] }}" 
                                           style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px; font-size: 14px;">
                                </div>
                                <div style="margin-bottom: 8px;">
                                    <label style="font-size: 12px; font-weight: bold; color: #333;">수량:</label>
                                    <input type="number" id="quantity_edit_{{ req[0] }}" value="{{ req[4] }}" min="1"
                                           style="width: 80px; padding: 4px; border: 1px solid #ddd; border-radius: 3px; font-size: 14px;">
                                </div>
                                <div style="margin-bottom: 8px;">
                                    <label style="font-size: 12px; font-weight: bold; color: #333;">사양:</label>
                                    <textarea id="specifications_edit_{{ req[0] }}" 
                                              style="width: 100%; height: 50px; padding: 4px; border: 1px solid #ddd; border-radius: 3px; font-size: 12px; resize: vertical;">{{ req[3] or '' }}</textarea>
                                </div>
                                <div style="margin-bottom: 8px;">
                                    <label style="font-size: 12px; font-weight: bold; color: #333;">요청 사유:</label>
                                    <textarea id="reason_edit_{{ req[0] }}" 
                                              style="width: 100%; height: 50px; padding: 4px; border: 1px solid #ddd; border-radius: 3px; font-size: 12px; resize: vertical;">{{ req[6] or '' }}</textarea>
                                </div>
                                <div style="display: flex; gap: 5px;">
                                    <button onclick="saveMaterialInfo({{ req[0] }})" 
                                            style="padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; font-size: 11px; cursor: pointer;">
                                        저장
                                    </button>
                                    <button onclick="cancelEditMaterialInfo({{ req[0] }})" 
                                            style="padding: 5px 10px; background: #6c757d; color: white; border: none; border-radius: 3px; font-size: 11px; cursor: pointer;">
                                        취소
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 상태 -->
                        <div style="text-align: center;">
                            <span class="badge badge-{% if req[8] == 'pending' %}secondary{% elif req[8] == 'approved' %}primary{% elif req[8] == 'ordered' %}info{% elif req[8] == 'received' %}success{% else %}danger{% endif %}" 
                                  style="font-size: 13px; padding: 6px 12px; font-weight: bold;">
                                {% if req[8] == 'pending' %}🕰️ 대기중
                                {% elif req[8] == 'approved' %}✅ 승인됨
                                {% elif req[8] == 'ordered' %}📦 발주완료
                                {% elif req[8] == 'received' %}✓ 입고완료
                                {% else %}❌ 반려{% endif %}
                            </span>
                        </div>
                        
                        <!-- 이미지 -->
                        <div id="image_section_{{ req[0] }}" ondblclick="editImageInfo({{ req[0] }})" style="text-align: center; cursor: pointer;" title="더블클릭하여 이미지 수정">
                            <div id="image_display_mode_{{ req[0] }}">
                                {% if req[9] %}
                                    <div style="margin-bottom: 5px;">
                                        <span class="badge badge-success">첨부됨</span>
                                    </div>
                                    <a href="/images/{{ req[9] }}" target="_blank" 
                                       style="display: inline-block; padding: 5px 10px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 11px;">
                                        🔍 보기
                                    </a>
                                {% else %}
                                    <span style="color: #999; font-size: 12px;">이미지 없음</span>
                                {% endif %}
                            </div>
                            
                            <div id="image_edit_mode_{{ req[0] }}" style="display: none; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                <div style="margin-bottom: 8px;">
                                    <label style="font-size: 12px; font-weight: bold; color: #333;">이미지 업로드:</label>
                                    <input type="file" id="image_file_{{ req[0] }}" accept="image/*" 
                                           style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px; font-size: 11px;">
                                </div>
                                {% if req[9] %}
                                <div style="margin-bottom: 8px;">
                                    <img src="/images/{{ req[9] }}" alt="현재 이미지" 
                                         style="max-width: 80px; max-height: 60px; border: 1px solid #ddd; border-radius: 3px;">
                                    <div style="font-size: 10px; color: #666; margin-top: 2px;">현재 이미지</div>
                                </div>
                                {% endif %}
                                <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                                    <button onclick="saveImageInfo({{ req[0] }})" 
                                            style="padding: 4px 8px; background: #28a745; color: white; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">
                                        💾 저장
                                    </button>
                                    {% if req[9] %}
                                    <button onclick="deleteImageInfo({{ req[0] }})" 
                                            style="padding: 4px 8px; background: #dc3545; color: white; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">
                                        🗑️ 삭제
                                    </button>
                                    {% endif %}
                                    <button onclick="cancelEditImageInfo({{ req[0] }})" 
                                            style="padding: 4px 8px; background: #6c757d; color: white; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">
                                        취소
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 긴급도 -->
                        <div style="text-align: center;">
                            <span class="badge badge-{% if req[5] == 'high' %}danger{% elif req[5] == 'normal' %}warning{% else %}success{% endif %}" 
                                  style="font-size: 12px; padding: 5px 10px;">
                                {% if req[5] == 'high' %}🔴 높음
                                {% elif req[5] == 'normal' %}🟡 보통
                                {% else %}🟢 낮음{% endif %}
                            </span>
                        </div>
                        
                        <!-- 발주업체 -->
                        <div style="display: flex; align-items: center; gap: 5px;">
                            <div>
                                {% if req[7] and req[7] != '대기중' %}
                                    <input type="text" class="form-control form-control-sm" id="vendor_{{ req[0] }}" 
                                           list="vendor_list_{{ req[0] }}" 
                                           value="{{ req[7] }}" 
                                           placeholder="대기중" 
                                           style="width: 120px; font-size: 12px; padding: 5px 8px;">
                                {% else %}
                                    <input type="text" class="form-control form-control-sm" id="vendor_{{ req[0] }}" 
                                           list="vendor_list_{{ req[0] }}" 
                                           value="" 
                                           placeholder="대기중" 
                                           style="width: 120px; font-size: 12px; padding: 5px 8px; color: #999;">
                                {% endif %}
                                <datalist id="vendor_list_{{ req[0] }}">
                                    <option value="대기중">
                                    <option value="ABC상사">
                                    <option value="XYZ공업">
                                    <option value="한국자재">
                                    <option value="대한공급">
                                    <option value="삼성물산">
                                    <option value="LG상사">
                                    <option value="현대건설">
                                </datalist>
                            </div>
                            <button onclick="updateRequest({{ req[0] }})" 
                                    style="display: inline-block; padding: 8px 10px; background: #28a745; color: white; text-decoration: none; border: none; border-radius: 4px; font-size: 11px; cursor: pointer; min-width: 35px;">
                                ✓
                            </button>
                        </div>
                        
                        <!-- 관리 -->
                        <div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="flex: 1;">
                                    <select class="form-control form-control-sm" id="status_{{ req[0] }}" 
                                            style="width: 100%; font-size: 12px; padding: 5px 8px;">
                                        <option value="pending" {% if req[8] == 'pending' %}selected{% endif %}>대기중</option>
                                        <option value="approved" {% if req[8] == 'approved' %}selected{% endif %}>승인됨</option>
                                        <option value="ordered" {% if req[8] == 'ordered' %}selected{% endif %}>발주완료</option>
                                        <option value="received" {% if req[8] == 'received' %}selected{% endif %}>입고완료</option>
                                        <option value="rejected" {% if req[8] == 'rejected' %}selected{% endif %}>반려</option>
                                    </select>
                                </div>
                                <button onclick="updateRequest({{ req[0] }})" 
                                        style="display: inline-block; padding: 8px 10px; background: #007bff; color: white; text-decoration: none; border: none; border-radius: 4px; font-size: 11px; cursor: pointer; min-width: 35px;">
                                    ✓
                                </button>
                            </div>
                        </div>
                        
                        <!-- 삭제 -->
                        <div style="text-align: center; display: flex; flex-direction: column; gap: 5px;">
                            <button onclick="copyRequest({{ req[0] }})" 
                                    style="background: #28a745; color: white; border: none; border-radius: 4px; font-size: 11px; padding: 6px 12px; cursor: pointer;">
                                복사
                            </button>
                            <button onclick="deleteRequest({{ req[0] }})" 
                                    style="background: #dc3545; color: white; border: none; border-radius: 4px; font-size: 11px; padding: 6px 12px; cursor: pointer;">
                                삭제
                            </button>
                        </div>
                        
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">
                <h3>📭 등록된 자재요청이 없습니다</h3>
                <p>새로운 자재요청을 등록해보세요!</p>
                <a href="/add" class="btn btn-success" style="margin-top: 20px;">➕ 첫 요청 등록하기</a>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        // 자재요청 상태 관리 JavaScript 기능
        function updateRequest(requestId) {
            const vendorInput = document.getElementById(`vendor_${requestId}`);
            const statusSelect = document.getElementById(`status_${requestId}`);
            
            const vendor = vendorInput.value;
            const status = statusSelect.value;
            
            // AJAX 요청으로 서버에 업데이트 전송
            fetch(`/admin/update/${requestId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    vendor: vendor,
                    status: status
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ 성공적으로 업데이트되었습니다!');
                    location.reload(); // 페이지 새로고침
                } else {
                    alert('❌ 업데이트 실패: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ 업데이트 중 오류가 발생했습니다.');
            });
        }
        
        function copyRequest(requestId) {
            if (confirm('이 자재요청을 복사하여 새 요청으로 등록하시겠습니까?')) {
                fetch(`/admin/copy/${requestId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ 성공적으로 복사되었습니다!');
                        location.reload();
                    } else {
                        alert('❌ 복사 실패: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('❌ 복사 중 오류가 발생했습니다.');
                });
            }
        }
        
        // 자재정보 인라인 편집 기능
        function editMaterialInfo(requestId) {
            document.getElementById(`display_mode_${requestId}`).style.display = 'none';
            document.getElementById(`edit_mode_${requestId}`).style.display = 'block';
        }
        
        function cancelEditMaterialInfo(requestId) {
            document.getElementById(`display_mode_${requestId}`).style.display = 'block';
            document.getElementById(`edit_mode_${requestId}`).style.display = 'none';
        }
        
        function saveMaterialInfo(requestId) {
            const itemName = document.getElementById(`item_name_edit_${requestId}`).value;
            const quantity = document.getElementById(`quantity_edit_${requestId}`).value;
            const specifications = document.getElementById(`specifications_edit_${requestId}`).value;
            const reason = document.getElementById(`reason_edit_${requestId}`).value;
            
            if (!itemName.trim()) {
                alert('자재명은 필수 입력 항목입니다.');
                return;
            }
            
            if (quantity < 1) {
                alert('수량은 1 이상이어야 합니다.');
                return;
            }
            
            fetch(`/admin/edit/${requestId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    item_name: itemName,
                    quantity: parseInt(quantity),
                    specifications: specifications,
                    reason: reason
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ 성공적으로 수정되었습니다!');
                    location.reload();
                } else {
                    alert('❌ 수정 실패: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ 수정 중 오류가 발생했습니다.');
            });
        }
        
        // 이미지 인라인 편집 기능
        function editImageInfo(requestId) {
            document.getElementById(`image_display_mode_${requestId}`).style.display = 'none';
            document.getElementById(`image_edit_mode_${requestId}`).style.display = 'block';
        }
        
        function cancelEditImageInfo(requestId) {
            document.getElementById(`image_display_mode_${requestId}`).style.display = 'block';
            document.getElementById(`image_edit_mode_${requestId}`).style.display = 'none';
        }
        
        function saveImageInfo(requestId) {
            const fileInput = document.getElementById(`image_file_${requestId}`);
            const file = fileInput.files[0];
            
            if (!file) {
                alert('업로드할 이미지 파일을 선택해주세요.');
                return;
            }
            
            // 파일 크기 체크 (5MB 제한)
            if (file.size > 5 * 1024 * 1024) {
                alert('이미지 파일 크기는 5MB 이하여야 합니다.');
                return;
            }
            
            // 이미지 파일 형식 체크
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드 가능합니다.');
                return;
            }
            
            const formData = new FormData();
            formData.append('image', file);
            
            fetch(`/admin/image/${requestId}`, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ 이미지가 성공적으로 업데이트되었습니다!');
                    location.reload();
                } else {
                    alert('❌ 이미지 업데이트 실패: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ 이미지 업데이트 중 오류가 발생했습니다.');
            });
        }
        
        function deleteImageInfo(requestId) {
            if (confirm('현재 이미지를 삭제하시겠습니까?')) {
                fetch(`/admin/image/${requestId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ 이미지가 성공적으로 삭제되었습니다!');
                        location.reload();
                    } else {
                        alert('❌ 이미지 삭제 실패: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('❌ 이미지 삭제 중 오류가 발생했습니다.');
                });
            }
        }
        
        function deleteRequest(requestId) {
            if (confirm('이 자재요청을 삭제하시겠습니까?')) {
                fetch(`/admin/delete/${requestId}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (response.ok) {
                        location.reload();
                    } else {
                        alert('삭제 중 오류가 발생했습니다.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('삭제 중 오류가 발생했습니다.');
                });
            }
        }
        

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
            
            <form method="POST" enctype="multipart/form-data">
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
                    <div class="image-paste-area" id="imagePasteArea">
                        <div class="paste-icon">📋</div>
                        <div class="paste-text">스크린샷을 캡쳐한 후 여기에 붙여넣기 (Ctrl+V)</div>
                        <div class="paste-help">또는 이 영역을 클릭해서 이미지를 붙여넣으세요</div>
                    </div>
                    <div class="image-preview" id="imagePreview" style="display: none;"></div>
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
        // 이미지 붙여넣기 기능
        const imagePasteArea = document.getElementById('imagePasteArea');
        const imagePreview = document.getElementById('imagePreview');
        const imageDataInput = document.getElementById('imageData');
        
        // 클립보드에서 이미지 붙여넣기
        function handlePaste(e) {
            const items = e.clipboardData.items;
            
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    e.preventDefault();
                    const blob = items[i].getAsFile();
                    handleImageFile(blob);
                    break;
                }
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
        
        // 이벤트 리스너 등록
        document.addEventListener('paste', handlePaste);
        imagePasteArea.addEventListener('click', function() {
            // 클릭 시 포커스를 주어 붙여넣기가 가능하도록
            this.focus();
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
    """메인 홈페이지 - 캐시 무효화 리다이렉트"""
    # 버전 파라미터가 없으면 리다이렉트
    version_param = request.args.get('v')
    if not version_param:
        return redirect(f'/?v={APP_VERSION}')
    
    try:
        env = detect_environment().upper()
        db_location = "로컬 DB (프로젝트/db)"
        
        return render_template_string(HOME_TEMPLATE, 
                                    environment=env,
                                    db_location=db_location,
                                    version=APP_VERSION)
    except Exception as e:
        logger.error(f"홈페이지 로드 실패: {e}")
        return f"<h1>❌ 오류</h1><p>페이지를 불러올 수 없습니다: {e}</p>"

@app.route('/requests')
def requests_page():
    try:
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        
        if USE_POSTGRES:
            # PostgreSQL 사용
            status_counts = get_status_counts()
            total_count = sum(status_counts.values())
            
            # 모든 요청 조회 (필터링은 Python에서 처리)
            all_requests = get_all_material_requests()
            
            # 상태 필터링
            if status_filter != 'all':
                requests = [req for req in all_requests if req[8] == status_filter]
            else:
                requests = all_requests
            
            # 검색 필터링
            if search_query:
                search_lower = search_query.lower()
                requests = [
                    req for req in requests 
                    if (search_lower in str(req[1]).lower() or  # item_name
                        search_lower in str(req[3] or '').lower() or  # specifications
                        search_lower in str(req[4] or '').lower())  # reason
                ]
        
        else:
            # SQLite 사용 (기존 로직)
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
            
            query = "SELECT * FROM material_requests WHERE 1=1"
            params = []
            
            if status_filter != 'all':
                query += " AND status = ?"
                params.append(status_filter)
            
            if search_query:
                query += " AND (item_name LIKE ? OR specifications LIKE ? OR reason LIKE ?)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            query += " ORDER BY id DESC"
            
            cursor.execute(query, params)
            requests = cursor.fetchall()
            conn.close()
        
        return render_template_string(REQUESTS_TEMPLATE, 
                                    requests=requests,
                                    status_filter=status_filter,
                                    search_query=search_query,
                                    status_counts=status_counts,
                                    total_count=total_count)
    except Exception as e:
        logger.error(f"자재요청 목록 조회 실패: {e}")
        return f"<h1>❌ 오류</h1><p>목록을 불러올 수 없습니다: {e}</p><a href='/'>← 홈으로</a>"

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
            
            if not item_name:
                return render_template_string(ADD_TEMPLATE, error="자재명은 필수 입력 항목입니다.")
            
            if quantity <= 0:
                return render_template_string(ADD_TEMPLATE, error="수량은 1 이상이어야 합니다.")
            
            # 이미지 처리
            image_filename = None
            if image_data and image_data.startswith('data:image/'):
                try:
                    # Base64 이미지 데이터 파싱
                    header, encoded = image_data.split(',', 1)
                    image_format = header.split(';')[0].split('/')[1]  # png, jpeg 등
                    
                    # 이미지 저장 폴더 생성 (OneDrive 연동)
                    images_dir = get_images_dir_path()
                    
                    # 고유한 파일명 생성 (타임스탬프 + 자재명)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_item_name = ''.join(c for c in item_name if c.isalnum() or c in (' ', '-', '_')).strip()[:20]
                    image_filename = f"{timestamp}_{safe_item_name}.{image_format}"
                    image_path = os.path.join(images_dir, image_filename)
                    
                    # Base64 디코딩 후 파일 저장
                    import base64
                    with open(image_path, 'wb') as f:
                        f.write(base64.b64decode(encoded))
                    
                    logger.info(f"이미지 저장 완료: {image_filename}")
                    
                except Exception as img_error:
                    logger.warning(f"이미지 저장 실패: {img_error}")
                    # 이미지 저장 실패해도 요청 등록은 계속 진행
                    image_filename = None
            
            # 데이터베이스에 자재요청 추가
            if USE_POSTGRES:
                # PostgreSQL 사용
                success = add_material_request(
                    item_name=item_name,
                    quantity=quantity,
                    specifications=specifications,
                    reason=reason,
                    urgency=urgency,
                    images=image_filename
                )
                
                if not success:
                    raise Exception("PostgreSQL 데이터 삽입 실패")
            
            else:
                # SQLite 사용 (기존 로직)
                db_path = get_material_db_path()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # DB 테이블 구조에 맞게 INSERT (이미지 파일명 포함)
                cursor.execute('''
                    INSERT INTO material_requests 
                    (request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                ''', (datetime.now().strftime('%Y-%m-%d'), item_name, specifications, quantity, urgency, reason, vendor, image_filename))
                
                conn.commit()
                conn.close()
            
            logger.info(f"새 자재요청 등록: {item_name} x {quantity} (이미지: {'있음' if image_filename else '없음'})")
            return redirect('/requests')
            
        except ValueError:
            return render_template_string(ADD_TEMPLATE, error="수량은 숫자로 입력해주세요.")
        except Exception as e:
            logger.error(f"자재요청 등록 실패: {e}")
            return render_template_string(ADD_TEMPLATE, error=f"등록 중 오류가 발생했습니다: {e}")
    
    return render_template_string(ADD_TEMPLATE)

@app.route('/stats')
def stats_page():
    """통계 페이지"""
    return "<h1>📊 통계</h1><p>곧 구현될 예정입니다!</p><a href='/'>← 홈으로</a>"

@app.route('/images/<filename>')
def serve_image(filename):
    """이미지 파일 서빙 - OneDrive 연동"""
    try:
        images_dir = get_images_dir_path()
        return send_from_directory(images_dir, filename)
    except Exception as e:
        logger.error(f"이미지 서빙 실패: {e}")
        return "Image not found", 404

@app.route('/admin/update/<int:request_id>', methods=['POST'])
def admin_update_request(request_id):
    """관리자 자재요청 업데이트"""
    try:
        data = request.get_json()
        vendor = data.get('vendor', '')
        status = data.get('status', 'pending')
        is_active = data.get('is_active', False)
        
        if USE_POSTGRES:
            # PostgreSQL 사용
            success = update_material_request_status(request_id, status, vendor)
            
            if not success:
                return jsonify({'success': False, 'error': '요청을 찾을 수 없거나 업데이트에 실패했습니다.'}), 404
        
        else:
            # SQLite 사용 (기존 로직)
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
            if USE_POSTGRES:
                # PostgreSQL에서 기존 이미지 정보 조회
                conn = get_postgres_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT images FROM material_requests WHERE id = %s", (request_id,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        old_image_path = os.path.join(get_images_dir_path(), result[0])
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            logger.info(f"기존 이미지 삭제: {result[0]}")
                    cursor.close()
                    conn.close()
            else:
                # SQLite에서 기존 이미지 정보 조회
                db_path = get_material_db_path()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT images FROM material_requests WHERE id = ?", (request_id,))
                result = cursor.fetchone()
                if result and result[0]:
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
            if USE_POSTGRES:
                success = update_material_image(request_id, filename)
                if not success:
                    raise Exception("PostgreSQL 이미지 업데이트 실패")
            else:
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
            
            if USE_POSTGRES:
                # PostgreSQL에서 이미지 정보 조회
                conn = get_postgres_connection()
                if not conn:
                    return jsonify({'success': False, 'error': '데이터베이스 연결 실패'}), 500
                
                cursor = conn.cursor()
                cursor.execute("SELECT images FROM material_requests WHERE id = %s", (request_id,))
                result = cursor.fetchone()
                
                if not result:
                    cursor.close()
                    conn.close()
                    return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
                
                image_filename = result[0]
                cursor.close()
                conn.close()
                
            else:
                # SQLite에서 이미지 정보 조회
                db_path = get_material_db_path()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT images FROM material_requests WHERE id = ?", (request_id,))
                result = cursor.fetchone()
                
                if not result:
                    conn.close()
                    return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
                
                image_filename = result[0]
                conn.close()
            
            if not image_filename:
                return jsonify({'success': False, 'error': '삭제할 이미지가 없습니다.'}), 400
            
            # 이미지 파일 삭제
            image_path = os.path.join(get_images_dir_path(), image_filename)
            if os.path.exists(image_path):
                os.remove(image_path)
                logger.info(f"이미지 파일 삭제: {image_filename}")
            
            # DB에서 이미지 정보 제거
            if USE_POSTGRES:
                success = update_material_image(request_id, None)
                if not success:
                    return jsonify({'success': False, 'error': 'PostgreSQL 이미지 삭제 실패'}), 500
            else:
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

@app.route('/admin/edit/<int:request_id>', methods=['POST'])
def admin_edit_material_info(request_id):
    """관리자 자재정보 수정"""
    try:
        data = request.get_json()
        item_name = data.get('item_name', '').strip()
        quantity = data.get('quantity', 1)
        specifications = data.get('specifications', '').strip()
        reason = data.get('reason', '').strip()
        
        # 입력 값 검증
        if not item_name:
            return jsonify({'success': False, 'error': '자재명은 필수 입력 항목입니다.'}), 400
        
        if quantity < 1:
            return jsonify({'success': False, 'error': '수량은 1 이상이어야 합니다.'}), 400
        
        # 자재정보 업데이트
        if USE_POSTGRES:
            # PostgreSQL 사용
            success = update_material_info(request_id, item_name, quantity, specifications, reason)
            
            if not success:
                return jsonify({'success': False, 'error': '수정할 요청을 찾을 수 없거나 업데이트에 실패했습니다.'}), 404
        
        else:
            # SQLite 사용 (기존 로직)
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
                return jsonify({'success': False, 'error': '수정할 요청을 찾을 수 없습니다.'}), 404
            
            conn.commit()
            conn.close()
        
        logger.info(f"자재정보 수정: ID {request_id} - {item_name} x {quantity}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"자재정보 수정 실패: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/copy/<int:request_id>', methods=['POST'])
def admin_copy_request(request_id):
    """관리자 자재요청 복사"""
    try:
        if USE_POSTGRES:
            # PostgreSQL에서 기존 요청 정보 조회
            conn = get_postgres_connection()
            if not conn:
                return jsonify({'success': False, 'error': '데이터베이스 연결 실패'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_name, specifications, quantity, urgency, reason, images
                FROM material_requests WHERE id = %s
            """, (request_id,))
            result = cursor.fetchone()
            
            if not result:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': '복사할 요청을 찾을 수 없습니다.'}), 404
            
            item_name, specifications, quantity, urgency, reason, images = result
            cursor.close()
            conn.close()
            
            # PostgreSQL 함수로 새 요청 추가
            success = add_material_request(
                item_name=item_name,
                quantity=quantity,
                specifications=specifications,
                reason=reason,
                urgency=urgency,
                images=images
            )
            
            if not success:
                return jsonify({'success': False, 'error': 'PostgreSQL 복사 실패'}), 500
            
            logger.info(f"자재요청 복사: ID {request_id} ({item_name})")
            return jsonify({'success': True})
        
        else:
            # SQLite 사용 (기존 로직)
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
            
            # 새로운 자재요청으로 등록 (상태는 pending, 발주업체는 비움)
            cursor.execute("""
                INSERT INTO material_requests 
                (request_date, item_name, specifications, quantity, urgency, reason, vendor, status, images)
                VALUES (?, ?, ?, ?, ?, ?, '', 'pending', ?)
            """, (datetime.now().strftime('%Y-%m-%d'), item_name, specifications, quantity, urgency, reason, images))
            
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
        image_filename = None
        
        if USE_POSTGRES:
            # PostgreSQL에서 이미지 정보 조회 후 삭제
            conn = get_postgres_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT images FROM material_requests WHERE id = %s", (request_id,))
                result = cursor.fetchone()
                image_filename = result[0] if result and result[0] else None
                cursor.close()
                conn.close()
            
            # PostgreSQL 함수로 삭제
            success = delete_material_request(request_id)
            
            if not success:
                return jsonify({'success': False, 'error': '요청을 찾을 수 없거나 삭제에 실패했습니다.'}), 404
        
        else:
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
            
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({'success': False, 'error': '요청을 찾을 수 없습니다.'}), 404
            
            conn.commit()
            conn.close()
            
            # SQLite에서만 ID 재정렬 수행
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
            backup_json = json.dumps(backup_data, ensure_ascii=False, separators=(',', ':'))
            
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


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 HPNT ENG Manager V2.0 시작")
    print("=" * 50)

    # 실행 환경 정보 출력
    env = detect_environment()
    print(f"실행 환경: {env}")

    # DB 초기화
    if init_material_database():
        db_path = get_material_db_path()
        print(f"DB 경로: {db_path}")
        print("DB 초기화 완료")
    else:
        print("⚠️ DB 초기화 실패")

    # Railway 환경에서는 PORT 환경 변수 사용
    port = int(os.environ.get('PORT', 5001))
    host = '0.0.0.0'  # Railway에서는 모든 인터페이스에서 수신해야 함
    
    print(f"서버 시작: {host}:{port}")
    print("=" * 50)
    
    # Flask 앱 실행
    app.run(
        host=host,
        port=port,
        debug=False  # 프로덕션 환경에서는 debug=False
    )
    env = detect_environment()
    print(f"📱 실행 환경: {env}")
    
    # DB 초기화
    if init_material_database():
        db_path = get_material_db_path()
        print(f"📊 DB 경로: {db_path}")
        
        # 포트 설정 (충돌 방지를 위해 5001 사용)
        port = int(os.environ.get('PORT', 5001))
        host = '0.0.0.0' if is_cloud_env() else '127.0.0.1'
        
        print(f"🌐 서버 시작: http://{host}:{port}")
        print("✨ V2.0 경량화 완료!")
        
        app.run(host=host, port=port, debug=not is_cloud_env())
    else:
        print("❌ DB 초기화 실패로 서버를 시작할 수 없습니다.")
