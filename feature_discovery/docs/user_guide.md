# feature_discovery — 사용 설명서

---

## 1. 환경 요구사항

- Python 3.7+
- MySQL 실행 중 (`daily_buy_list`, `daily_craw` DB 존재)
- `library/cf.py`의 DB 접속 정보 정상 설정
- OPT10045 backfill 완료 — `inst_buy_ratio`/`foreign_buy_ratio` 사용 시 필수
  ```bash
  python backfill_inst_data.py           # daily_craw에 수급 데이터 수집
  python migration_inst_to_daily_buy_list.py  # daily_buy_list에 복사
  ```
- ML 패키지 설치 (ml_analysis와 공유)
  ```bash
  pip install catboost lightgbm scikit-learn shap
  ```

---

## 2. 실행 위치

반드시 프로젝트 루트에서 실행.

```bash
cd "C:\Users\USER\Desktop\Personal project\trading_bot"
python -m feature_discovery.main [옵션]
```

---

## 3. 빠른 시작

### Step 1 — 첫 실행 (빠른 테스트)

전체 기간 데이터 로드에 10~20분 걸린다. 먼저 샘플링으로 구조 확인.

```bash
# 5일마다 1개 샘플링 (약 20% 데이터, 로드 ~2분)
python -m feature_discovery.main --sample_every 5 --mode boost
```

### Step 2 — 캐시 저장 후 전체 분석

```bash
# 전체 데이터 로드 + 캐시 저장 (첫 실행 10~20분)
python -m feature_discovery.main --cache fd_cache.parquet --mode boost

# 이후 캐시 재사용 (DB 접속 없이 즉시 실행)
python -m feature_discovery.main --cache fd_cache.parquet --mode boost
```

### Step 3 — 목적별 실행

```bash
# 수급 피처만 집중 확인
python -m feature_discovery.main --cache fd_cache.parquet \
    --groups supply momentum --horizon 10 --mode boost

# 단기(5일) vs 중기(15일) 비교
python -m feature_discovery.main --cache fd_cache.parquet --horizon 5  --mode boost
python -m feature_discovery.main --cache fd_cache.parquet --horizon 15 --mode boost

# 상관분석만 (가장 빠름, ~1분)
python -m feature_discovery.main --cache fd_cache.parquet --mode corr_only

# 큰 수익(+3% 이상)을 예측하는 피처
python -m feature_discovery.main --cache fd_cache.parquet --label big_win --mode boost

# 최대 상승 가능성 예측
python -m feature_discovery.main --cache fd_cache.parquet --label max --mode boost

# 특정 기간만 분석
python -m feature_discovery.main --start 20240101 --end 20251231 \
    --cache fd_cache_2024.parquet --mode boost
```

---

## 4. 전체 옵션 표

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--start` | `20230101` | 데이터 시작일 (YYYYMMDD) |
| `--end` | 오늘 | 데이터 종료일 (YYYYMMDD) |
| `--horizon` | `10` | 예측 호라이즌 (거래일 수) |
| `--label` | `win` | 라벨 유형 (아래 표 참조) |
| `--mode` | `boost` | 실행 모드 (아래 표 참조) |
| `--groups` | 전체 | 사용할 피처 그룹 (아래 표 참조) |
| `--sample_every` | `1` | N일마다 1개 샘플링 (빠른 테스트: 5~10) |
| `--n_splits` | `5` | Walk-Forward CV fold 수 |
| `--top_n` | `20` | 중요도/상관계수 표시 상위 N개 |
| `--output` | `feature_discovery/output/` | 결과 저장 디렉토리 |
| `--cache` | 없음 | parquet 캐시 경로. 있으면 로드, 없으면 생성 |

### `--label` 옵션

| 값 | 타입 | 설명 |
|---|---|---|
| `win` | 이진 | N일 후 수익률 > 0 (기본) |
| `big_win` | 이진 | N일 후 수익률 > 3% |
| `return` | 회귀 | N일 후 실제 수익률 (연속값) |
| `max` | 회귀 | N일 내 최대 고가 수익률 (순수 상승 가능성) |

> `max`가 가장 순수: 조정/하락 구간에서도 고점 가능성 측정.  
> `win`이 가장 직관적: 매수 후 수익 여부.

### `--mode` 옵션

| 모드 | 실행 내용 | 소요 시간 (캐시 있을 때) |
|---|---|---|
| `corr_only` | Pearson 상관분석 + 차트 | ~1분 |
| `quick` | 상관분석 + CatBoost | ~3분 |
| `boost` | 상관분석 + CatBoost + LightGBM + LASSO + Permutation + SHAP | ~8분 |
| `full` | `boost` + RandomForest | ~12분 |

> 데이터 규모 (300K~500K행)로 인해 ml_analysis보다 1.5~2배 시간 소요.

### `--groups` 옵션

| 그룹명 | 포함 피처 | 설명 |
|---|---|---|
| `price` | d1_diff_rate, close_vs_clo5/20/60/120, clo5/20_diff_rate | 가격 모멘텀 |
| `volume` | vol_ratio_5_20, volume_ratio, obv, mfi14, cmf20 | 거래량 |
| `momentum` | rsi14, macd, macd_histogram, adx, plus_di, minus_di, di_diff | 오실레이터 |
| `volatility` | bb_position, bb_bandwidth, atr_rate | 변동성 |
| `pattern` | candle_pattern_score | 캔들 패턴 |
| `ichimoku` | ichimoku_tenkan_vs_close, ichimoku_kijun_vs_close | 일목균형표 |
| `supply` | inst_buy_ratio, foreign_buy_ratio | 기관/외국인 수급 |

```bash
# 수급 + 모멘텀만
python -m feature_discovery.main --cache fd_cache.parquet \
    --groups supply momentum --mode boost

