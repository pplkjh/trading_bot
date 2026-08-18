# db 계정
db_id='bot' # [mysql ID를 넣어주세요]
# db ip
db_ip='localhost'
# db 패스워드
db_passwd='qwer1232' # [mysql password 를 넣어주세요]

# db port가 3306이 아닌 다른 port를 사용 하시는 분은 아래 변수에 포트에 맞게 수정하셔야합니다.
db_port='3306'

# 모의 투자 계좌번호를 넣는다. 모의 투자 계좌는 3개월에 한번씩 만료 되기 때문에 3개월 이용 후 재신청 하게 되면 계좌 번호가 변경된다.
# 이때 계정이 존재 하지 않는다!!! 는 에러가 뜰텐데 그때 변경 된 계좌번호를 다시 아래 imi1_account 변수에 넣으면 된다.
# 계좌 번호 쉽게 알아보는법:  콘솔창에 보면 상단 부분에 로그로 "계좌번호 :  " 옆에 출력이 된다
imi1_accout = "8127145311" # [모의투자 계좌번호를 넣어주세요. 주의! 10자리 계좌번호입니다. 모의투자는 8자리 계좌번호 뒤에 11, 실전은 10이 붙어 있음]

# imi1_simul_num은 알고리즘의 번호이다. 새로운 알고리즘으로 새롭게 database를 구축해서 운영하고 싶을 경우 번호를 2, 3, 4 ... 순차적으로 올려 주면 된다.
# simul_num=4/5/6은 모두 jackbot4_imi1 DB를 공유한다.
imi1_simul_num=6
imi1_db_name = ("jackbot4_imi1" if imi1_simul_num in (4, 5, 6)
                else "jackbot5_imi1" if imi1_simul_num == 10
                else "jackbot"+str(imi1_simul_num)+"_imi1")


# 아래는 실전 투자 계좌번호를 넣는다.
real_account=""
real_simul_num=6
real_db_name="jackbot"+str(real_simul_num)


real_daily_craw_db_name = "daily_craw"
real_daily_buy_list_db_name = "daily_buy_list"

# daily_buy_list database의 날짜 테이블을 과거 어떤 시점 부터 만들 것인지 설정 하는 변수
start_daily_buy_list='20230102'

# openapi 1회 조회 시 대기 시간(0.2 보다-> 0.3이 안정적)
TR_REQ_TIME_INTERVAL = 0.3

# n회 조회를 1번 발생시킨 경우 대기 시간
TR_REQ_TIME_INTERVAL_LONG = 1

# api를 최대 몇 번까지 호출 하고 봇을 끌지 설정 하는 옵션
# 데이터 수집 시: 99999 (거의 무제한)
# 일반 트레이딩 시: 999 (안전)
max_api_call = 4500

# dart api key (고급클래스에서 소개)
dart_api_key = ''

# etf 사용 여부 (고급클래스에서 소개)
use_etf = False

# 분봉 데이터 수집 여부
# True: 분봉 수집 (백테스팅 정밀도 향상, 시간 오래 걸림)
# False: 분봉 수집 안 함 (스윙 트레이딩은 일봉만으로 충분)
use_min_crawler = False

# dart api key
# dart_api_key = '8c44ace91948ce4d34b8ba27051836c2c8c35257'
dart_api_key = 'cc3e62c424689322f224f18b4f5ab5f6bfdb5497'

# ===== v2 확장 Scoring 설정 (simul_num=3 전용) =====
# 종목당 1회 투자 금액
# - invest_unit_pct > 0 이면 초기 자본의 퍼센트로 계산 (고정값 무시)
#   예) invest_unit_pct = 0.1 → 초기자본 10M × 10% = 1M
# - invest_unit_pct = 0.0 이면 invest_unit 고정값 사용
invest_unit     = 1_000_000   # 고정 금액 모드 (원)
invest_unit_pct = 0.0         # 퍼센트 모드 (0.0 = 고정 금액 사용)
initial_capital = 50_000_000  # 초기 투자 원금 (대시보드 원금 대비 손익 계산용)

# 250점 만점 중 최소 매수 기준점
v2_min_score = 120

# 펀더멘털 사전 필터 사용 여부
v2_fundamental_filter = True

# 펀더멘털 최소 점수 (50점 만점 중)
v2_fundamental_min_score = 15

# 펀더멘털 수집 주기 (일)
v2_fundamental_collect_interval = 1

# 동적 가중치 (ADX 기반)
v2_dynamic_weights = True

# ===== v4 Scoring (simul_num=4/5/6) =====
# v3.2 스코어링 재조정 (2026-05-29):
#   A: score_f 방향 역전 (BB압축도→BB활성도), score_a 과도 돌파 패널티 추가
#      score_a > 40pt → -20pt / score_a > 30pt → -10pt (한국 개별주 단기 역전 효과 실증)
#   B: score_d 10pt(15→10), score_f 15pt(10→15) [r=+0.1316 최고 상관 상향]
#
# min_score 확정 (2026-06-02, 백테스트 score_analyze.py + 상관분석 기반):
#   A=110: 구간별 분석에서 >=110이 avg수익 최고, composite 음의 상관 최소화
#   B=110: score_g 역방향 재설계 후 (2026-06-13) 구간별 단조성 완성
#          >=110: WR 77.8%, avg +10.32%, R=2.13 (n=761, 이전 >=90: avg +8.09%)
v4_min_score_a = 110    # BreakoutStrategyV3 — 백테스트 composite 최적 구간
v4_min_score_b = 110    # ReversalStrategyV3 — score_g 역방향 재설계 후 최적 구간

