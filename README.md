# 🤖 AI 기반 자동 주식 매매 시스템

키움증권 OpenAPI를 활용한 **실전 최적화 자동매매 프로그램**

---

## 📖 문서 안내

시작하기 전에 적합한 문서를 선택하세요:

| 문서 | 대상 | 내용 |
|------|------|------|
| **[⚡ QUICK_START.md](QUICK_START.md)** | 처음 시작하는 분 | 10분 안에 시작하는 빠른 가이드 |
| **[📚 USER_MANUAL.md](USER_MANUAL.md)** | 모든 사용자 | 완전한 사용 설명서 (초기 설정 ~ 실전 투자) |
| **[📊 STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)** | 전략 선택 | 전략 상세 설명 및 비교 |
| **[🚀 ADVANCED_STRATEGY_GUIDE.md](ADVANCED_STRATEGY_GUIDE.md)** | 고급 사용자 | 멀티팩터 전략, 리스크 관리 고급 기능 |
| **[🤖 AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md)** | 자동화 원하는 분 | 완전 무인 자동화 (컴퓨터 자동 켜기/끄기) |

**👉 추천 시작 순서:**
1. `QUICK_START.md` - 빠르게 시작
2. `USER_MANUAL.md` - 자세히 학습
3. `STRATEGY_GUIDE.md` - 전략 선택 및 백테스팅
4. `ADVANCED_STRATEGY_GUIDE.md` - 고급 전략 활용 (선택)
5. `AUTOMATION_GUIDE.md` - 완전 자동화 (선택)

---

## 🎯 주요 특징

### ✨ 기본 기능
- ✅ **완전 자동화** - 데이터 수집부터 매매까지 자동
- ✅ **백테스팅** - 실전 투자 전 전략 검증
- ✅ **모의투자** - 리스크 없이 실전 연습
- ✅ **실시간 모니터링** - PyQt5 GUI 대시보드
- ✅ **다양한 전략** - 이동평균, 모멘텀, AI 예측 등

### 🚀 고급 전략 시스템 (NEW!)

#### 1. **멀티팩터 스코어링**
- 5가지 팩터 종합 평가 (기술적/모멘텀/거래량/변동성/추세)
- 0-100점 스코어링으로 객관적 종목 선정

#### 2. **하이브리드 전략**
- 모멘텀 브레이크아웃 60% + 평균회귀 40%
- 다양한 시장 환경에 적응

#### 3. **동적 리스크 관리**
- ATR 기반 포지션 사이징
- Kelly Criterion 최적 포지션
- 상관관계 기반 분산투자

#### 4. **고급 청산 시스템**
- 트레일링 스톱으로 수익 보호
- 6가지 청산 조건 (우선순위 자동 판단)
- 부분 청산 지원

#### 5. **전문 성과 분석**
- Sharpe, Sortino, Calmar Ratio
- Maximum Drawdown, Win Rate
- Profit Factor, VaR 등

---

## 📦 핵심 구성 요소

### 기본 시스템

| 모듈 | 파일 | 설명 |
|------|------|------|
| **트레이더** | `trader_advanced.py` | 실시간 자동매매 GUI |
| **데이터 수집** | `collector_v3.py` | 일봉/분봉 데이터 수집 + 고급 전략 스캔 |
| **백테스팅** | `simulator.py`, `simul_run.py` | 전략 백테스트 실행 |
| **모니터링** | `monitor.py` | 포트폴리오 실시간 모니터링 |
| **성과 분석** | `performance_report.py` | 거래 성과 리포트 생성 |
| **API 래퍼** | `library/open_api.py` | 키움 OpenAPI 인터페이스 |
| **설정** | `library/cf.py` | 전역 설정 (DB, 계좌 등) |

### 고급 전략 모듈 (collector_api.py에 통합!)

| 모듈 | 파일 | 설명 |
|------|------|------|
| **날짜기반 전략** | `library/date_based_strategy.py` | 멀티팩터 스코어링 + 하이브리드 전략 통합 |
| **리스크 관리** | `library/risk_manager.py` | ATR 기반 포지션 사이징 |
| **멀티팩터** | `library/multi_factor_scoring.py` | 5가지 팩터 스코어링 시스템 |
| **하이브리드 전략** | `library/hybrid_strategy.py` | 모멘텀 + 평균회귀 전략 |
| **청산 전략** | `library/exit_strategy.py` | 트레일링 스톱, 다중 청산 |
| **성과 분석** | `library/performance_analytics.py` | 전문 성과 지표 |
| **통합 시스템** | `library/advanced_strategy_system.py` | 모든 모듈 통합 |
| **자동 스캔** | `library/collector_api.py` | 고급 전략 자동 실행 (collector_v3.py 실행 시) |

### AI/ML 모듈

