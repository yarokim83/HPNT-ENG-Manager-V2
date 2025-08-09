#!/usr/bin/env python3
"""Git 업데이트 스크립트"""

import subprocess
import sys
import os

def run_git_command(cmd):
    """Git 명령 실행"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Exception running {cmd}: {e}")
        return False

def main():
    """메인 함수"""
    print("🚀 Git 업데이트 시작...")
    print("=" * 50)
    
    # 1. Git status 확인
    print("\n1️⃣ Git 상태 확인...")
    run_git_command(['git', 'status', '--porcelain'])
    
    # 2. Git add
    print("\n2️⃣ Git add...")
    if run_git_command(['git', 'add', '.']):
        print("✅ Git add 성공")
    else:
        print("❌ Git add 실패")
        return
    
    # 3. Git commit
    print("\n3️⃣ Git commit...")
    commit_msg = """feat: 자재요청 관리 시스템 기능 복원 및 iOS 26 디자인 적용

- 홈페이지에 통계 카드, 버튼, 다이나믹 아일랜드 복원
- 자재요청 목록에 인라인 발주업체/상태 편집 기능 추가  
- 이미지 업로드/삭제 기능 복원
- 상세보기 버튼 제거
- iOS 26 디자인 시스템 적용 (Glassmorphism, 애니메이션, 햅틱)
- 통계 API에 in_progress, environment, database 필드 추가
- 서비스워커 캐시 무효화 강화"""
    
    if run_git_command(['git', 'commit', '-m', commit_msg]):
        print("✅ Git commit 성공")
    else:
        print("❌ Git commit 실패 (변경사항이 없거나 오류)")
    
    # 4. Git push
    print("\n4️⃣ Git push...")
    if run_git_command(['git', 'push', 'origin', 'main']):
        print("✅ Git push 성공")
    else:
        print("❌ Git push 실패")
    
    print("\n🎉 Git 업데이트 완료!")

if __name__ == "__main__":
    main()
