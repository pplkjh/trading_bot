# Windows 작업 스케줄러 XML 파일

이 폴더에는 자동 매매 시스템을 위한 Windows 작업 스케줄러 XML 파일 4개가 포함되어 있습니다.

## 📁 파일 목록

| 파일명 | 실행 시간 | 설명 |
|--------|----------|------|
| `TradingBot_Morning_Collector.xml` | 08:40 (평일) | 아침 장 시작 전 데이터 수집 |
| `TradingBot_Auto_Trading.xml` | 08:50 (평일) | 자동 매매 프로그램 실행 |
| `TradingBot_Evening_Collector.xml` | 15:35 (평일) | 장 마감 후 데이터 최종 수집 |
| `TradingBot_Smart_Shutdown.xml` | 20:50 (매일) | 스마트 종료 (주말: 즉시, 평일: 21시) |

## 🚀 사용 방법

### 1. 작업 스케줄러 열기
```
윈도우 키 + R → taskschd.msc 입력 → 확인
```

### 2. XML 파일 가져오기
1. 왼쪽의 **작업 스케줄러 라이브러리** 우클릭
2. **작업 가져오기** 클릭
3. 이 폴더의 XML 파일 선택 (예: `TradingBot_Morning_Collector.xml`)
4. **확인** 클릭
5. 나머지 3개 파일도 동일하게 가져오기

### 3. 경로 확인 (중요!)
각 작업을 가져온 후:
1. 작업 우클릭 → **속성**
2. **동작** 탭 확인
3. Python 경로와 trading_bot 폴더 경로가 본인 환경과 맞는지 확인

기본 경로:
- **Python**: `python.exe` (PATH에 등록되어 있어야 함)
- **작업 디렉토리**: `%USERPROFILE%\trading_bot`

## ⚙️ 실행 프로그램 정보

각 XML 파일에 정의된 실행 프로그램:

### Morning Collector & Evening Collector
```
프로그램: python.exe
인수: collector_advanced.py
작업 디렉토리: %USERPROFILE%\trading_bot
```

### Auto Trading
```
프로그램: python.exe
인수: trader_advanced.py
작업 디렉토리: %USERPROFILE%\trading_bot
```

### Smart Shutdown
```
프로그램: cmd.exe
인수: /c "%USERPROFILE%\trading_bot\batch\smart_shutdown.bat"
작업 디렉토리: %USERPROFILE%\trading_bot\batch
```

## 🔧 설정 옵션

모든 작업에 공통 적용된 설정:

- **실행 권한**: 가장 높은 수준의 권한
- **배터리**: 배터리 사용 시에도 실행
- **실패 시 재시작**: 1분 간격으로 최대 3회
- **제한 시간**:
  - Collector: 2시간
  - Trader: 8시간
  - Smart Shutdown: 2시간

## 📖 자세한 가이드

전체 설정 가이드는 프로젝트 루트의 `WINDOWS_SCHEDULER_GUIDE.md` 파일을 참고하세요.

## ⚠️ 주의사항

1. **Python 경로**: Python이 시스템 PATH에 등록되어 있어야 합니다.
2. **작업 디렉토리**: `trading_bot` 폴더가 사용자 홈 디렉토리에 있어야 합니다.
3. **권한**: 작업이 "가장 높은 수준의 권한"으로 실행되도록 설정되어 있습니다.
4. **테스트**: 실제 운영 전에 각 작업을 수동으로 실행하여 정상 작동을 확인하세요.

## 🧪 테스트 방법

각 작업을 우클릭 → **실행**하여 즉시 테스트할 수 있습니다.

로그 확인:
```
trading_bot/logs/
├── jackbot.log           # Trader 로그
├── collector.log         # Collector 로그
└── trading_events.log    # 매매 이벤트 로그
```

## 🎉 완료!

4개의 작업을 모두 가져오면 완전 자동화 시스템이 완성됩니다!
