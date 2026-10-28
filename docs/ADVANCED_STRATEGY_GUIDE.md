# 고급 매매 전략 시스템 가이드

## 🎯 개요

이 프로젝트는 기존 트레이딩 봇을 **실전 자동 매매에 최적화된 고급 시스템**으로 업그레이드한 버전입니다.

### 주요 개선 사항

1. **멀티팩터 스코어링 시스템** - 5가지 팩터를 종합한 종목 평가
2. **하이브리드 전략** - 모멘텀 돌파(60%) + 평균회귀(40%)
3. **동적 리스크 관리** - ATR 기반 포지션 사이징
4. **고급 청산 전략** - 트레일링 스톱, 다중 청산 조건
5. **성과 분석 도구** - Sharpe, Sortino, MaxDD 등 전문 지표

---

## 📦 새로 추가된 모듈

### 1. **risk_manager.py** - 리스크 관리
- ATR 기반 동적 포지션 사이징
- Kelly Criterion 포지션 계산
- 포트폴리오 레벨 리스크 체크
- 상관관계 기반 분산투자
- 트레일링 스톱 계산

**주요 클래스:**
```python
from library.risk_manager import RiskManager

rm = RiskManager(
    portfolio_value=10000000,
    risk_profile='aggressive',  # 'conservative', 'moderate', 'aggressive'
    max_position_pct=0.15,      # 단일 포지션 최대 15%
    max_daily_loss_pct=-0.08    # 일일 최대 손실 -8%
)

# ATR 기반 포지션 사이징
shares = rm.calculate_position_size_atr(
    current_price=50000,
    atr=2000
)

# 손절가/목표가 계산
stop_loss = rm.calculate_stop_loss(entry_price=50000, atr=2000)
profit_target = rm.calculate_profit_target(entry_price=50000, atr=2000)
```

### 2. **multi_factor_scoring.py** - 멀티팩터 스코어링
- 기술적 지표 (RSI, MACD, 볼린저밴드, Stochastic)
- 모멘텀 지표 (5일/20일/60일 수익률)
- 거래량 지표 (거래량 비율, OBV)
- 변동성 지표 (ATR)
- 추세 지표 (이동평균선 배열)

**주요 클래스:**
```python
from library.multi_factor_scoring import MultiFactorScoring, get_stock_score

scorer = MultiFactorScoring()

# 종목 스코어 계산
scores = get_stock_score(code='005930', db_name='daily_buy_list')

print(f"종합 스코어: {scores['composite_score']:.1f}/100")
print(f"RSI: {scores['rsi']:.1f}")
print(f"5일 수익률: {scores['return_5d']:.2f}%")
print(f"거래량 비율: {scores['volume_ratio']:.2f}x")
```

### 3. **hybrid_strategy.py** - 하이브리드 전략
- 모멘텀 브레이크아웃 전략 (변동성 돌파, 거래량 확인)
- 평균회귀 전략 (RSI 과매도, 볼린저밴드 하단)
- 전략 조합 및 가중 평균

**주요 클래스:**
```python
from library.hybrid_strategy import HybridStrategy

strategy = HybridStrategy(
    momentum_weight=0.6,        # 모멘텀 60%
    mean_reversion_weight=0.4,  # 평균회귀 40%
    min_score=70.0              # 최소 진입 스코어
)

# 매매 시그널 생성
signal = strategy.get_hybrid_signal(df)  # df = OHLCV DataFrame

if signal['signal'] == 'BUY':
    print(f"매수 시그널! (스코어: {signal['score']:.1f})")
    print(f"전략 타입: {signal['strategy_type']}")
```

### 4. **exit_strategy.py** - 고급 청산 전략
- ATR 기반 동적 손절/익절
- 트레일링 스톱 (수익 보호)
- 시간 기반 청산 (최대 보유기간)
- 팩터 스코어 기반 청산
- 기술적 지표 청산 (데드크로스, RSI 과매수 등)