| 모듈 | 파일 | 설명 |
|------|------|------|
| **LSTM 모델** | `ai/SPPModel.py` | 주가 예측 딥러닝 모델 |
| **AI 필터** | `ai_filter.py` | AI 기반 종목 필터링 |

---

## 🚀 빠른 시작

### 1️⃣ 초기 설정 (5분)

```bash
# 1. Python 패키지 설치
pip install PyQt5 pandas numpy pymysql sqlalchemy

# 2. MySQL 데이터베이스 생성
mysql -u root -p
CREATE DATABASE daily_craw;
CREATE DATABASE daily_buy_list;
CREATE DATABASE JackBot1_imi1;
```

### 2️⃣ 설정 파일 수정 (2분)

**`library/cf.py` 편집:**
```python
db_passwd = 'your_password'         # MySQL 비밀번호
imi1_accout = "8032914911"          # 모의투자 계좌번호
```

### 3️⃣ 데이터 수집 (30분-1시간)

```bash
python collector_v3.py
```

### 4️⃣ 모의투자 시작 (1분)

```bash
python trader_advanced.py
```

**✅ 완료!** 고급 전략이 적용된 자동 매매가 시작됩니다.

**더 자세한 설명:** [QUICK_START.md](QUICK_START.md) 참조

---

## 💡 사용 예시

### 매수 종목 확인하기

```bash
# 고급 전략으로 선정된 매수 후보 확인
python check_buy_list.py
```

**출력 예시:**
```
[1] 005930     삼성전자
      현재가:         72,000원
      전략:           모멘텀 돌파
      종합 스코어:    85.3/100
      거래량 비율:    2.5x
```

### 실시간 모니터링

```bash
# 포트폴리오 및 매수 후보 실시간 확인
python monitor.py
```

**출력 예시:**
```
📊 포트폴리오 현황 (JackBot1_imi1)
========================
📈 보유 종목 (3개)
총 평가금액:     10,250,000원
총 평가손익:       +250,000원
총 수익률:         +2.50%
```

### 성과 분석

```bash
# 거래 성과 리포트 생성
python performance_report.py
```

**출력 예시:**
```
📊 PERFORMANCE REPORT
====================================
총 거래:          45건
승률:             58.5%
평균 수익률:      +2.3%
최대 수익:        +15.2%
최대 손실:        -4.8%
```

### 데이터 수집 (고급 전략 자동 실행)

```bash
# collector 실행 시 자동으로 고급 전략 스캔
python collector_v3.py
```

**collector 실행 시 자동으로:**
1. 일봉/분봉 데이터 수집
2. 멀티팩터 스코어링 실행
3. 하이브리드 전략 적용
4. 매수 후보 realtime_daily_buy_list에 자동 저장

---

## 📊 전략 성능 지표

### 리스크 프로필: Aggressive (공격적)

| 항목 | 설정값 |
|------|--------|
| 보유 기간 | 3-10일 (스윙) |
| 단일 포지션 | 최대 15% |
| 거래당 리스크 | 3% |
| 일일 최대 손실 | -8% |
| 최대 포지션 수 | 10개 |

### 매수 조건
- ✅ 멀티팩터 스코어 ≥ 70점
- ✅ 하이브리드 전략 시그널
- ✅ 리스크 관리 통과

### 매도 조건 (우선순위)
1. ATR 손절 (우선순위 100)
2. 트레일링 스톱 (우선순위 90)
3. ATR 목표가 (우선순위 70)
4. 시간 기반 청산 (우선순위 60)
5. 기술적 청산 (우선순위 50)
6. 팩터 스코어 악화 (우선순위 40)

---

## 🔧 환경 요구사항

### 필수 사항
- **OS**: Windows 10/11 (64bit) - 키움 API 제약
- **Python**: 3.8 이상 (64bit)
- **MySQL**: 5.7 이상
- **RAM**: 8GB 이상 (16GB 권장)
- **저장공간**: 50GB 이상

### 키움증권
- 키움증권 계좌
- 모의투자 신청
- 영웅문 HTS 설치
- OpenAPI+ 모듈 설치

---

## 📅 일일 루틴

### 거래일 루틴 (완전 자동화)

**아침 08:30 (자동 실행)**
- 작업 스케줄러가 `trader_advanced.py` 자동 시작
- 고급 전략 매수 후보 자동 로드

**장 중 (09:00-15:30)**
- 자동 매수/매도 처리
- 실시간 모니터링: `python monitor.py`

**장 마감 후 15:40 (자동 실행)**
```bash
# 자동 실행됨:
# 1. 데이터 수집
# 2. 고급 전략 스캔
# 3. 내일 매수 후보 생성
python collector_v3.py
```

**저녁 (수동 확인)**
```bash
# 오늘 성과 확인
python performance_report.py

# 내일 매수 후보 확인
python check_buy_list.py
```

### 주말 루틴
- 주간 성과 분석
- 전략 파라미터 재검토
- 필요 시 백테스팅 재실행

---

