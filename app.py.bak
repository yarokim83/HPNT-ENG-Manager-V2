#!/usr/bin/env python3
"""
HPNT_ENG_Manager V2.0 - 경량화된 자재관리 시스템
iPad 및 크로스 플랫폼 지원
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'hpnt-manager-v2-2025'

# 환경 감지
def detect_environment():
    """실행 환경 감지"""
    if os.environ.get('RENDER'):
        return 'render'
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

def get_icloud_drive_path():
    """iCloud Drive 경로 감지"""
    possible_paths = [
        # Windows
        os.path.expanduser('~/iCloudDrive'),
        os.path.join(os.path.expanduser('~'), 'iCloud Drive'),
        # macOS
        os.path.expanduser('~/Library/Mobile Documents/com~apple~CloudDocs'),
        # iPad/iOS
        os.path.expanduser('~/Documents/iCloud Drive'),
        '/private/var/mobile/Library/Mobile Documents/com~apple~CloudDocs',
        # Linux/iSH
        '/mnt/icloud'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"iCloud Drive 경로 발견: {path}")
            return path
    
    raise Exception("iCloud Drive 경로를 찾을 수 없습니다")

def get_material_db_path():
    """자재관리 DB 경로 결정"""
    # 프로젝트 내 db 폴더 사용
    if getattr(sys, 'frozen', False):
        # 실행파일 환경
        current_dir = os.path.dirname(sys.executable)
    else:
        # 스크립트 환경
        current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # db 폴더 경로 생성
    db_folder = os.path.join(current_dir, 'db')
    
    # db 폴더가 없으면 생성
    if not os.path.exists(db_folder):
        os.makedirs(db_folder, exist_ok=True)
        logger.info(f"DB 폴더 생성: {db_folder}")
    
    db_path = os.path.join(db_folder, 'material_rq.db')
    logger.info(f"로컬 DB 경로: {db_path}")
    return db_path

def init_material_database():
    """자재관리 데이터베이스 초기화"""
    db_path = get_material_db_path()
    
    try:
        # 데이터베이스 디렉토리 생성
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"DB 디렉토리 생성: {db_dir}")
        
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
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ 자재관리 DB 초기화 완료: {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 자재관리 DB 초기화 실패: {e}")
        return False

# Flask 라우트 함수들
@app.route('/')
def home():
    """메인 홈페이지"""
    try:
        env = detect_environment().upper()
        db_location = "로컬 DB (프로젝트/db)"
        
        return render_template_string(HOME_TEMPLATE, 
                                    environment=env,
                                    db_location=db_location)
    except Exception as e:
        logger.error(f"홈페이지 로드 실패: {e}")
        return f"<h1>❌ 오류</h1><p>페이지를 불러올 수 없습니다: {e}</p>"

@app.route('/requests')
def requests_page():
    """자재요청 목록 페이지"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        
        query = "SELECT * FROM material_requests WHERE 1=1"
        params = []
        
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        
        if search_query:
            query += " AND (item_name LIKE ? OR specifications LIKE ? OR reason LIKE ?)"
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        requests = cursor.fetchall()
        conn.close()
        
        return render_template_string(REQUESTS_TEMPLATE, 
                                    requests=requests,
                                    status_filter=status_filter,
                                    search_query=search_query)
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
            
            if not item_name:
                return render_template_string(ADD_TEMPLATE, error="자재명은 필수 입력 항목입니다.")
            
            if quantity <= 0:
                return render_template_string(ADD_TEMPLATE, error="수량은 1 이상이어야 합니다.")
            
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # DB 테이블 구조에 맞게 INSERT
            cursor.execute('''
                INSERT INTO material_requests 
                (request_date, item_name, specifications, quantity, urgency, reason, vendor, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (datetime.now().strftime('%Y-%m-%d'), item_name, specifications, quantity, urgency, reason, vendor))
            
            conn.commit()
            conn.close()
            
            logger.info(f"새 자재요청 등록: {item_name} x {quantity}")
            return redirect('/requests')
            
        except ValueError:
            return render_template_string(ADD_TEMPLATE, error="수량은 숫자로 입력해주세요.")
        except Exception as e:
            logger.error(f"자재요청 등록 실패: {e}")
            return render_template_string(ADD_TEMPLATE, error=f"등록 중 오류가 발생했습니다: {e}")
    
    return render_template_string(ADD_TEMPLATE)

@app.route('/request/<int:request_id>')
def request_detail(request_id):
    """자재요청 상세 페이지"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM material_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req:
            conn.close()
            return f"<h1>❌ 오류</h1><p>요청을 찾을 수 없습니다.</p><a href='/requests'>← 목록으로</a>"
        
        conn.close()
        return render_template_string(DETAIL_TEMPLATE, request=req)
        
    except Exception as e:
        logger.error(f"자재요청 상세 조회 실패: {e}")
        return f"<h1>❌ 오류</h1><p>상세 정보를 불러올 수 없습니다: {e}</p><a href='/requests'>← 목록으로</a>"

@app.route('/request/<int:request_id>/status', methods=['POST'])
def update_request_status(request_id):
    """자재요청 상태 변경"""
    try:
        new_status = request.form.get('status')
        valid_statuses = ['pending', 'approved', 'ordered', 'received', 'rejected']
        
        if new_status not in valid_statuses:
            return jsonify({'error': '유효하지 않은 상태입니다.'}), 400
        
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE material_requests SET status = ? WHERE id = ?", 
            (new_status, request_id)
        )
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': '요청을 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"자재요청 {request_id} 상태 변경: {new_status}")
        return redirect(f'/request/{request_id}')
        
    except Exception as e:
        logger.error(f"상태 변경 실패: {e}")
        return jsonify({'error': f'상태 변경 중 오류가 발생했습니다: {e}'}), 500

@app.route('/stats')
def stats_page():
    """통계 페이지"""
    return "<h1>📊 통계</h1><p>곧 구현될 예정입니다!</p><a href='/'>← 홈으로</a>"

# 요청 상세 페이지 템플릿
DETAIL_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>📋 요청 상세 - HPNT Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 900px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            border-radius: 25px; 
            overflow: hidden;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
        }
        .header { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; 
            padding: 30px; 
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 40px; }
        .detail-card { 
            background: white; 
            border-radius: 20px; 
            padding: 30px; 
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border-left: 5px solid #4facfe;
        }
        .detail-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 25px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .detail-title { 
            font-size: 2em; 
            font-weight: 700; 
            color: #333;
        }
        .status-badge { 
            padding: 10px 20px; 
            border-radius: 25px; 
            font-size: 1.1em; 
            font-weight: 600;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-approved { background: #d1ecf1; color: #0c5460; }
        .status-ordered { background: #d4edda; color: #155724; }
        .status-received { background: #e2e3e5; color: #383d41; }
        .status-rejected { background: #f8d7da; color: #721c24; }
        .detail-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 25px;
        }
        .detail-item { 
            padding: 20px; 
            background: #f8f9fa; 
            border-radius: 15px;
        }
        .detail-label { 
            font-weight: 600; 
            color: #495057; 
            margin-bottom: 8px; 
            font-size: 1.1em;
        }
        .detail-value { 
            color: #333; 
            font-size: 1.1em; 
            line-height: 1.5;
        }
        .btn { 
            padding: 12px 25px; 
            border: none; 
            border-radius: 25px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-block;
            margin: 5px;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-warning { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: white; }
        .btn-danger { background: linear-gradient(135deg, #dc3545 0%, #e83e8c 100%); color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .status-actions { 
            background: #f8f9fa; 
            padding: 25px; 
            border-radius: 15px; 
            margin-top: 25px;
        }
        .status-actions h3 { 
            margin-bottom: 20px; 
            color: #333;
        }
        .action-buttons { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 10px;
        }
        .urgency-high { color: #dc3545; }
        .urgency-normal { color: #ffc107; }
        .urgency-low { color: #28a745; }
        @media (max-width: 768px) {
            .detail-header { flex-direction: column; text-align: center; }
            .detail-grid { grid-template-columns: 1fr; }
            .action-buttons { flex-direction: column; }
            .content { padding: 25px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 요청 상세</h1>
            <p>자재요청 상세 정보 및 상태 관리</p>
        </div>
        
        <div class="content">
            <div class="detail-card">
                <div class="detail-header">
                    <div class="detail-title">{{ request[2] }}</div>
                    <div class="status-badge status-{{ request[7] }}">
                        {% if request[7] == 'pending' %}🟡 대기중
                        {% elif request[7] == 'approved' %}🟢 승인됨
                        {% elif request[7] == 'ordered' %}🔵 발주됨
                        {% elif request[7] == 'received' %}⚪ 입고됨
                        {% elif request[7] == 'rejected' %}🔴 반려됨
                        {% endif %}
                    </div>
                </div>
                
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">📦 수량</div>
                        <div class="detail-value">{{ request[4] }}개</div>
                    </div>
                    
                    <div class="detail-item">
                        <div class="detail-label">⚡ 긴급도</div>
                        <div class="detail-value">
                            {% if request[5] == 'high' %}
                                <span class="urgency-high">🔴 높음</span>
                            {% elif request[5] == 'normal' %}
                                <span class="urgency-normal">🟡 보통</span>
                            {% else %}
                                <span class="urgency-low">🟢 낮음</span>
                            {% endif %}
                        </div>
                    </div>
                    
                    <div class="detail-item">
                        <div class="detail-label">📅 등록일</div>
                        <div class="detail-value">{{ request[10] }}</div>
                    </div>
                    
                    <div class="detail-item">
                        <div class="detail-label">👤 요청자</div>
                        <div class="detail-value">{{ request[1] }}</div>
                    </div>
                </div>
                
                {% if request[3] %}
                <div class="detail-item" style="margin-top: 25px;">
                    <div class="detail-label">📋 사양 및 규격</div>
                    <div class="detail-value">{{ request[3] }}</div>
                </div>
                {% endif %}
                
                {% if request[6] %}
                <div class="detail-item" style="margin-top: 25px;">
                    <div class="detail-label">📝 요청 사유</div>
                    <div class="detail-value">{{ request[6] }}</div>
                </div>
                {% endif %}
                
                {% if request[8] %}
                <div class="detail-item" style="margin-top: 25px;">
                    <div class="detail-label">🏢 선호 업체</div>
                    <div class="detail-value">{{ request[8] }}</div>
                </div>
                {% endif %}
            </div>
            
            <div class="status-actions">
                <h3>🔄 상태 변경</h3>
                <div class="action-buttons">
                    <form method="POST" action="/request/{{ request[0] }}/status" style="display: inline;">
                        <input type="hidden" name="status" value="pending">
                        <button type="submit" class="btn btn-secondary"
                                {% if request[7] == 'pending' %}disabled{% endif %}>
                            🟡 대기중으로 변경
                        </button>
                    </form>
                    
                    <form method="POST" action="/request/{{ request[0] }}/status" style="display: inline;">
                        <input type="hidden" name="status" value="approved">
                        <button type="submit" class="btn btn-success"
                                {% if request[7] == 'approved' %}disabled{% endif %}>
                            ✅ 승인
                        </button>
                    </form>
                    
                    <form method="POST" action="/request/{{ request[0] }}/status" style="display: inline;">
                        <input type="hidden" name="status" value="ordered">
                        <button type="submit" class="btn btn-primary"
                                {% if request[7] == 'ordered' %}disabled{% endif %}>
                            📦 발주
                        </button>
                    </form>
                    
                    <form method="POST" action="/request/{{ request[0] }}/status" style="display: inline;">
                        <input type="hidden" name="status" value="received">
                        <button type="submit" class="btn btn-success"
                                {% if request[7] == 'received' %}disabled{% endif %}>
                            🎉 입고 완료
                        </button>
                    </form>
                    
                    <form method="POST" action="/request/{{ request[0] }}/status" style="display: inline;">
                        <input type="hidden" name="status" value="rejected">
                        <button type="submit" class="btn btn-danger"
                                {% if request[7] == 'rejected' %}disabled{% endif %}>
                            ❌ 반려
                        </button>
                    </form>
                </div>
            </div>
            
            <div style="margin-top: 30px; text-align: center;">
                <a href="/requests" class="btn btn-primary">📋 목록으로</a>
                <a href="/" class="btn btn-secondary">🏠 홈으로</a>
            </div>
        </div>
    </div>
</body>
</html>
'''

# 새 요청 등록 페이지 템플릿
ADD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>➕ 새 요청 등록 - HPNT Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
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
            border-radius: 25px; 
            overflow: hidden;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
        }
        .header { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; 
            padding: 30px; 
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 40px; }
        .form-group { margin-bottom: 25px; }
        .form-group label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600; 
            color: #333;
            font-size: 1.1em;
        }
        .form-control { 
            width: 100%; 
            padding: 15px 20px; 
            border: 2px solid #e0e0e0; 
            border-radius: 15px; 
            font-size: 16px;
            outline: none;
            transition: all 0.3s ease;
            background: white;
        }
        .form-control:focus { 
            border-color: #4facfe; 
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }
        .form-control.textarea { 
            min-height: 100px; 
            resize: vertical;
            font-family: inherit;
        }
        .form-row { 
            display: grid; 
            grid-template-columns: 2fr 1fr; 
            gap: 20px;
        }
        .btn { 
            padding: 15px 30px; 
            border: none; 
            border-radius: 25px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-block;
            margin: 10px 10px 10px 0;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .btn-block { width: 100%; text-align: center; }
        .alert { 
            padding: 15px 20px; 
            border-radius: 15px; 
            margin-bottom: 25px;
            font-weight: 500;
        }
        .alert-danger { 
            background: #f8d7da; 
            color: #721c24; 
            border: 1px solid #f5c6cb;
        }
        .required { color: #e74c3c; }
        .form-help { 
            font-size: 0.9em; 
            color: #666; 
            margin-top: 5px;
        }
        .urgency-options { 
            display: grid; 
            grid-template-columns: repeat(3, 1fr); 
            gap: 10px;
        }
        .urgency-option { 
            position: relative;
        }
        .urgency-option input[type="radio"] { 
            position: absolute; 
            opacity: 0;
        }
        .urgency-option label { 
            display: block; 
            padding: 12px; 
            border: 2px solid #e0e0e0; 
            border-radius: 10px; 
            text-align: center; 
            cursor: pointer; 
            transition: all 0.3s ease;
            margin-bottom: 0;
        }
        .urgency-option input[type="radio"]:checked + label { 
            border-color: #4facfe; 
            background: rgba(79, 172, 254, 0.1);
        }
        @media (max-width: 768px) {
            .form-row { grid-template-columns: 1fr; }
            .urgency-options { grid-template-columns: 1fr; }
            .content { padding: 25px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>➕ 새 요청 등록</h1>
            <p>필요한 자재를 요청해보세요</p>
        </div>
        
        <div class="content">
            {% if error %}
            <div class="alert alert-danger">
                ❌ {{ error }}
            </div>
            {% endif %}
            
            <form method="POST">
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
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="quantity">수량 <span class="required">*</span></label>
                        <input type="number" id="quantity" name="quantity" class="form-control" 
                               value="1" min="1" required>
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
</body>
</html>
'''

# 자재요청 목록 페이지 템플릿
REQUESTS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>📋 자재요청 목록 - HPNT Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
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
            border-radius: 25px; 
            overflow: hidden;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
        }
        .header { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; 
            padding: 30px; 
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 30px; }
        .controls { 
            display: flex; 
            gap: 15px; 
            margin-bottom: 30px; 
            flex-wrap: wrap;
        }
        .search-box, .filter-select { 
            padding: 12px 20px; 
            border: 2px solid #e0e0e0; 
            border-radius: 25px; 
            font-size: 16px;
            outline: none;
            transition: all 0.3s ease;
        }
        .search-box:focus, .filter-select:focus { 
            border-color: #4facfe; 
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }
        .btn { 
            padding: 12px 25px; 
            border: none; 
            border-radius: 25px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .request-grid { 
            display: grid; 
            gap: 20px; 
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        }
        .request-card { 
            background: white; 
            border-radius: 15px; 
            padding: 25px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
            border-left: 5px solid #4facfe;
        }
        .request-card:hover { transform: translateY(-5px); }
        .request-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 15px;
        }
        .request-title { font-size: 1.3em; font-weight: 600; color: #333; }
        .status-badge { 
            padding: 6px 12px; 
            border-radius: 15px; 
            font-size: 0.9em; 
            font-weight: 600;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-approved { background: #d1ecf1; color: #0c5460; }
        .status-ordered { background: #d4edda; color: #155724; }
        .status-received { background: #e2e3e5; color: #383d41; }
        .status-rejected { background: #f8d7da; color: #721c24; }
        .request-details { color: #666; line-height: 1.6; }
        .request-meta { 
            margin-top: 15px; 
            padding-top: 15px; 
            border-top: 1px solid #eee; 
            font-size: 0.9em; 
            color: #888;
        }
        .empty-state { 
            text-align: center; 
            padding: 60px 20px; 
            color: #666;
        }
        .empty-state h3 { font-size: 1.5em; margin-bottom: 10px; }
        @media (max-width: 768px) {
            .controls { flex-direction: column; }
            .search-box, .filter-select { width: 100%; }
            .request-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 자재요청 목록</h1>
            <p>등록된 모든 자재요청을 관리하세요</p>
        </div>
        
        <div class="content">
            <div class="controls">
                <a href="/" class="btn btn-primary">🏠 홈으로</a>
                <a href="/add" class="btn btn-success">➕ 새 요청</a>
                
                <form method="GET" style="display: flex; gap: 15px; flex: 1;">
                    <input type="text" name="search" class="search-box" 
                           placeholder="🔍 자재명, 사양, 사유로 검색..." 
                           value="{{ search_query }}">
                    
                    <select name="status" class="filter-select" onchange="this.form.submit()">
                        <option value="all" {% if status_filter == 'all' %}selected{% endif %}>전체 상태</option>
                        <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>대기중</option>
                        <option value="approved" {% if status_filter == 'approved' %}selected{% endif %}>승인됨</option>
                        <option value="ordered" {% if status_filter == 'ordered' %}selected{% endif %}>발주됨</option>
                        <option value="received" {% if status_filter == 'received' %}selected{% endif %}>입고됨</option>
                        <option value="rejected" {% if status_filter == 'rejected' %}selected{% endif %}>반려됨</option>
                    </select>
                    
                    <button type="submit" class="btn btn-primary">검색</button>
                </form>
            </div>
            
            {% if requests %}
            <div class="request-grid">
                {% for req in requests %}
                <div class="request-card">
                    <div class="request-header">
                        <div class="request-title">{{ req[2] }}</div>
                        <div class="status-badge status-{{ req[7] }}">
                            {% if req[7] == 'pending' %}대기중
                            {% elif req[7] == 'approved' %}승인됨
                            {% elif req[7] == 'ordered' %}발주됨
                            {% elif req[7] == 'received' %}입고됨
                            {% elif req[7] == 'rejected' %}반려됨
                            {% endif %}
                        </div>
                    </div>
                    
                    <div class="request-details">
                        <p><strong>📦 수량:</strong> {{ req[4] }}개</p>
                        {% if req[3] %}<p><strong>📋 사양:</strong> {{ req[3] }}</p>{% endif %}
                        {% if req[6] %}<p><strong>📝 사유:</strong> {{ req[6] }}</p>{% endif %}
                        {% if req[8] %}<p><strong>🏢 업체:</strong> {{ req[8] }}</p>{% endif %}
                        <p><strong>⚡ 긴급도:</strong> 
                            {% if req[5] == 'high' %}🔴 높음
                            {% elif req[5] == 'normal' %}🟡 보통
                            {% else %}🟢 낮음
                            {% endif %}
                        </p>
                    </div>
                    
                    <div class="request-meta">
                        <p>📅 등록일: {{ req[10] }}</p>
                        <a href="/request/{{ req[0] }}" class="btn btn-primary" style="margin-top: 10px; font-size: 14px;">상세보기</a>
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
</body>
</html>
'''

# 메인 페이지 HTML 템플릿
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>🚀 HPNT Manager V2.0</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HPNT Manager">
    <style>
        * { 
            box-sizing: border-box; 
            margin: 0; 
            padding: 0; 
            -webkit-tap-highlight-color: transparent;
        }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            overflow-x: hidden;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px; 
            box-shadow: 0 25px 50px rgba(0,0,0,0.15);
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; 
            padding: 40px 30px; 
            text-align: center; 
            position: relative;
        }
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
        }
        .header h1 { 
            font-size: 3em; 
            margin-bottom: 10px; 
            font-weight: 700;
            position: relative;
            z-index: 1;
        }
        .header p { 
            font-size: 1.3em; 
            opacity: 0.9; 
            position: relative;
            z-index: 1;
        }
        .version-badge {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
        }
        .content { 
            padding: 40px 30px; 
        }
        .btn { 
            display: inline-block;
            padding: 18px 35px; 
            margin: 12px; 
            border: none; 
            border-radius: 25px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            position: relative;
            overflow: hidden;
        }
        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        .btn:hover::before {
            left: 100%;
        }
        .btn-primary { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
        }
        .btn-success { 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; 
        }
        .btn-info { 
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            color: white; 
        }
        .btn:hover { 
            transform: translateY(-3px) scale(1.02); 
            box-shadow: 0 15px 35px rgba(0,0,0,0.2); 
        }
        .btn:active {
            transform: translateY(-1px) scale(0.98);
        }
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 25px; 
            margin: 40px 0; 
        }
        .stat-card { 
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white; 
            padding: 30px; 
            border-radius: 20px; 
            text-align: center;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            transform: rotate(45deg);
            transition: transform 0.5s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-card:hover::before {
            transform: rotate(45deg) translate(20px, 20px);
        }
        .stat-number { 
            font-size: 3em; 
            font-weight: 800; 
            margin-bottom: 15px;
            position: relative;
            z-index: 1;
        }
        .stat-label { 
            font-size: 1.2em; 
            opacity: 0.95;
            position: relative;
            z-index: 1;
        }
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-top: 40px;
        }
        .feature-card {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        .feature-card:hover {
            transform: translateY(-5px);
        }
        .feature-icon {
            font-size: 3em;
            margin-bottom: 20px;
        }
        .feature-title {
            font-size: 1.4em;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
        }
        .feature-desc {
            color: #666;
            line-height: 1.6;
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 2.2em; }
            .header p { font-size: 1.1em; }
            .content { padding: 25px 20px; }
            .btn { 
                padding: 15px 25px; 
                font-size: 14px; 
                margin: 8px 5px;
                display: block;
                text-align: center;
            }
            .stats {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }
            .stat-card { padding: 20px; }
            .stat-number { font-size: 2.2em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="version-badge">V2.0</div>
            <h1>🚀 HPNT Manager</h1>
            <p>💎 차세대 자재관리 시스템</p>
            <p style="font-size: 1em; margin-top: 10px;">
                🍎 {{ environment }} | 📊 {{ db_location }}
            </p>
        </div>
        
        <div class="content">
            <div style="text-align: center; margin-bottom: 40px;">
                <a href="/requests" class="btn btn-primary">📋 자재요청 목록</a>
                <a href="/add" class="btn btn-success">➕ 새 요청 등록</a>
                <a href="/stats" class="btn btn-info">📊 통계 보기</a>
                <button onclick="location.reload()" class="btn btn-primary">🔄 새로고침</button>
            </div>
            
            <div class="stats" id="stats">
                <!-- 통계는 JavaScript로 로드 -->
            </div>
            
            <div class="feature-grid">
                <div class="feature-card">
                    <div class="feature-icon">☁️</div>
                    <div class="feature-title">iCloud Drive 동기화</div>
                    <div class="feature-desc">
                        모든 Apple 기기에서 실시간 데이터 동기화
                    </div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📱</div>
                    <div class="feature-title">iPad 최적화</div>
                    <div class="feature-desc">
                        터치 인터페이스와 모바일 환경에 완벽 최적화
                    </div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <div class="feature-title">경량화 설계</div>
                    <div class="feature-desc">
                        핵심 기능만 선별한 빠르고 가벼운 시스템
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // PWA 등록
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(reg => console.log('SW registered'))
                .catch(err => console.log('SW registration failed'));
        }
        
        // 페이지 로드 시 통계 로드
        window.onload = function() {
            loadStats();
        };
        
        function loadStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.total || 0}</div>
                            <div class="stat-label">전체 요청</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.pending || 0}</div>
                            <div class="stat-label">대기중</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.approved || 0}</div>
                            <div class="stat-label">승인됨</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.ordered || 0}</div>
                            <div class="stat-label">발주됨</div>
                        </div>
                    `;
                })
                .catch(error => {
                    console.error('통계 로드 실패:', error);
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">-</div>
                            <div class="stat-label">데이터 로딩 중...</div>
                        </div>
                    `;
                });
        }
        
        // 터치 이벤트 최적화
        document.addEventListener('touchstart', function() {}, {passive: true});
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """메인 페이지"""
    env = detect_environment()
    
    # DB 위치 표시
    db_location = "로컬 DB (프로젝트/db)"
    
    return render_template_string(MAIN_TEMPLATE, 
                                environment=env.upper(), 
                                db_location=db_location)

