# 🚀 HPNT Manager V2.0

## 📋 개요
**HPNT Manager V2.0**은 경량화된 차세대 자재관리 시스템입니다.
iPad 및 크로스 플랫폼 환경에서 최적화된 성능을 제공합니다.

## ✨ 주요 특징

### 🎯 V2.0 핵심 개선사항
- **경량화 설계**: 핵심 기능만 선별한 빠른 성능
- **iPad 최적화**: 터치 인터페이스 완벽 지원
- **iCloud Drive 연동**: 모든 Apple 기기 간 실시간 동기화
- **PWA 지원**: 네이티브 앱과 같은 사용자 경험
- **크로스 플랫폼**: Windows, macOS, iPad, iPhone 모두 지원

### 🛠️ 기술 스택
- **Backend**: Flask (Python)
- **Database**: SQLite + iCloud Drive 동기화
- **Frontend**: HTML5 + CSS3 + JavaScript
- **PWA**: Service Worker + Web App Manifest
- **Deployment**: Render Cloud Platform

## 🚀 빠른 시작

### 로컬 실행
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 앱 실행
python app.py

# 3. 브라우저에서 접속
# http://127.0.0.1:5000
```

### iPad에서 실행
```bash
# a-Shell 또는 Pythonista 3에서
python3 app.py
```

## 📱 iPad 설치 가이드

### 방법 1: a-Shell (무료)
1. App Store에서 "a-Shell" 설치
2. 터미널에서 `pip install flask` 실행
3. 프로젝트 파일을 iCloud Drive로 복사
4. `python3 app.py` 실행

### 방법 2: Pythonista 3 ($9.99)
1. App Store에서 "Pythonista 3" 구매
2. 앱 내에서 Flask 설치
3. 프로젝트 파일 임포트
4. 실행

## 🗄️ 데이터베이스 설정

### iCloud Drive 자동 동기화
```bash
# 환경변수 설정 (기본값: true)
export USE_ICLOUD_DB=true
```

### 지원 경로
- **Windows**: `~/iCloudDrive/HPNT_Manager/`
- **macOS**: `~/Library/Mobile Documents/com~apple~CloudDocs/HPNT_Manager/`
- **iPad**: `~/Documents/iCloud Drive/HPNT_Manager/`

## 🌐 배포

### Render 클라우드 배포
1. GitHub 저장소 생성
2. Render에서 웹 서비스 생성
3. 자동 배포 설정

### 환경변수
```
USE_ICLOUD_DB=false  # 클라우드 환경에서는 false
PORT=5000           # Render에서 자동 설정
```

## 📊 API 엔드포인트

### 통계 API
```
GET /api/stats
```

### 자재요청 관리 (추후 구현)
```
GET /api/requests      # 목록 조회
POST /api/requests     # 새 요청 생성
PUT /api/requests/:id  # 요청 수정
DELETE /api/requests/:id # 요청 삭제
```

## 🔧 개발 환경

### 필수 요구사항
- Python 3.8+
- Flask 2.3+
- SQLite3

### 개발 도구
- **IDE**: Windsurf, VS Code, Pythonista 3
- **버전 관리**: Git
- **배포**: Render, Railway

## 📂 프로젝트 구조
```
HPNT_ENG_ManagerV2.0/
├── app.py              # 메인 애플리케이션
├── requirements.txt    # Python 의존성
├── README.md          # 프로젝트 문서
└── material_rq.db     # SQLite 데이터베이스 (자동 생성)
```

## 🎨 UI/UX 특징

### 모던 디자인
- **그라디언트 배경**: 시각적 깊이감
- **글래스모피즘**: 반투명 효과
- **마이크로 인터랙션**: 부드러운 애니메이션
- **반응형 디자인**: 모든 화면 크기 지원

### 터치 최적화
- **큰 터치 영역**: 손가락 터치에 최적화
- **스와이프 제스처**: 직관적인 네비게이션
- **햅틱 피드백**: 터치 반응 향상

## 🔒 보안

### 데이터 보호
- **로컬 저장**: 민감한 데이터는 기기에만 저장
- **iCloud 암호화**: Apple의 엔드투엔드 암호화
- **HTTPS**: 모든 통신 암호화

## 🚀 로드맵

### Phase 1: 핵심 기능 (현재)
- [x] 기본 Flask 앱 구조
- [x] iCloud Drive 연동
- [x] PWA 기본 기능
- [ ] 자재요청 CRUD

### Phase 2: 고급 기능
- [ ] 이미지 업로드/관리
- [ ] 실시간 알림
- [ ] 오프라인 지원
- [ ] 데이터 내보내기

### Phase 3: 확장 기능
- [ ] 다중 사용자 지원
- [ ] 권한 관리
- [ ] 대시보드 고도화
- [ ] ERP 연동

## 🤝 기여

이 프로젝트는 HPNT 엔지니어링 팀의 내부 도구입니다.
개선 사항이나 버그 리포트는 팀 내에서 공유해 주세요.

## 📄 라이선스

Copyright © 2025 HPNT Engineering Team
All rights reserved.

---

**🍎 Made with ❤️ for iPad**