**주요 클래스:**
```python
from library.exit_strategy import ExitStrategy

exit_strategy = ExitStrategy(
    atr_stop_multiplier=2.0,          # ATR 2배 손절
    trailing_stop_activation=0.05,    # 5% 수익 시 활성화
    max_holding_days=10               # 최대 10일 보유
)

# 청산 판단
position = {
    'code': '005930',
    'entry_price': 50000,
    'entry_date': datetime(2024, 1, 1),
    'shares': 10,
    'highest_price': 55000
}

decision = exit_strategy.get_exit_decision(position, current_data)

if decision['should_exit']:
    print(f"청산 시그널! - {decision['reason']}")
    print(f"청산 비율: {decision['exit_ratio']*100:.0f}%")
```

### 5. **performance_analytics.py** - 성과 분석
- 수익률 지표 (Total Return, CAGR)
- 리스크 조정 수익률 (Sharpe, Sortino, Calmar Ratio)
- 손실 지표 (Maximum Drawdown, VaR)
- 매매 통계 (Win Rate, Profit Factor)

**주요 클래스:**
```python
from library.performance_analytics import PerformanceAnalytics

analytics = PerformanceAnalytics(risk_free_rate=0.035)

# 성과 분석
report = analytics.generate_performance_report(
    equity_curve=equity_series,
    trades=trade_list
)

# 리포트 출력
analytics.print_report(report)

# 주요 지표 확인
print(f"Sharpe Ratio: {report['sharpe_ratio']:.2f}")
print(f"Maximum Drawdown: {report['max_drawdown']:.2f}%")
print(f"Win Rate: {report['win_rate']:.1f}%")
```

### 6. **advanced_strategy_system.py** - 통합 시스템
모든 모듈을 통합한 올인원 인터페이스

**주요 클래스:**
```python
from library.advanced_strategy_system import AdvancedStrategySystem

system = AdvancedStrategySystem(
    portfolio_value=10000000,
    risk_profile='aggressive'
)

# 매수 시그널 생성
buy_list = system.generate_buy_signals(
    current_positions=[],
    top_n=20
)

# 매도 시그널 생성
sell_list = system.generate_sell_signals(positions)
```

---

## 🚀 사용 방법

### 1. 매수 후보 종목 스캔

```bash
# 기본 스캔 (1000만원 포트폴리오, Top 20)
python run_advanced_strategy.py --mode scan

# 커스터마이징
python run_advanced_strategy.py --mode scan --portfolio 50000000 --top 10
```

**출력 예시:**
```
[1] 005930
  현재가:         72,000원
  종합 스코어:    85.3/100
  전략 타입:      hybrid_strong
  추천 수량:      20주
  투자 금액:      1,440,000원 (14.4%)
  손절가:         68,400원 (-5.0%)
  목표가:         78,300원 (+8.8%)
  손익비:         1.75:1
  리스크 스코어:  45.2/100
```

### 2. 성과 분석

```bash
python run_advanced_strategy.py --mode analyze --db JackBot1_imi1
```

**출력 예시:**
```
📊 PERFORMANCE REPORT
====================================
🎯 수익률 지표:
  총 수익률:        25.50%
  연평균 수익률:    18.30%
  연간 변동성:      22.10%

📈 리스크 조정 수익률:
  Sharpe Ratio:     1.35
  Sortino Ratio:    1.82
  Calmar Ratio:     1.52

📉 손실 지표:
  최대 낙폭:        -12.05%
  회복 기간:        23일

💼 매매 통계:
  승률:             58.5%
  Profit Factor:    1.82
```

### 3. Python 코드에서 직접 사용

```python
from library.advanced_strategy_system import create_optimized_buy_list

# 매수 리스트 생성
buy_list = create_optimized_buy_list(
    portfolio_value=10000000,
    risk_profile='aggressive',
    top_n=20
)

# 결과 확인
for idx, row in buy_list.iterrows():
    print(f"{row['code']}: {row['composite_score']:.1f}점")
```