@app.route('/api/stats')
def get_stats():
    """통계 API"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 전체 통계
        cursor.execute("SELECT COUNT(*) FROM material_requests")
        total = cursor.fetchone()[0]
        
        # 상태별 통계
        cursor.execute("SELECT status, COUNT(*) FROM material_requests GROUP BY status")
        status_counts = dict(cursor.fetchall())
        
        conn.close()
        
        return jsonify({
            'total': total,
            'pending': status_counts.get('pending', 0),
            'approved': status_counts.get('approved', 0),
            'ordered': status_counts.get('ordered', 0),
            'received': status_counts.get('received', 0),
            'rejected': status_counts.get('rejected', 0)
        })
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/requests')
def requests_page():
    """자재요청 목록 페이지"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 상태 필터링
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        
        # 기본 쿼리
        query = "SELECT * FROM material_requests WHERE 1=1"
        params = []
        
        # 상태 필터 적용
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        
        # 검색 필터 적용
        if search_query:
            query += " AND (item_name LIKE ? OR specifications LIKE ? OR reason LIKE ?)"
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        requests = cursor.fetchall()
        conn.close()
        
        return render_template_string(REQUESTS_TEMPLATE, 
                                    requests=requests,
                                    status_filter=status_filter,
                                    search_query=search_query)
    except Exception as e:
        logger.error(f"자재요청 목록 조회 실패: {e}")
        return f"<h1>❌ 오류</h1><p>목록을 불러올 수 없습니다: {e}</p><a href='/'>← 홈으로</a>"

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    """새 요청 등록 페이지"""
    if request.method == 'POST':
        try:
            # 폼 데이터 받기
            item_name = request.form.get('item_name', '').strip()
            specifications = request.form.get('specifications', '').strip()
            quantity = int(request.form.get('quantity', 1))
            urgency = request.form.get('urgency', 'normal')
            reason = request.form.get('reason', '').strip()
            vendor = request.form.get('vendor', '').strip()
            
            # 필수 필드 검증
            if not item_name:
                return render_template_string(ADD_TEMPLATE, 
                                            error="자재명은 필수 입력 항목입니다.")
            
            if quantity <= 0:
                return render_template_string(ADD_TEMPLATE, 
                                            error="수량은 1 이상이어야 합니다.")
            
            # 데이터베이스에 저장
            db_path = get_material_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO material_requests 
                (requester, item_name, specifications, quantity, urgency, reason, vendor, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', ('HPNT_USER', item_name, specifications, quantity, urgency, reason, vendor))
            
            conn.commit()
            conn.close()
            
            logger.info(f"새 자재요청 등록: {item_name} x {quantity}")
            return redirect('/requests')
            
        except ValueError:
            return render_template_string(ADD_TEMPLATE, 
                                        error="수량은 숫자로 입력해주세요.")
        except Exception as e:
            logger.error(f"자재요청 등록 실패: {e}")
            return render_template_string(ADD_TEMPLATE, 
                                        error=f"등록 중 오류가 발생했습니다: {e}")
    
    # GET 요청일 때 빈 폼 표시
    return render_template_string(ADD_TEMPLATE)

@app.route('/request/<int:request_id>')
def request_detail(request_id):
    """자재요청 상세 페이지"""
    try:
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM material_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req:
            conn.close()
            return f"<h1>❌ 오류</h1><p>요청을 찾을 수 없습니다.</p><a href='/requests'>← 목록으로</a>"
        
        conn.close()
        return render_template_string(DETAIL_TEMPLATE, request=req)
        
    except Exception as e:
        logger.error(f"자재요청 상세 조회 실패: {e}")
        return f"<h1>❌ 오류</h1><p>상세 정보를 불러올 수 없습니다: {e}</p><a href='/requests'>← 목록으로</a>"

@app.route('/request/<int:request_id>/status', methods=['POST'])
def update_request_status(request_id):
    """자재요청 상태 변경"""
    try:
        new_status = request.form.get('status')
        valid_statuses = ['pending', 'approved', 'ordered', 'received', 'rejected']
        
        if new_status not in valid_statuses:
            return jsonify({'error': '유효하지 않은 상태입니다.'}), 400
        
        db_path = get_material_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE material_requests SET status = ? WHERE id = ?", 
            (new_status, request_id)
        )
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': '요청을 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"자재요청 {request_id} 상태 변경: {new_status}")
        return redirect(f'/request/{request_id}')
        
    except Exception as e:
        logger.error(f"상태 변경 실패: {e}")
        return jsonify({'error': f'상태 변경 중 오류가 발생했습니다: {e}'}), 500

@app.route('/stats')
def stats_page():
    """통계 페이지"""
    # 간단한 통계 페이지 (추후 구현)
    return "<h1>📊 통계</h1><p>곧 구현될 예정입니다!</p><a href='/'>← 홈으로</a>"



# PWA 서비스 워커
@app.route('/sw.js')
def service_worker():
    """PWA 서비스 워커"""
    sw_content = '''
const CACHE_NAME = 'hpnt-manager-v2-cache';
const urlsToCache = [
    '/',
    '/requests',
    '/add',
    '/stats'
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {
                if (response) {
                    return response;
                }
                return fetch(event.request);
            })
    );
});
'''
    return sw_content, 200, {'Content-Type': 'application/javascript'}

if __name__ == '__main__':
    print("🚀 HPNT Manager V2.0 시작...")
    print("=" * 50)
    
    # 환경 정보 출력
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
