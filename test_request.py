#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
자재요청 등록 테스트 스크립트
"""

import requests
import json

def test_add_request():
    """테스트 자재요청 등록"""
    url = "http://127.0.0.1:5001/add"
    
    # 테스트 데이터
    test_data = {
        'item_name': '안전헬멧',
        'specifications': 'KS규격 화이트 헬멧, 충격흡수 패드 포함',
        'quantity': '10',
        'urgency': 'high',
        'reason': '현장 안전장비 부족으로 인한 긴급 보충 필요',
        'vendor': '안전용품코리아'
    }
    
    try:
        print("🔄 자재요청 등록 테스트 시작...")
        print(f"📤 요청 데이터: {test_data}")
        
        # POST 요청 전송
        response = requests.post(url, data=test_data)
        
        print(f"📊 응답 상태: {response.status_code}")
        print(f"📍 리다이렉트 URL: {response.url}")
        
        if response.status_code == 200:
            print("✅ 자재요청 등록 성공!")
            return True
        else:
            print(f"❌ 등록 실패: {response.status_code}")
            print(f"응답 내용: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

def test_add_multiple_requests():
    """여러 테스트 자재요청 등록"""
    test_requests = [
        {
            'item_name': '안전헬멧',
            'specifications': 'KS규격 화이트 헬멧, 충격흡수 패드 포함',
            'quantity': '10',
            'urgency': 'high',
            'reason': '현장 안전장비 부족으로 인한 긴급 보충 필요',
            'vendor': '안전용품코리아'
        },
        {
            'item_name': '와이어로프',
            'specifications': '6x19 구조, 직경 12mm, 길이 100m',
            'quantity': '2',
            'urgency': 'normal',
            'reason': '크레인 주 와이어 정기 교체',
            'vendor': '대한와이어'
        },
        {
            'item_name': '볼트 세트',
            'specifications': 'M16x50, SUS304 재질, 너트 포함',
            'quantity': '50',
            'urgency': 'low',
            'reason': '정기 점검 시 교체용 예비 부품',
            'vendor': ''
        }
    ]
    
    success_count = 0
    for i, data in enumerate(test_requests, 1):
        print(f"\n🔄 테스트 요청 {i}/{len(test_requests)} 등록 중...")
        if test_single_request(data):
            success_count += 1
    
    print(f"\n📊 등록 결과: {success_count}/{len(test_requests)} 성공")
    return success_count == len(test_requests)

def test_single_request(data):
    """단일 자재요청 등록 테스트"""
    url = "http://127.0.0.1:5001/add"
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"✅ '{data['item_name']}' 등록 성공")
            return True
        else:
            print(f"❌ '{data['item_name']}' 등록 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ '{data['item_name']}' 등록 오류: {e}")
        return False

if __name__ == "__main__":
    print("🚀 HPNT Manager V2.0 자재요청 등록 테스트")
    print("=" * 50)
    
    # 여러 테스트 요청 등록
    test_add_multiple_requests()
    
    print("\n🔍 등록된 요청 확인을 위해 브라우저에서 http://127.0.0.1:5001/requests 를 확인하세요!")