---

## ⚙️ 전략 설정

### 리스크 프로필

**1. Conservative (보수적)**
- 포지션 크기: 5%
- 거래당 리스크: 1%
- 최대 포지션 수: 15개
- ATR 손절 배수: 3.0x

**2. Moderate (중도)**
- 포지션 크기: 10%
- 거래당 리스크: 2%
- 최대 포지션 수: 12개
- ATR 손절 배수: 2.5x

**3. Aggressive (공격적)** ⭐ 기본값
- 포지션 크기: 15%
- 거래당 리스크: 3%
- 최대 포지션 수: 10개
- ATR 손절 배수: 2.0x

### 전략 가중치 조정

```python
from library.hybrid_strategy import HybridStrategy

# 모멘텀 중심 (80:20)
strategy = HybridStrategy(
    momentum_weight=0.8,
    mean_reversion_weight=0.2
)

# 평균회귀 중심 (30:70)
strategy = HybridStrategy(
    momentum_weight=0.3,
    mean_reversion_weight=0.7
)
```

---

## 📊 전략 로직

### 매수 조건 (AND 조건)

1. **멀티팩터 스코어 ≥ 70점**
   - 기술적 지표 (25%)
   - 모멘텀 (30%)
   - 거래량 (20%)
   - 변동성 (15%)
   - 추세 (10%)

2. **하이브리드 전략 시그널**
   - 모멘텀 브레이크아웃 OR
   - 평균회귀 반등

3. **리스크 관리 통과**
   - 포트폴리오 리스크 한도 내
   - 상관관계 < 0.7
   - 리스크 스코어 ≤ 70점

### 매도 조건 (OR 조건)

1. **ATR 손절** (최우선, 우선순위 100)
   - 가격 ≤ 진입가 - (ATR × 2)

2. **트레일링 스톱** (우선순위 90)
   - 수익 ≥ 5% 시 활성화
   - 최고가에서 ATR × 2 하락

3. **ATR 목표가** (우선순위 70)
   - 가격 ≥ 진입가 + (ATR × 3)
   - 50% 부분 청산

4. **시간 기반 청산** (우선순위 60)
   - 보유 10일 초과
   - 5일 후 손실 ≤ -2%

5. **기술적 청산** (우선순위 50)
   - 이동평균 데드크로스
   - RSI 과매수 (80 이상)
   - MACD 히스토그램 음전환

6. **팩터 스코어 악화** (우선순위 40)
   - 현재 스코어 < 40점

---

## 📈 성과 메트릭

### 수익률 지표
- **Total Return**: 총 수익률
- **CAGR**: 연평균 수익률
- **Volatility**: 연간 변동성

### 리스크 조정 수익률
- **Sharpe Ratio**: (수익률 - 무위험이자율) / 변동성
- **Sortino Ratio**: Sharpe와 유사하나 하방 변동성만 고려
- **Calmar Ratio**: CAGR / |Max Drawdown|

### 손실 지표
- **Maximum Drawdown**: 최대 낙폭 (%)
- **Recovery Time**: 최고점 회복 기간
- **VaR (95%)**: 95% 신뢰수준 손실 한도

### 매매 통계
- **Win Rate**: 승률 (%)
- **Profit Factor**: 총 이익 / 총 손실
- **Win/Loss Ratio**: 평균 수익 / 평균 손실

---

## 🔧 고급 활용

### 1. 커스터마이징된 전략 실행

