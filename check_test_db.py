#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPNT_ENG_Manager V2.0 - 테스트 데이터베이스 확인 스크립트
"""

import os
import sqlite3
import sys
from datetime import datetime

def get_db_path():
    """DB 경로 결정"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'db', 'material_rq.db')
    return db_path

def check_database():
    """데이터베이스 내용 확인"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일이 존재하지 않습니다: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("📊 HPNT ENG Manager V2.0 - 테스트 데이터베이스 확인")
        print("=" * 80)
        print(f"📁 DB 파일: {db_path}")
        print(f"📅 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(material_requests)")
        columns = cursor.fetchall()
        print("📋 테이블 구조:")
        print("-" * 60)
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        print()
        
        # 전체 데이터 개수
        cursor.execute("SELECT COUNT(*) FROM material_requests")
        total_count = cursor.fetchone()[0]
        print(f"📊 총 레코드 수: {total_count}개")
        print()
        
        # 상태별 통계
        cursor.execute("SELECT status, COUNT(*) FROM material_requests GROUP BY status ORDER BY COUNT(*) DESC")
        status_stats = cursor.fetchall()
        print("📈 상태별 통계:")
        print("-" * 30)
        for status, count in status_stats:
            print(f"  {status}: {count}개")
        print()
        
        # 긴급도별 통계
        cursor.execute("SELECT urgency, COUNT(*) FROM material_requests GROUP BY urgency ORDER BY COUNT(*) DESC")
        urgency_stats = cursor.fetchall()
        print("🚨 긴급도별 통계:")
        print("-" * 30)
        for urgency, count in urgency_stats:
            print(f"  {urgency}: {count}개")
        print()
        
        # 최근 데이터 5개
        cursor.execute("""
            SELECT id, item_name, quantity, urgency, status, request_date 
            FROM material_requests 
            ORDER BY id DESC 
            LIMIT 5
        """)
        recent_data = cursor.fetchall()
        print("🆕 최근 데이터 5개:")
        print("-" * 80)
        print(f"{'ID':<3} {'자재명':<20} {'수량':<5} {'긴급도':<8} {'상태':<12} {'요청일':<12}")
        print("-" * 80)
        for row in recent_data:
            id, item_name, quantity, urgency, status, request_date = row
            print(f"{id:<3} {item_name:<20} {quantity:<5} {urgency:<8} {status:<12} {request_date:<12}")
        print()
        
        # 테스트 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM material_requests WHERE item_name LIKE '%테스트%'")
        test_count = cursor.fetchone()[0]
        print(f"🧪 테스트 데이터: {test_count}개")
        
        cursor.execute("SELECT COUNT(*) FROM material_requests WHERE item_name NOT LIKE '%테스트%'")
        real_count = cursor.fetchone()[0]
        print(f"📦 실제 자재 데이터: {real_count}개")
        print()
        
        conn.close()
        
        print("=" * 80)
        print("✅ 데이터베이스 확인 완료!")
        print("🌐 서버 실행: python app_new.py")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 확인 실패: {e}")
        return False

if __name__ == '__main__':
    check_database() 