# 변동성 + 거래량만
python -m feature_discovery.main --cache fd_cache.parquet \
    --groups volatility volume --mode boost
```

---

## 5. 출력 파일

결과는 `feature_discovery/output/`에 저장.  
파일명 접두사: `h{horizon}_{label}_{groups}` 형태.

예) `--horizon 10 --label win --groups all` → 접두사 `h10_win_all`

| 파일 | 내용 |
|---|---|
| `corr_h10_win_all.png` | Pearson r 수평 막대그래프 |
| `correlation_h10_win_all.csv` | Pearson r 수치 전체 |
| `importance_h10_win_all.png` | 모델별 피처 중요도 차트 |
| `importance_cmp_h10_win_all.png` | 모델 간 비교 (boost/full) |
| `importance_catboost_*.csv` | CatBoost 피처 중요도 |
| `importance_lightgbm_*.csv` | LightGBM 피처 중요도 |
| `importance_lasso_*.csv` | LASSO 계수 (0 = 불필요 피처) |
| `perm_importance_*.csv` | Permutation Importance |
| `cv_scores_catboost_*.csv` | Fold별 AUC/RMSE |
| `shap_bee_h10_win_all.png` | SHAP Beeswarm plot |
| `shap_bar_h10_win_all.png` | SHAP 전역 중요도 bar plot |

---

## 6. 캐시 운영 전략

데이터 로드가 오래 걸리므로 캐시를 적극 활용한다.

```bash
# 기간별 캐시 분리 (기간 변경 시 새로 생성)
python -m feature_discovery.main \
    --start 20230101 --end 20261231 \
    --cache fd_full.parquet --mode boost

python -m feature_discovery.main \
    --start 20240101 --end 20261231 \
    --cache fd_2024.parquet --mode boost

# 샘플링 캐시 (빠른 실험용)
python -m feature_discovery.main \
    --sample_every 5 \
    --cache fd_sample5.parquet --mode boost

# 캐시는 parquet 형식 — pandas로 직접 열어볼 수 있음
import pandas as pd
df = pd.read_parquet('fd_full.parquet')
print(df.columns.tolist())
print(df['fwd_return_10d'].describe())
```

---

## 7. 수급 데이터 준비 확인

```bash
# backfill 완료 여부 확인 (MySQL)
SELECT
    COUNT(*) AS total_stocks,
    SUM(inst_backfill_done) AS done,
    COUNT(*) - SUM(inst_backfill_done) AS remaining
FROM daily_buy_list.stock_item_all;

# 샘플 종목의 inst 데이터 확인
SELECT date, inst_net_buy, foreign_net_buy
FROM daily_craw.`삼성전자`
WHERE inst_net_buy IS NOT NULL
ORDER BY date DESC LIMIT 10;

# daily_buy_list에 컬럼 존재 여부
SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema = 'daily_buy_list'
  AND table_name = '20260610'
  AND column_name IN ('inst_net_buy', 'foreign_net_buy');
-- 결과가 2이면 정상
```

수급 데이터가 없는 경우:
```bash
python backfill_inst_data.py          # ~20~30분 소요
python migration_inst_to_daily_buy_list.py  # ~5~10분 소요
```

---

## 8. 자주 묻는 질문

**Q. 로드 시간이 너무 오래 걸린다.**  
A. `--sample_every 5` 로 5배 빠르게 테스트. 결과 확인 후 캐시로 전체 실행.

**Q. `fwd_return_10d`가 모두 NaN이다.**  
A. 최근 10 거래일 이후 가격 데이터가 없는 것. `--end`를 오늘 기준 10 거래일 이전으로 조정.

**Q. inst_buy_ratio가 대부분 -1(NaN 채움)이다.**  
A. backfill/migration이 미실행된 날짜. 수급 데이터 준비 후 캐시 재생성.

**Q. feature_discovery와 ml_analysis 결과가 다르다.**  
A. 정상이다. ml_analysis는 필터 통과 거래만, feature_discovery는 전체 후보.  
두 결과가 일치하는 피처만 진짜 강한 신호다.