## 📂 프로젝트 구조

```
trading_bot/
├── 📚 문서
│   ├── QUICK_START.md                 # 빠른 시작 가이드
│   ├── USER_MANUAL.md                 # 완전 사용 설명서
│   └── ADVANCED_STRATEGY_GUIDE.md     # 고급 전략 가이드
│
├── 🎯 실행 파일
│   ├── trader_advanced.py             # 고급 전략 트레이더 GUI
│   ├── collector_v3.py                # 데이터 수집 + 고급 전략 스캔
│   ├── simulator.py, simul_run.py     # 백테스터
│   ├── monitor.py                     # 실시간 모니터링
│   ├── check_buy_list.py              # 매수 후보 확인
│   └── performance_report.py          # 성과 리포트
│
├── 📦 library/ (핵심 모듈)
│   ├── cf.py                          # 전역 설정
│   ├── open_api.py                    # 키움 API 래퍼
│   ├── risk_manager.py                # 리스크 관리
│   ├── multi_factor_scoring.py        # 멀티팩터 스코어링
│   ├── hybrid_strategy.py             # 하이브리드 전략
│   ├── exit_strategy.py               # 청산 전략
│   ├── performance_analytics.py       # 성과 분석
│   └── advanced_strategy_system.py    # 통합 시스템
│
├── 🤖 ai/ (AI 모델)
│   └── SPPModel.py                    # LSTM 예측 모델
│
├── 🗄️ sql/ (데이터베이스 스키마)
│   ├── init_databases.sql
│   ├── stock_item_all_schema.sql
│   └── jackbot_schema.sql
│
└── ⏰ scheduler/ (작업 스케줄러)
    └── *.xml
```

---

## 🎓 학습 경로

### 1주차: 기초
- ✅ `QUICK_START.md` 따라하기
- ✅ 데이터 수집 성공
- ✅ 첫 백테스트 실행

### 2-4주차: 모의투자
- ✅ `trader_advanced.py`로 모의투자 시작
- ✅ 고급 전략 자동 적용
- ✅ `monitor.py`로 실시간 확인
- ✅ `performance_report.py`로 성과 분석

### 1-2개월: 고급
- ✅ `ADVANCED_STRATEGY_GUIDE.md` 학습
- ✅ 고급 전략 사용
- ✅ 파라미터 최적화

### 3개월+: 실전
- ✅ 소액 실전 투자 시작
- ✅ 전략 커스터마이징
- ✅ 지속적 개선

---

## 🛠️ 문제 해결

### 자주 묻는 질문

**Q: "계좌번호가 존재하지 않습니다" 오류**
```python
# library/cf.py 확인
imi1_accout = "8032914911"  # 정확한 10자리 입력
```

**Q: 데이터 수집이 너무 느림**
- 정상입니다 (API 제한)
- 첫 실행: 6-8시간
- 이후 업데이트: 30분-1시간

**Q: 매수가 실행되지 않음**
1. 잔고 확인 (종목당 50만원 이상)
2. 스코어 확인 (70점 이상인지)
3. 장 시간 확인 (09:00-15:30)

**더 많은 문제 해결:** [USER_MANUAL.md의 9장](USER_MANUAL.md#9-문제-해결) 참조

---

## 📈 성과 예시

(백테스트 결과 - 과거 성과가 미래를 보장하지 않음)

```
기간: 2023-01-01 ~ 2024-11-15
초기 자본: 10,000,000원

총 수익률:     25.5%
연평균 수익률: 18.3%
Sharpe Ratio:  1.35
최대 낙폭:     -12.05%
승률:          58.5%
거래 횟수:     127회
```

---

## ⚠️ 면책 조항

- 이 프로그램은 **교육 및 연구 목적**입니다
- 투자 손실에 대한 책임은 **사용자**에게 있습니다
- 충분한 테스트 없이 실전 투자 금지
- 과거 수익률이 미래를 보장하지 않습니다
- 본인의 판단과 책임 하에 사용하세요

---

## 🤝 기여

- **버그 리포트**: GitHub Issues
- **기능 제안**: Pull Request 환영
- **문의**: GitHub Discussions

---

## 📄 라이센스

이 프로젝트의 라이센스 정보는 별도로 확인하세요.

---

## 🙏 감사의 글

- 키움증권 OpenAPI
- PyQt5 커뮤니티
- TensorFlow/Keras

---

## 📞 지원

- **문서**: [USER_MANUAL.md](USER_MANUAL.md)
- **빠른 시작**: [QUICK_START.md](QUICK_START.md)
- **고급 전략**: [ADVANCED_STRATEGY_GUIDE.md](ADVANCED_STRATEGY_GUIDE.md)
- **GitHub**: [Issues](https://github.com/pplkjh/trading_bot/issues)

---

**Happy Trading! 📈🚀**

_마지막 업데이트: 2025-12-13 (고급 전략 통합 완료)_
