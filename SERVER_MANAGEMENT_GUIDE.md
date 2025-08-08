# 🛡️ HPNT ENG Manager V2.0 서버 관리 가이드

## 📋 중복 서버 실행 방지 가이드

### 🚨 문제 상황
- 5001 포트에 여러 서버가 동시 실행
- 브라우저가 예측 불가능한 서버에 연결
- 코드 변경사항이 적용되지 않는 현상

### ✅ 해결책: 안전한 서버 관리

## 🚀 1. 권장 방법: 배치 스크립트 사용

### 서버 시작
```bash
# 안전한 서버 시작 (권장)
start_server.bat
```

### 서버 종료
```bash
# 안전한 서버 종료 (권장)
stop_server.bat
```

## 🔧 2. 수동 방법: 단계별 체크

### 서버 시작 전 체크리스트
```bash
# 1. 포트 사용 확인
netstat -ano | findstr :5001

# 2. 기존 프로세스 종료 (필요시)
taskkill /F /IM python.exe

# 3. 포트 해제 확인
netstat -ano | findstr :5001
# (결과가 없으면 포트가 깨끗함)

# 4. 서버 시작
python app_new.py
```

### 서버 종료 체크리스트
```bash
# 1. Ctrl+C로 서버 종료 시도

# 2. 프로세스 확인
netstat -ano | findstr :5001

# 3. 강제 종료 (필요시)
taskkill /F /IM python.exe

# 4. 최종 확인
netstat -ano | findstr :5001
```

## 🔍 3. 문제 진단 방법

### 포트 사용 상태 확인
```bash
# 5001 포트 사용 프로세스 확인
netstat -ano | findstr :5001

# 모든 Python 프로세스 확인
tasklist /FI "IMAGENAME eq python.exe"
```

### 브라우저 캐시 문제 해결
```bash
# 하드 새로고침
Ctrl + F5

# 개발자 도구에서 캐시 비우기
F12 → Network 탭 → "Disable cache" 체크
```

## 🚨 4. 응급 상황 대처법

### 모든 Python 프로세스 강제 종료
```bash
taskkill /F /IM python.exe
```

### 특정 PID 프로세스 종료
```bash
taskkill /F /PID [PID번호]
```

### 포트 강제 해제 (극단적 상황)
```bash
# 관리자 권한으로 실행
netsh int ip reset
```

## 📝 5. 예방 수칙

### ✅ DO (권장사항)
- `start_server.bat` 사용하여 서버 시작
- 서버 종료 시 `stop_server.bat` 사용
- 코드 변경 후 반드시 서버 재시작
- 브라우저 하드 새로고침 (`Ctrl+F5`) 습관화

### ❌ DON'T (금지사항)
- 여러 터미널에서 동시 서버 실행
- 서버 종료 없이 새 서버 시작
- `python app_new.py` 직접 실행 (배치 스크립트 우선)
- 브라우저 일반 새로고침에만 의존

## 🔧 6. 내장 안전 기능

### 자동 포트 충돌 감지
- 서버 시작 시 자동으로 포트 사용 상태 확인
- 충돌 감지 시 안전한 해결 방법 안내
- 5초 후 자동 종료로 중복 실행 방지

### 환경별 최적화
- **로컬 환경**: 포트 충돌 체크 활성화
- **클라우드 환경**: 포트 체크 비활성화 (성능 최적화)

## 📊 7. 모니터링 명령어

### 실시간 포트 모니터링
```bash
# 5초마다 포트 상태 확인
for /l %i in (1,0,2) do (netstat -ano | findstr :5001 && timeout /t 5)
```

### 서버 상태 확인
```bash
# 서버 응답 확인
curl http://127.0.0.1:5001/health
```

## 🎯 8. 성공 확인 방법

### 정상 서버 실행 확인
1. **URL 버전**: `?v=YYYYMMDD_HHMMSS_responsive_ui` (동적)
2. **버튼 링크**: `/requests`, `/stats` (버전 파라미터 없음)
3. **포트 상태**: 단일 프로세스만 5001 포트 사용
4. **브라우저**: 새로운 UI/기능이 즉시 반영

### 문제 상황 식별
1. **URL 버전**: 고정된 이전 버전 표시
2. **버튼 링크**: 버전 파라미터 포함
3. **포트 상태**: 여러 프로세스가 동시 사용
4. **브라우저**: 변경사항이 반영되지 않음

---

## 📞 문제 발생 시 체크리스트

1. ✅ `stop_server.bat` 실행
2. ✅ `netstat -ano | findstr :5001` 확인
3. ✅ `start_server.bat` 실행
4. ✅ 브라우저 하드 새로고침 (`Ctrl+F5`)
5. ✅ URL 버전이 동적으로 변경되는지 확인

이 가이드를 따르면 중복 서버 실행 문제를 완전히 예방할 수 있습니다! 🎯
