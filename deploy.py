#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPNT ENG Manager V2.0 - GitHub 업로드 및 Render 자동 배포 스크립트
"""

import os
import subprocess
import sys
from datetime import datetime

def run_command(command, cwd=None):
    """명령어 실행"""
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, 
                              capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print(f"✅ {command}")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {command}")
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 명령어 실행 오류: {e}")
        return False

def main():
    """메인 배포 함수"""
    print("🚀 HPNT ENG Manager V2.0 - GitHub 업로드 및 Render 배포")
    print("=" * 60)
    
    # 현재 디렉토리 확인
    current_dir = os.getcwd()
    print(f"📁 현재 디렉토리: {current_dir}")
    
    # Git 설정 확인
    print("\n1️⃣ Git 설정 확인...")
    run_command("git config --global user.name || git config --global user.name 'HPNT ENG'")
    run_command("git config --global user.email || git config --global user.email 'hpnt@example.com'")
    
    # 파일 추가
    print("\n2️⃣ 파일 스테이징...")
    if not run_command("git add ."):
        print("❌ 파일 추가 실패")
        return False
    
    # 커밋
    print("\n3️⃣ 커밋 생성...")
    commit_message = f"HPNT ENG Manager V2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if not run_command(f'git commit -m "{commit_message}"'):
        print("❌ 커밋 실패 (변경사항이 없을 수 있습니다)")
    
    # 브랜치 확인/변경
    print("\n4️⃣ 브랜치 설정...")
    run_command("git branch -M main")
    
    # GitHub 저장소 정보 입력
    print("\n5️⃣ GitHub 저장소 설정...")
    repo_url = input("GitHub 저장소 URL을 입력하세요 (예: https://github.com/username/repo.git): ").strip()
    
    if not repo_url:
        print("❌ 저장소 URL이 필요합니다.")
        return False
    
    # 원격 저장소 추가
    run_command("git remote remove origin")  # 기존 origin 제거 (있다면)
    if not run_command(f"git remote add origin {repo_url}"):
        print("❌ 원격 저장소 추가 실패")
        return False
    
    # GitHub에 푸시
    print("\n6️⃣ GitHub에 업로드...")
    if not run_command("git push -u origin main"):
        print("❌ GitHub 업로드 실패")
        print("💡 GitHub 인증이 필요할 수 있습니다.")
        print("💡 Personal Access Token을 사용하거나 GitHub CLI를 설정해주세요.")
        return False
    
    print("\n🎉 GitHub 업로드 완료!")
    print("\n📋 Render 자동 배포 설정 방법:")
    print("1. https://render.com 에 로그인")
    print("2. 'New' → 'Web Service' 선택")
    print(f"3. GitHub 저장소 연결: {repo_url}")
    print("4. 설정:")
    print("   - Name: hpnt-eng-manager")
    print("   - Environment: Python 3")
    print("   - Build Command: pip install -r requirements.txt")
    print("   - Start Command: chmod +x start.sh && ./start.sh")
    print("   - Plan: Free")
    print("5. 'Create Web Service' 클릭")
    print("\n✅ 배포가 완료되면 Render에서 제공하는 URL로 접속 가능합니다!")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
    
    input("\n엔터를 눌러 종료...")
