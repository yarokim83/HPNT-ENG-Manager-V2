"""
PostgreSQL 데이터베이스 연결 및 관리 모듈
Railway PostgreSQL 서비스와 연동
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

def get_postgres_connection():
    """PostgreSQL 연결 생성"""
    try:
        # Railway PostgreSQL 환경 변수 (자동 생성됨)
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Railway에서 제공하는 DATABASE_URL 사용
            conn = psycopg2.connect(database_url)
        else:
            # 로컬 개발 환경용 (필요시)
            conn = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'hpnt_manager'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', 'password'),
                port=os.environ.get('DB_PORT', '5432')
            )
        
        return conn
    except Exception as e:
        logger.error(f"PostgreSQL 연결 실패: {e}")
        return None

def init_postgres_database():
    """PostgreSQL 테이블 초기화"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # material_requests 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS material_requests (
                id SERIAL PRIMARY KEY,
                item_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                specifications TEXT,
                reason TEXT,
                urgency VARCHAR(20) DEFAULT 'normal',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vendor VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                images VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 인덱스 생성 (성능 최적화)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_material_requests_status ON material_requests(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_material_requests_date ON material_requests(request_date)')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("PostgreSQL 데이터베이스 초기화 완료")
        return True
        
    except Exception as e:
        logger.error(f"PostgreSQL 초기화 실패: {e}")
        return False

def insert_sample_data():
    """샘플 데이터 삽입"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 기존 데이터 확인
        cursor.execute('SELECT COUNT(*) FROM material_requests')
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.info("기존 데이터가 있어 샘플 데이터 삽입을 건너뜁니다.")
            cursor.close()
            conn.close()
            return True
        
        # 샘플 데이터 삽입
        sample_data = [
            ('볼트 M8x20', 50, 'SUS304 스테인리스 스틸', '장비 고정용', 'normal', 'pending'),
            ('너트 M8', 50, 'SUS304 스테인리스 스틸', '볼트와 세트', 'normal', 'pending'),
            ('와셔 M8', 100, '평와셔, 아연도금', '볼트 조임용', 'low', 'pending'),
            ('케이블 타이', 200, '200mm, 검정색', '케이블 정리용', 'normal', 'pending'),
            ('전선 2.5sq', 100, 'KIV 전선, 빨간색', '전원 배선용', 'high', 'pending')
        ]
        
        for item in sample_data:
            cursor.execute('''
                INSERT INTO material_requests 
                (item_name, quantity, specifications, reason, urgency, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', item)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"샘플 데이터 {len(sample_data)}개 삽입 완료")
        return True
        
    except Exception as e:
        logger.error(f"샘플 데이터 삽입 실패: {e}")
        return False

def get_all_material_requests():
    """모든 자재요청 조회"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT id, item_name, quantity, specifications, reason, urgency, 
                   request_date, vendor, status, images, created_at
            FROM material_requests 
            ORDER BY id DESC
        ''')
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # RealDictCursor 결과를 튜플 리스트로 변환 (기존 코드 호환성)
        formatted_results = []
        for row in results:
            formatted_results.append((
                row['id'], row['item_name'], row['quantity'], 
                row['specifications'], row['reason'], row['urgency'],
                row['request_date'], row['vendor'], row['status'], 
                row['images'], row['created_at']
            ))
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"자재요청 조회 실패: {e}")
        return []

def add_material_request(item_name, quantity, specifications, reason, urgency, images=None):
    """새 자재요청 추가"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO material_requests 
            (item_name, quantity, specifications, reason, urgency, images)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (item_name, quantity, specifications, reason, urgency, images))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"자재요청 추가: {item_name}")
        return True
        
    except Exception as e:
        logger.error(f"자재요청 추가 실패: {e}")
        return False

def update_material_request_status(request_id, status, vendor=None):
    """자재요청 상태 업데이트"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        if vendor:
            cursor.execute('''
                UPDATE material_requests 
                SET status = %s, vendor = %s 
                WHERE id = %s
            ''', (status, vendor, request_id))
        else:
            cursor.execute('''
                UPDATE material_requests 
                SET status = %s 
                WHERE id = %s
            ''', (status, request_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"자재요청 상태 업데이트: ID {request_id} -> {status}")
        return True
        
    except Exception as e:
        logger.error(f"상태 업데이트 실패: {e}")
        return False

def delete_material_request(request_id):
    """자재요청 삭제"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute('DELETE FROM material_requests WHERE id = %s', (request_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"자재요청 삭제: ID {request_id}")
        return True
        
    except Exception as e:
        logger.error(f"자재요청 삭제 실패: {e}")
        return False

def update_material_info(request_id, item_name, quantity, specifications, reason):
    """자재 정보 업데이트"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE material_requests 
            SET item_name = %s, quantity = %s, specifications = %s, reason = %s
            WHERE id = %s
        ''', (item_name, quantity, specifications, reason, request_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"자재 정보 업데이트: ID {request_id}")
        return True
        
    except Exception as e:
        logger.error(f"자재 정보 업데이트 실패: {e}")
        return False

def update_material_image(request_id, image_filename):
    """자재 이미지 업데이트"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE material_requests 
            SET images = %s 
            WHERE id = %s
        ''', (image_filename, request_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"자재 이미지 업데이트: ID {request_id} -> {image_filename}")
        return True
        
    except Exception as e:
        logger.error(f"이미지 업데이트 실패: {e}")
        return False

def get_status_counts():
    """상태별 카운트 조회"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM material_requests 
            GROUP BY status
        ''')
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        status_counts = {}
        for status, count in results:
            status_counts[status] = count
        
        return status_counts
        
    except Exception as e:
        logger.error(f"상태별 카운트 조회 실패: {e}")
        return {}

def backup_to_json():
    """데이터베이스를 JSON으로 백업"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM material_requests ORDER BY id')
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # datetime 객체를 문자열로 변환
        backup_data = []
        for row in results:
            row_dict = dict(row)
            for key, value in row_dict.items():
                if isinstance(value, datetime):
                    row_dict[key] = value.isoformat()
            backup_data.append(row_dict)
        
        return json.dumps(backup_data, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"JSON 백업 실패: {e}")
        return None

def reindex_postgres_ids():
    """PostgreSQL에서 ID 재정렬 (#1부터 순차적으로)"""
    try:
        conn = get_postgres_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 모든 데이터를 created_at 순서로 조회
        cursor.execute('''
            SELECT id, item_name, quantity, specifications, reason, urgency, 
                   request_date, vendor, status, images, created_at
            FROM material_requests 
            ORDER BY created_at ASC, id ASC
        ''')
        
        all_data = cursor.fetchall()
        
        if not all_data:
            cursor.close()
            conn.close()
            return True
        
        # 기존 테이블 백업 후 재생성
        cursor.execute('DROP TABLE IF EXISTS material_requests_backup')
        cursor.execute('''
            CREATE TABLE material_requests_backup AS 
            SELECT * FROM material_requests
        ''')
        
        # 기존 테이블 삭제 후 재생성
        cursor.execute('DROP TABLE material_requests')
        cursor.execute('''
            CREATE TABLE material_requests (
                id SERIAL PRIMARY KEY,
                item_name VARCHAR(200) NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                specifications TEXT,
                reason TEXT,
                urgency VARCHAR(20) DEFAULT 'normal',
                request_date DATE DEFAULT CURRENT_DATE,
                vendor VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                images VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 데이터를 순서대로 다시 삽입 (ID는 자동으로 1부터 할당됨)
        for i, row in enumerate(all_data, 1):
            cursor.execute('''
                INSERT INTO material_requests 
                (item_name, quantity, specifications, reason, urgency, 
                 request_date, vendor, status, images, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row[1], row[2], row[3], row[4], row[5],  # item_name, quantity, specifications, reason, urgency
                row[6], row[7], row[8], row[9], row[10]  # request_date, vendor, status, images, created_at
            ))
        
        # 백업 테이블 삭제
        cursor.execute('DROP TABLE material_requests_backup')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"PostgreSQL ID 재정렬 완료: {len(all_data)}개 항목")
        return True
        
    except Exception as e:
        logger.error(f"PostgreSQL ID 재정렬 실패: {e}")
        return False