# ===== v5 Scoring (simul_num=7) =====
# sim=7: BreakoutStrategyV4 + ReversalStrategyV4 + NASDAQ gate (Layer 1)
# atr_rate 패널티 제거 (A) + NASDAQ hard gate (BEAR/OVERHEAT → skip)
# min_score 확정 (2026-06-17, 백테스트 28,965회 기반):
#   A=120: >=120 avg +5.56%, WR 68.2%, R=1.79 (단조 최고)
#   B=110: >=110 avg +8.65%, WR 74.2%, R=1.99 (단조 최고, 강한 신호)
v5_min_score_a = 120    # BreakoutStrategyV4 — 백테스트 확정
v5_min_score_b = 110    # ReversalStrategyV4 — 백테스트 확정

# ===== v6 Hybrid System (simul_num=8) =====
# sim=8: BreakoutStrategyV5 (condition) + ReversalStrategyV4 (scoring)
# A: binary condition 기반 — composite_score = optional 통과 수 (0~5)
# B: V4 scoring 기반    — composite_score = 점수 (0~240)
v6_min_opt_a  = 3    # A optional 최소 통과 수 (5개 중 3개 이상)
v6_min_score_b = 100  # B V4 scoring 최소 점수 (110→100으로 완화, 거래량 확대)

# ===== v7 Hybrid System (simul_num=9) =====
# A: BreakoutStrategyV6 (5개 조건 전부 필수) — total 항상 5.0, auto_reject로 필터
# B: ReversalStrategyV4 (scoring, sim=8과 동일)
v7_min_opt_a   = 5    # A: 5/5 전부 통과 (사실상 auto_reject가 처리)
v7_min_score_b = 100  # B: sim=8과 동일

# ===== Strategy E (simul_num=10) — 가치투자/장기투자 =====
# DART 재무 데이터 기반 우량기업 선별 (ROE≥15%, 영업이익률≥10%, 부채비율≤150%)
# buy_list_num=23 / sell_list_num=50
e_invest_unit   = 2_000_000  # 종목당 투자 금액 (원) — 일반 전략의 2배
e_max_positions = 5          # 최대 동시 보유 종목 수

# ── 백테스트 구간 ─────────────────────────────────────────────────────────
# 헤드라인 기준: 벤치마크와 정합된 구간 (추가 작업 A 결과 — kospi_index 시작일)
# 전체 구간 참고용 재실행 시에는 "20230102"로 변경
e_simul_start_date = "20230905"   # baseline_v1 헤드라인 구간 (벤치마크 정합)
e_simul_end_date   = "20260810"   # baseline_v1 헤드라인 종료 (벤치마크 정합)

# ── 레짐 게이트 (sell_list_num=50 / db_to_realtime_buy_list_num=23) ─────────
# baseline_v1에서 OFF — ablation 3-1 항목으로 보류 (판단 2, 2026-08-11)
e_regime_gate_on        = True   # 레짐 게이트 — baseline_v2 확정 (2026-08-18)
e_regime_gate_ma_period = 120    # MA 기간     — baseline_v2 확정 (Gate MA120)

# ── 매도 규칙 (sell_list_num=50) 플래그 ─────────────────────────────────────
# baseline_v1 기본값: SL_HARD, MA60이탈, RSI과매수만 ON.
# 나머지는 애블레이션 후보 — 변경 시 dump 자동 기록됨.
#
# [ON — baseline_v1]
e_sell_sl_pct         = -15.0   # ① SL 기준선 (활성화 시 이 값 사용)
e_sell_sl_hard_on     = True    # ① SL_HARD      : rate <= e_sell_sl_pct
e_sell_ma60_on        = True    # ② TREND_BREAK  : present_price < ma60
e_sell_rsi80_on       = False   # v2 RSI-OFF 확정
#
# [OFF — 애블레이션 후보. 순서는 CASE 우선순위 순]
e_sell_sl12_on        = False   # A1 | SL -12% (타이트 손절)          — sell_list_num=50 구버전
e_sell_ma120_on       = False   # A2 | MA120 이탈 (장기 추세 종료)     — sell_list_num=50 구버전
e_sell_ma60_double_on = False   # A3 | MA60+MA20 이중확인              — sell_list_num=50 구버전
e_sell_rsi78_rate_on  = False   # A4 | rsi14>=78 AND rate>=20%       — sell_list_num=50 구버전
e_sell_tp35_on        = False   # A5 | rate>=35% 목표TP               — sell_list_num=50 구버전
e_sell_time110_on     = False   # A6 | 110일 AND rate<5% 시간청산     — sell_list_num=50 구버전