```python
from library.advanced_strategy_system import AdvancedStrategySystem

# 커스텀 설정
custom_config = {
    'min_factor_score': 75.0,      # 더 엄격한 진입
    'min_hybrid_score': 75.0,
    'max_positions': 8,             # 집중 투자
    'max_position_pct': 0.20,       # 더 큰 포지션
    'max_daily_loss_pct': -0.10,    # 더 넓은 손실 허용
    'atr_stop_multiplier': 1.5,     # 더 타이트한 손절
    'trailing_stop_activation': 0.03,  # 빠른 트레일링 활성화
    'max_holding_days': 15          # 더 긴 보유
}

system = AdvancedStrategySystem(
    portfolio_value=50000000,
    risk_profile='aggressive',
    strategy_config=custom_config
)

buy_list = system.generate_buy_signals(top_n=10)
```

### 2. 특정 종목군만 스캔

```python
# KOSPI200 종목만 스캔
kospi200_codes = ['005930', '000660', '035420', ...]  # 종목 리스트

buy_list = system.generate_buy_signals(
    stock_codes=kospi200_codes,
    top_n=10
)
```

### 3. 실시간 모니터링

```python
# 현재 포지션
positions = [
    {
        'code': '005930',
        'entry_price': 70000,
        'entry_date': datetime(2024, 11, 1),
        'shares': 20,
        'highest_price': 72000
    }
]

# 매도 시그널 체크
sell_signals = system.generate_sell_signals(positions)

for signal in sell_signals:
    if signal['decision']['should_exit']:
        print(f"[매도] {signal['code']}: {signal['decision']['reason']}")
```

---

## 🎓 전략 성능 개선 Tips

### 1. 승률 향상
- `min_factor_score` 증가 (70 → 75)
- 거래량 필터 강화
- AI 예측 모델 통합 (별도 구현 필요)

### 2. 손익비 개선
- `risk_reward_ratio` 증가 (1.5 → 2.0)
- 트레일링 스톱 적극 활용
- 부분 청산 비율 조정

### 3. 최대 낙폭 감소
- `atr_stop_multiplier` 감소 (2.0 → 1.5)
- `max_position_pct` 감소 (0.15 → 0.10)
- 상관관계 필터 강화

### 4. 시장 환경 적응
- 변동성 높은 시장: 모멘텀 가중치 증가
- 변동성 낮은 시장: 평균회귀 가중치 증가
- 약세장: `risk_profile='conservative'`

---

## 📝 주의사항

1. **백테스팅 결과와 실전 차이**
   - 슬리피지, 시장 충격 미반영
   - 실전에서는 체결가가 다를 수 있음

2. **데이터 품질**
   - 종목 분할, 배당 등 기업 행동 확인 필요
   - 데이터 누락 종목 주의

3. **시장 상황 변화**
   - 과거 성과가 미래를 보장하지 않음
   - 정기적인 파라미터 재최적화 필요

4. **리스크 관리**
   - 일일 최대 손실 한도 엄수
   - 감정적 판단 배제

---

## 🆘 문제 해결

### Q1: 매수 후보가 없습니다
- `min_score` 낮추기 (70 → 65)
- 스캔 종목 수 늘리기
- 시장 상황 확인 (약세장에서는 후보 적음)

### Q2: 손절이 너무 자주 발생합니다
- `atr_stop_multiplier` 증가 (2.0 → 2.5)
- 진입 조건 강화 (`min_score` 증가)

### Q3: 수익이 나도 빨리 청산됩니다
- `trailing_stop_activation` 증가 (0.05 → 0.08)
- `max_holding_days` 증가

---

## 📞 지원

문제 발생 시:
1. 로그 확인
2. 데이터베이스 연결 상태 확인
3. 종목 데이터 유효성 확인

---

## 🎉 결론

이 고급 전략 시스템은:
- ✅ 다양한 시장 환경에 적응
- ✅ 체계적인 리스크 관리
- ✅ 수익 보호 메커니즘
- ✅ 전문적인 성과 분석

**성공적인 트레이딩을 위해서는:**
1. 충분한 백테스팅
2. 점진적 자본 투입
3. 꾸준한 모니터링
4. 지속적인 개선

Happy Trading! 🚀
