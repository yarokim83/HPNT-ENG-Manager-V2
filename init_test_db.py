#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPNT_ENG_Manager V2.0 - 테스트 데이터베이스 초기화 스크립트
"""

import os
import sqlite3
import sys
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_test_db_path():
    """테스트용 DB 경로 결정"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_folder = os.path.join(current_dir, 'db')
    
    if not os.path.exists(db_folder):
        os.makedirs(db_folder, exist_ok=True)
        logger.info(f"테스트 DB 폴더 생성: {db_folder}")
    
    db_path = os.path.join(db_folder, 'material_rq.db')
    logger.info(f"테스트 DB 경로: {db_path}")
    return db_path

def init_test_database():
    """테스트용 자재관리 데이터베이스 초기화"""
    db_path = get_test_db_path()
    
    try:
        # 기존 DB 파일이 있으면 삭제
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"기존 DB 파일 삭제: {db_path}")
        
        # 데이터베이스 디렉토리 생성
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"📁 DB 디렉토리 생성: {db_dir}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 자재요청 테이블 생성 (최신 스키마)
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
        
        # 테스트용 샘플 데이터 삽입
        logger.info("📝 테스트용 샘플 데이터 삽입 시작")
        
        test_data = [
            # 기본 테스트 데이터
            ('🔧 테스트 자재 1', 5, '테스트용 스펙', '테스트 목적', 'high', '2025-01-15', '테스트 벤더', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('📦 테스트 자재 2', 10, '테스트용 스펙 2', '테스트 목적 2', 'normal', '2025-01-15', '테스트 벤더 2', 'approved', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('⚡ 테스트 자재 3', 3, '긴급 테스트용', '긴급 테스트', 'high', '2025-01-15', '긴급 벤더', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            
            # 실제 자재와 유사한 테스트 데이터
            ('안전모', 15, '흰색, CE 인증, 대형', '현장 안전 강화', 'high', '2025-01-14', '안전용품공급', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('작업장갑', 25, '면장갑, L사이즈, 내구성 강화', '작업자 보호용', 'normal', '2025-01-14', '보호용품공급', 'approved', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('전선', 5, '2.5sq, 100m, 빨간색', '전기 배선 작업용', 'normal', '2025-01-13', '전기재료공급', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('볼트 M8x20', 100, 'SUS304 스테인리스 스틸', '장비 고정용', 'low', '2025-01-13', '금속재료공급', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('너트 M8', 100, 'SUS304 스테인리스 스틸', '볼트와 세트', 'low', '2025-01-12', '금속재료공급', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('케이블 타이', 500, '200mm, 검정색, 내열성', '케이블 정리용', 'normal', '2025-01-12', '전기재료공급', 'approved', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('와셔 M8', 200, '평와셔, 아연도금, 표준품', '볼트 조임용', 'low', '2025-01-11', '금속재료공급', 'pending', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            
            # 다양한 상태의 테스트 데이터
            ('완료된 자재', 1, '테스트 완료용', '테스트 완료', 'normal', '2025-01-10', '완료벤더', 'completed', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('거부된 자재', 1, '테스트 거부용', '테스트 거부', 'normal', '2025-01-09', '거부벤더', 'rejected', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ('진행중인 자재', 1, '테스트 진행용', '테스트 진행', 'normal', '2025-01-08', '진행벤더', 'in_progress', '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ]
        
        cursor.executemany('''
            INSERT INTO material_requests 
            (item_name, quantity, specifications, reason, urgency, request_date, vendor, status, images, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_data)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ 테스트용 자재관리 DB 초기화 완료: {db_path}")
        logger.info(f"✅ 테스트 데이터 {len(test_data)}개 삽입 완료")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트용 자재관리 DB 초기화 실패: {e}")
        return False

def verify_test_database():
    """테스트 데이터베이스 검증"""
    db_path = get_test_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(material_requests)")
        columns = cursor.fetchall()
        logger.info(f"📋 테이블 컬럼 수: {len(columns)}개")
        
        # 데이터 개수 확인
        cursor.execute("SELECT COUNT(*) FROM material_requests")
        count = cursor.fetchone()[0]
        logger.info(f"📊 총 레코드 수: {count}개")
        
        # 상태별 데이터 확인
        cursor.execute("SELECT status, COUNT(*) FROM material_requests GROUP BY status")
        status_counts = cursor.fetchall()
        logger.info("📈 상태별 데이터 분포:")
        for status, count in status_counts:
            logger.info(f"  - {status}: {count}개")
        
        # 긴급도별 데이터 확인
        cursor.execute("SELECT urgency, COUNT(*) FROM material_requests GROUP BY urgency")
        urgency_counts = cursor.fetchall()
        logger.info("🚨 긴급도별 데이터 분포:")
        for urgency, count in urgency_counts:
            logger.info(f"  - {urgency}: {count}개")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 검증 실패: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 HPNT ENG Manager V2.0 - 테스트 데이터베이스 초기화")
    print("=" * 60)
    
    # 테스트 DB 초기화
    if init_test_database():
        print("✅ 테스트 데이터베이스 초기화 성공!")
        
        # 데이터베이스 검증
        if verify_test_database():
            print("✅ 데이터베이스 검증 완료!")
        else:
            print("❌ 데이터베이스 검증 실패!")
    else:
        print("❌ 테스트 데이터베이스 초기화 실패!")
    
    print("=" * 60)
    print("🎯 테스트 데이터베이스 준비 완료!")
    print("📁 DB 파일 위치: db/material_rq.db")
    print("🌐 서버 실행: python app_new.py")
    print("=" * 60) 