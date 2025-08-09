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
- **iOS 26 디자인**: 최신 iOS 26 디자인 언어 적용

### 🛠️ 기술 스택
- **Backend**: Flask (Python)
- **Database**: SQLite + iCloud Drive 동기화
- **Frontend**: HTML5 + CSS3 + JavaScript
- **PWA**: Service Worker + Web App Manifest
- **Deployment**: Render Cloud Platform

## 🎨 iOS 26 UI/UX 디자인

### 🍎 iOS 26 디자인 시스템
- **글래스모피즘**: 반투명 효과와 블러 처리
- **다이나믹 아일랜드**: iOS 16+ 스타일의 상태 표시
- **햅틱 피드백**: 터치 반응 시뮬레이션
- **다크모드**: 자동 다크모드 지원
- **접근성**: 웹 접근성 가이드라인 준수

### 🎯 디자인 특징
- **iOS 26 색상 팔레트**: Apple의 공식 색상 사용
- **SF Pro 폰트**: Apple의 시스템 폰트 적용
- **부드러운 애니메이션**: iOS 스타일의 자연스러운 전환
- **반응형 디자인**: 모든 화면 크기 최적화
- **터치 최적화**: 44px 최소 터치 영역

### 📱 모바일 최적화
- **PWA 지원**: 홈 화면에 앱으로 설치 가능
- **오프라인 지원**: 서비스 워커를 통한 캐싱
- **스와이프 제스처**: 직관적인 네비게이션
- **키보드 최적화**: 모바일 키보드 대응

## 🚀 빠른 시작

### 로컬 실행
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 앱 실행
python app_new.py

# 3. 브라우저에서 접속
# http://127.0.0.1:5001
```

### iPad에서 실행
```bash
# a-Shell 또는 Pythonista 3에서
python3 app_new.py
```

## 🧪 테스트 데이터베이스

### 전체 DB 초기화 (권장)
```bash
# Python 스크립트로 전체 초기화 (로컬 + OneDrive)
python init_all_test_db.py

# 또는 배치 파일 사용 (Windows)
init_all_test_db.bat
```

### 개별 DB 초기화
```bash
# 로컬 DB만 초기화
python init_test_db.py

# OneDrive DB만 초기화
python init_onedrive_test_db.py

# 또는 개별 배치 파일 사용 (Windows)
init_test_db.bat
```

### 테스트 DB 확인
```bash
# 데이터베이스 내용 확인
python check_test_db.py
```

### 테스트 데이터 구성
- **총 13개의 샘플 데이터**
- **다양한 상태**: pending(7), approved(3), rejected(1), in_progress(1), completed(1)
- **다양한 긴급도**: normal(7), low(3), high(3)
- **테스트용 데이터**: 3개
- **실제 자재 데이터**: 10개 (안전모, 작업장갑, 전선, 볼트, 너트 등)

## 📁 프로젝트 구조

```
HPNT_ENG_ManagerV2.0/
├── app_new.py           # 메인 애플리케이션 (V2.0)
├── app.py              # 기존 애플리케이션
├── init_all_test_db.py # 전체 테스트 DB 초기화 스크립트
├── init_test_db.py     # 로컬 테스트 DB 초기화 스크립트
├── init_onedrive_test_db.py # OneDrive 테스트 DB 초기화 스크립트
├── check_test_db.py    # 테스트 DB 확인 스크립트
├── init_all_test_db.bat # 전체 테스트 DB 초기화 배치 파일
├── init_test_db.bat    # 로컬 테스트 DB 초기화 배치 파일
├── ios26_ui_design.py  # iOS 26 UI 디자인 시스템
├── requirements.txt    # Python 의존성
├── README.md          # 프로젝트 문서
├── db/
│   ├── material_rq.db # SQLite 데이터베이스
│   └── images/        # 업로드된 이미지
├── static/
│   ├── ios26_design.css # iOS 26 CSS 스타일
│   └── ios26_ui.js     # iOS 26 JavaScript
└── templates/
    └── ios26_main.html # iOS 26 메인 템플릿
```

## 🎨 UI/UX 특징

### 모던 디자인
- **글래스모피즘**: 반투명 효과와 블러 처리
- **iOS 26 색상**: Apple의 공식 색상 팔레트
- **SF Pro 폰트**: Apple의 시스템 폰트
- **부드러운 애니메이션**: iOS 스타일 전환 효과

### 터치 최적화
- **큰 터치 영역**: 44px 최소 터치 타겟
- **스와이프 제스처**: 직관적인 네비게이션
- **햅틱 피드백**: 터치 반응 향상
- **키보드 최적화**: 모바일 키보드 대응

### 반응형 디자인
- **모바일 우선**: 모바일 환경 최적화
- **태블릿 지원**: iPad 및 태블릿 최적화
- **데스크톱 호환**: PC 환경에서도 완벽 동작
- **다양한 해상도**: 모든 화면 크기 지원

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
- [x] 테스트 데이터베이스
- [x] iOS 26 UI/UX 디자인
- [x] 자재요청 CRUD

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

## 📱 PWA 설치 방법

### iOS Safari
1. 웹사이트 접속
2. 공유 버튼 탭
3. "홈 화면에 추가" 선택
4. 앱 이름 확인 후 "추가" 탭

### Android Chrome
1. 웹사이트 접속
2. 메뉴 버튼 탭
3. "홈 화면에 추가" 선택
4. 앱 이름 확인 후 "추가" 탭

## 🔧 개발 환경

### 필수 요구사항
- Python 3.8+
- Flask 2.0+
- SQLite3
- 모던 웹 브라우저

### 개발 도구
- VS Code (권장)
- Python 확장
- Live Server 확장

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 지원

문제가 있거나 제안사항이 있으시면 이슈를 생성해주세요.

---

**HPNT Manager V2.0** - 💎 차세대 자재관리 시스템
