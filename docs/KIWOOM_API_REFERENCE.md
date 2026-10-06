# 키움 Open API 개발 레퍼런스

> Claude가 이 프로젝트에서 코드를 작성할 때 참조하는 실전 개발 문서.
> 공식 원문 → `docs/키움 OpenAPI.txt`

---

## 목차

1. [핵심 함수 레퍼런스](#1-핵심-함수-레퍼런스)
2. [이벤트 레퍼런스](#2-이벤트-레퍼런스)
3. [TR 전체 목록](#3-tr-전체-목록)
4. [프로젝트 사용 TR 상세 스펙](#4-프로젝트-사용-tr-상세-스펙)
5. [OnReceiveChejanData FID 목록](#5-onreceivechejandata-fid-목록)
6. [주문 관련 상수](#6-주문-관련-상수)
7. [에러 코드](#7-에러-코드)
8. [속도 제한 & 주의사항](#8-속도-제한--주의사항)
9. [기타 유틸리티 함수](#9-기타-유틸리티-함수)

---

## 1. 핵심 함수 레퍼런스

### TR 요청

```python
# 입력값 설정 (CommRqData 호출 전에 순서대로 설정)
SetInputValue("파라미터명", "값")

# TR 조회 요청
# next: 0=초기조회, 2=연속조회
# screen_no: 4자리 숫자 문자열 (프로젝트 화면번호 할당표 참고)
# 리턴 0=성공, -200=과부하, -201=전문작성에러
ret = CommRqData(rqname, trcode, next, screen_no)

# 복수종목 조회 (최대 100종목, OPTKWFID TR 고정)
CommKwRqData(code_arr, next=0, count, type_flag=0, rqname, screen_no)
# code_arr: "005930;000660;035420" 형식
# type_flag: 0=주식, 3=선물옵션
```

### 수신 데이터 추출 (OnReceiveTrData 이벤트 안에서만 유효)

```python
# 단일 값 추출
value = GetCommData(trcode, rqname, index, "필드명")
# 주의: 현재가 등에 앞에 부호 붙을 수 있음 → .strip() + int() 처리

# 멀티데이터 행 수
row_count = GetRepeatCnt(trcode, rqname)

# 멀티데이터 루프 패턴
for i in range(GetRepeatCnt(trcode, rqname)):
    date  = GetCommData(trcode, rqname, i, "일자").strip()
    close = int(GetCommData(trcode, rqname, i, "현재가").strip())
```

### 실시간 데이터

```python
# 실시간 등록
# opt_type: "0"=교체등록(기존해지), "1"=추가등록
SetRealReg(screen_no, "005930;000660", "9001;10;15;20", "0")

# 실시간 해제
SetRealRemove(screen_no, code)   # 특정 종목
SetRealRemove("ALL", "ALL")      # 전체 해제

# 실시간 데이터 값 추출 (OnReceiveRealData 이벤트 안에서만)
value = GetCommRealData(code, fid_number)
# 예) 현재가 = GetCommRealData(code, 10)

# 특정 화면에 등록된 실시간 전체 해제
DisconnectRealData(screen_no)
```

### 주문

```python
# 현금 주문 (리턴 0=호출성공 ≠ 주문성공)
SendOrder(rqname, screen_no, acc_no, order_type, code, qty, price, hoga_gb, org_order_no)

# 신용 주문
SendOrderCredit(rqname, screen_no, acc_no, order_type, code, qty, price, hoga_gb, credit_gb, loan_date, org_order_no)

# 체결/잔고 데이터 추출 (OnReceiveChejanData 이벤트 안에서만)
value = GetChejanData(fid_number)
# 예) 체결가 = GetChejanData(910)
```

### 로그인/계좌 정보

```python
GetLoginInfo("ACCOUNT_CNT")   # 보유계좌 수
GetLoginInfo("ACCLIST")       # 계좌번호 목록 (';'로 구분)
GetLoginInfo("USER_ID")       # 사용자 ID
GetLoginInfo("GetServerGubun") # "1"=모의투자, 나머지=실서버

# 종목 관련
GetCodeListByMarket("0")      # 코스피 종목코드 리스트 (';' 구분)
GetMasterCodeName(code)        # 종목명
GetMasterStockState(code)      # 증거금율/거래정지/관리종목 등 상태
KOA_Functions("GetStockMarketKind", code)  # 시장구분 ("0"=코스피, "10"=코스닥)
```

---

## 2. 이벤트 레퍼런스

### OnReceiveTrData — TR 조회 응답

```python
def _receive_tr_data(self, screen_no, rqname, trcode, record_name, next, *args):
    if next == '2':
        self.remained_data = True   # 연속조회 필요
    else:
        self.remained_data = False
    # GetCommData / GetRepeatCnt 여기서만 유효
```

### OnReceiveRealData — 실시간 시세

```python
def _receive_real_data(self, code, real_type, real_data):
    # real_type: "주식체결", "주식시세", "주식호가잔량" 등
    # GetCommRealData 여기서만 유효
    if real_type == "주식체결":
        price = abs(int(GetCommRealData(code, 10)))  # 현재가
        volume = abs(int(GetCommRealData(code, 15))) # 체결량 (음수=매도)
```

### OnReceiveChejanData — 주문체결/잔고 변경

```python
def _receive_chejan_data(self, gubun, item_cnt, fid_list):
    # gubun: "0"=접수/체결, "1"=국내주식 잔고변경, "4"=파생잔고
    # GetChejanData 여기서만 유효
    if gubun == "0":
        order_no = GetChejanData(9203)   # 주문번호
        status   = GetChejanData(913)    # 주문상태: 접수/체결/확인
        filled   = GetChejanData(911)    # 체결량
```

### OnReceiveMsg — 서버 메시지

```python
def _receive_msg(self, screen_no, rqname, trcode, msg):
    # 주문거부 사유, 조회에러 등 확인
    # 주의: 메시지의 6자리 코드번호는 변경될 수 있으므로 로직에 사용 금지
```

### 주문 처리 순서

```
SendOrder → OnReceiveTRData(주문번호) → OnReceiveMsg → OnReceiveChejan(접수) → OnReceiveChejan(체결) → OnReceiveChejan(잔고)
주의: 주문폭주시 OnReceiveChejan이 OnReceiveTRData보다 먼저 올 수 있음
```

---

## 3. TR 전체 목록

### OPT10000 시리즈 — 국내 주식

| TR 코드 | 한글명 | 비고 |
|---------|--------|------|
| OPT10001 | 주식기본정보요청 | PER/ROE/PBR 등 펀더멘털 |
| OPT10002 | 주식거래원요청 | - |
| OPT10003 | 주식차트패턴요청 | - |
| OPT10004 | 주식현재가요청 | - |
| OPT10005 | 주식일주월시분요청 | - |
| OPT10008 | 주식외국인요청 | - |
| OPT10009 | 주식업종코드요청 | - |
| OPT10010 | 업종별주가요청 | - |
| OPT10014 | 주식호가요청 | - |
| OPT10016 | 신고저가요청 | 거래소구분 지원 |
| OPT10017 | 상하한가요청 | 거래소구분 지원 |
| OPT10018 | 고저가근접요청 | 거래소구분 지원 |
| OPT10019 | 가격급등락요청 | 거래소구분 지원 |
| OPT10020 | 호가잔량상위요청 | 거래소구분 지원 |
| OPT10021 | 호가잔량급증요청 | 거래소구분 지원 |
| OPT10022 | 잔량율급증요청 | 거래소구분 지원 |
| OPT10023 | 거래량급증요청 | 거래소구분 지원 |
| OPT10024 | 거래량갱신요청 | 거래소구분 지원 |
| OPT10025 | 매물대집중요청 | 거래소구분 지원 |
| OPT10026 | 고저PER요청 | 거래소구분 지원 |
| OPT10027 | 전일대비등락률상위요청 | 거래소구분 지원 |
| OPT10028 | 시가대비등락률요청 | 거래소구분 지원 |
| OPT10029 | 예상체결등락률상위요청 | 거래소구분 지원 |
| OPT10030 | 당일거래량상위요청 | 거래소구분 지원 |
| OPT10031 | 전일거래량상위요청 | 거래소구분 지원 |
| OPT10032 | 거래대금상위요청 | 거래소구분 지원 |
| OPT10033 | 신용비율상위요청 | 거래소구분 지원 |
| OPT10034 | 외인기간별매매상위요청 | 거래소구분 지원 |
| OPT10035 | 외인연속순매매상위요청 | 거래소구분 지원 |
| OPT10036 | 외인한도소진율증가상위 | 거래소구분 지원 |
| OPT10037 | 외국계창구매매상위요청 | 거래소구분 지원 |
| OPT10039 | 증권사별매매상위요청 | 거래소구분 지원 |
| OPT10042 | 순매수거래원순위요청 | 거래소구분 지원 |
| OPT10043 | 거래원매물대분석요청 | 거래소구분 지원 |
| OPT10047 | 체결강도추이일별요청 | 거래소구분 지원 |
| OPT10051 | 업종별투자자순매수요청 | 거래소구분 지원 |
| OPT10052 | 거래원순간거래량요청 | 거래소구분 지원 |
| OPT10054 | 변동성완화장치발동종목요청 | 거래소구분 지원, VI발동 실시간 등록 |
| OPT10058 | 투자자별일별매매종목요청 | 거래소구분 지원 |
| OPT10062 | 동일순매매순위요청 | 거래소구분 지원 |
| OPT10063 | 장중투자자별매매요청 | 거래소구분 지원 |
| OPT10066 | 장중투자자별매매차트요청 | 거래소구분 지원 |
| OPT10070 | 당일주요거래원요청 | 싱글데이터만 |
| **OPT10073** | **일자별종목별실현손익요청** | **프로젝트 사용** |
| **OPT10074** | **당일매매현황요청** | **프로젝트 사용** |
| OPT10075 | 미체결요청 | 거래소구분 지원 (0=통합,1=KRX,2=NXT) |
| **OPT10076** | **체결요청** | **프로젝트 사용** (미체결수량 확인) 거래소구분 지원 |
| **OPT10080** | **주식분봉차트조회요청** | **프로젝트 사용** (1분봉) |
| **OPT10081** | **주식일봉차트조회요청** | **프로젝트 사용** (가장 핵심) 싱글+멀티 |
| OPT10082 | 주식주봉차트조회요청 | - |
| OPT10083 | 주식월봉차트조회요청 | - |
| OPT10085 | 계좌수익률요청 | 거래소구분 지원 |
| OPT10086 | 일별데이터조회 | 공식문서 연속조회 예시에 등장 |
| OPT10094 | 주식틱차트조회 | - |
| OPT10098 | (기타) | - |
| OPT10131 | 기관외국인연속매매현황요청 | 거래소구분 지원 |

### OPT20000 시리즈 — 업종/지수

| TR 코드 | 한글명 | 비고 |
|---------|--------|------|
| OPT20001 | 업종현재가요청 | 실시간 지수 등록 트리거 |
| OPT20002 | 업종별주가요청 | - |
| OPT20003 | 전업종지수요청 | - |
| OPT20004 | 업종틱차트조회 | - |
| OPT20005 | 업종분봉차트조회 | - |
| **OPT20006** | **업종일봉차트조회요청** | **프로젝트 사용** (KOSPI/KOSDAQ 지수) |
| OPT20007 | 업종주봉차트조회 | - |
| OPT20008 | 업종월봉차트조회 | - |
| OPT20009 | 업종거래추이요청 | - |
| OPT20019 | 업종현재가요청2 | - |
| OPT20068 | 업종시세요청 | - |

### OPT30000 시리즈 — ELW / OPT40000 — ETF / OPT50000 — 선물옵션

> 이 프로젝트에서 미사용. 필요시 KOA Studio 확인.

| TR 코드 범위 | 분류 |
|---|---|
| OPT30001~OPT30011 | ELW |
| OPT40001~OPT40010 | ETF (OPT40004=ETF전체시세) |
| OPT50001~OPT50073 | 선물옵션 |

### OPT90000 시리즈 — 테마/프로그램매매

| TR 코드 | 한글명 |
|---------|--------|
| OPT90001 | 테마그룹별요청 |
| OPT90002 | 테마구성종목요청 |
| OPT90003 | 프로그램순매수상위50요청 |
| OPT90004 | 종목별프로그램매매현황요청 |
| OPT90005 | 프로그램매매추이요청 |
| OPT90006 | 프로그램매매차익잔고추이요청 |
| OPT90007 | 프로그램매매누적추이요청 |
| OPT90009 | 외국인기관매매상위요청 |
| OPT90013 | (기타) |
| OPT99999 | (기타) |

### OPW 시리즈 — 계좌

| TR 코드 | 한글명 | 비고 |
|---------|--------|------|
| **OPW00001** | **예수금상세현황요청** | **프로젝트 사용** (D+2 잔고) |
| OPW00004 | 계좌평가현황요청 | 거래소구분 지원 |
| OPW00005 | 체결잔고요청 | 거래소구분 지원 |
| OPW00007 | 계좌별주문체결내역상세요청 | 거래소구분 지원 |
| OPW00009 | 계좌별주문체결현황요청 | 거래소구분 지원 |
| OPW00011 | 증거금율별주문가능수량조회요청 | 주문가능수량 계산 |
| **OPW00015** | **위탁종합거래내역요청** | **프로젝트 사용** (부분구현) 거래소구분 지원 |
| **OPW00018** | **계좌평가잔고내역요청** | **프로젝트 사용** (보유종목) 거래소구분 지원 |
| OPW10001~OPW10004 | (기타 계좌) | - |
| OPW20001~OPW20017 | (기타 계좌) | - |

### 특수 TR

| TR 코드 | 용도 |
|---------|------|
| OPTKWFID | 복수종목정보요청 (CommKwRqData 전용, CommRqData 불가) |
| OPTKWINV | (기타) |
| OPTKWPRO | (기타) |

---

## 4. 프로젝트 사용 TR 상세 스펙

### OPT10081 — 주식 일봉차트

**입력**
```python
SetInputValue("종목코드",    "005930")
SetInputValue("기준일자",    "20240101")  # YYYYMMDD
SetInputValue("수정주가구분", "1")         # 1=수정주가
```

**출력 (multi-row, 최대 600건/요청)**

| 필드명 | 설명 |
|--------|------|
| 일자 | YYYYMMDD |
| 시가 / 고가 / 저가 / 현재가 | OHLC (앞에 부호 붙을 수 있음) |
| 거래량 | - |

**화면번호**: `"0101"` | **페이지네이션**: ✅ (collector 모드만)  
**py_gubun 분기**: trader → `_opt10081()`, collector → `collector_opt10081()`

---

### OPT10080 — 주식 분봉차트

**입력**
```python
SetInputValue("종목코드",    "005930")
SetInputValue("틱범위",      "1")   # 1분봉
SetInputValue("수정주가구분", "1")
```

**출력 (multi-row)**

| 필드명 | 설명 |
|--------|------|
| 체결시간 | HHMMss |
| 시가 / 고가 / 저가 / 현재가 | OHLC |
| 거래량 | - |

**화면번호**: `"1999"` | **활성화 여부**: `cf.use_min_crawler`

---

### OPT20006 — 업종(지수) 일봉차트

**입력**
```python
SetInputValue("업종코드",    "001")  # KOSPI=001, KOSDAQ=101
SetInputValue("기준일자",    "20240101")
SetInputValue("수정주가구분", "1")
```

**출력**: OPT10081과 동일 (일자/시가/고가/저가/현재가/거래량)

**화면번호**: `"0102"` | **저장 DB**: `daily_craw.kospi_index` / `daily_craw.kosdaq_index`

---

### OPT10001 — 주식 기본정보 (펀더멘털)

**입력**
```python
SetInputValue("종목코드", "005930")
```

**출력 (single-row)**

| 필드명 | 필드명 |
|--------|--------|
| PER | BPS |
| EPS | 매출액 |
| ROE | 영업이익 |
| PBR | 당기순이익 |
| EV | 시가총액 |
| 외인소진률 | 신용비율 |
| 250최고가대비율 | 250최저가대비율 |
| 유통주식 | 유통비율 |

**화면번호**: `"0103"` | **저장**: `self.fundamental_data` → `daily_buy_list.sf_YYYYMMDD`

---

### OPT10073 — 일자별 종목별 실현손익

**입력**
```python
SetInputValue("계좌번호", cf.account_num)
SetInputValue("시작일자", today_str)
SetInputValue("종료일자", today_str)
```

**출력 (multi-row)**

| 필드명 | 설명 |
|--------|------|
| 일자 | YYYYMMDD |
| 종목코드 / 종목명 | - |
| 체결량 | - |
| 당일매도손익 | 실현손익 (원) |
| 손익율 | % |

**화면번호**: `"0328"` | **페이지네이션**: ✅

---

### OPT10074 — 당일 매매 현황

**입력**
```python
SetInputValue("계좌번호", cf.account_num)
SetInputValue("시작일자", "20170101")  # 고정
SetInputValue("종료일자", today_str)
```

**출력 (single-row)**

| 필드명 | 저장 변수 |
|--------|-----------|
| 실현손익 | `self.total_profit` |
| 당일매도손익 | `self.today_profit` |

**화면번호**: `"0329"` | **페이지네이션**: ✅

---

### OPT10076 — 체결/미체결 조회

**입력**
```python
SetInputValue("종목코드", "")          # 빈 문자열 = 전체 조회
SetInputValue("조회구분", "0")         # 0=전체
SetInputValue("계좌번호", cf.account_num)
```

**출력 (multi-row)**

| 필드명 | 설명 |
|--------|------|
| 주문번호 | - |
| 종목명 | - |
| 주문구분 | `"+매수"` / `"-매도"` |
| 주문가격 / 주문수량 | - |
| 체결가 / 체결량 | - |
| 미체결수량 | 0이면 완전체결 |
| 주문상태 | 접수/체결/확인 |
| 주문시간 | HHMMss |
| 원주문번호 | 정정/취소 원주문 |

**화면번호**: `"0350"` | **저장**: `self._data`

---

### OPW00001 — 예수금 / D+2 잔고

**입력**
```python
SetInputValue("계좌번호",          cf.account_num)
SetInputValue("비밀번호",          "")
SetInputValue("비밀번호입력매체구분", "00")
SetInputValue("조회구분",          "2")  # 1=추정, 2=일반
```

**출력 (single-row)**

| 필드명 | 저장 변수 |
|--------|-----------|
| d+2출금가능금액 | `self.d2_deposit` |
| 주문가능금액 | (필요시 추가 가능) |

**화면번호**: `"2000"`

---

### OPW00018 — 계좌 평가잔고 / 보유종목

**입력**
```python
SetInputValue("계좌번호",          cf.account_num)
SetInputValue("비밀번호",          "")
SetInputValue("비밀번호입력매체구분", "00")
SetInputValue("조회구분",          "1")  # 1=조회, 2=재조회
```

**출력 (single-row)** — 계좌 합계

| 필드명 |
|--------|
| 총매입금액 / 총평가금액 / 총평가손익금액 / 총수익률(%) / 추정예탁자산 |

**출력 (multi-row)** — 종목별

| 필드명 |
|--------|
| 종목번호(코드) / 종목명 / 보유수량 / 매입가 / 현재가 / 평가손익 / 수익률(%) / 매입금액 |

**화면번호**: `"2000"` | **페이지네이션**: ✅  
**저장**: `self.opw00018_output = {'single': [...], 'multi': [...]}`

---

## 5. OnReceiveChejanData FID 목록

`gubun == "0"` (접수/체결) 시 사용하는 주요 FID:

| FID | 항목 | FID | 항목 |
|-----|------|-----|------|
| **9201** | 계좌번호 | **910** | 체결가 |
| **9203** | 주문번호 | **911** | 체결량 |
| **9001** | 종목코드 | **914** | 단위체결가 |
| **302** | 종목명 | **915** | 단위체결량 |
| **913** | 주문상태 (접수/체결/확인) | **919** | 거부사유 |
| **900** | 주문수량 | **920** | 화면번호 |
| **901** | 주문가격 | **905** | 주문구분 |
| **902** | 미체결수량 | **906** | 매매구분 |
| **903** | 체결누계금액 | **907** | 매도수구분 |
| **904** | 원주문번호 | **908** | 주문/체결시간 |
| **10** | 현재가 | **909** | 체결번호 |
| **27** | 최우선매도호가 | **917** | 신용구분 |
| **28** | 최우선매수호가 | **916** | 대출일 |

`gubun == "1"` (잔고변경) 시 추가 FID:

| FID | 항목 | FID | 항목 |
|-----|------|-----|------|
| **930** | 보유수량 | **945** | 당일순매수수량 |
| **931** | 매입단가 | **950** | 당일총매도손익 |
| **932** | 총매입가 | **990** | 당일실현손익(유가) |
| **933** | 주문가능수량 | **991** | 당일실현손익률(유가) |
| **307** | 기준가 | **992** | 당일실현손익(신용) |
| **8019** | 손익율 | **993** | 당일실현손익률(신용) |
| **305** | 상한가 | **306** | 하한가 |

---

## 6. 주문 관련 상수

### 주문유형 (SendOrder nOrderType)

| 값 | 의미 | 값 | 의미 |
|----|------|----|------|
| **1** | 신규매수 | **2** | 신규매도 |
| **3** | 매수취소 | **4** | 매도취소 |
| **5** | 매수정정 | **6** | 매도정정 |
| 11 | SOR매수 | 12 | SOR매도 |
| 13 | SOR취소 | 15 | SOR정정 |
| 21 | NXT매수 | 22 | NXT매도 |
| 23 | NXT취소 | 25 | NXT정정 |

### 거래구분 / 호가구분 (sHogaGb)

| 값 | 의미 | 값 | 의미 |
|----|----|----|----|
| **"00"** | 지정가 | **"03"** | 시장가 (가격 0 입력) |
| "05" | 조건부지정가 | "06" | 최유리지정가 |
| "07" | 최우선지정가 | "10" | 지정가IOC |
| "13" | 시장가IOC | "16" | 최유리IOC |
| "20" | 지정가FOK | "23" | 시장가FOK |
| "26" | 최유리FOK | "28" | 스탑지정가 |
| "29" | 중간가 | "61" | 장전시간외종가 |
| "62" | 시간외단일가 | "81" | 장후시간외종가 |

> 모의투자에서는 `"00"` (지정가) 와 `"03"` (시장가) 만 사용 가능

### 정규장 외 주문 시간

| 구분 | 시간 | 거래구분 |
|------|------|---------|
| 장전 동시호가 | 08:30~09:00 | 00 또는 03 |
| 장전시간외종가 | 08:30~08:40 | 61, 가격 0 |
| 장마감 동시호가 | 15:20~15:30 | 00 또는 03 |
| 장후시간외종가 | 15:40~16:00 | 81, 가격 0 |
| 시간외단일가 | 16:00~18:00 | 62, 가격 입력 (10분 단위 체결) |

---

## 7. 에러 코드

| 코드 | 의미 |
|------|------|
| 0 또는 1 | 정상 |
| **-200** | **시세조회 과부하** (1초 5회 초과) |
| -201 | 전문작성 초기화 실패 |
| -202 | 전문작성 입력값 오류 |
| **-203** | **데이터 없음** |
| -204 | 조회 가능 종목수 초과 (최대 100종목) |
| -205 | 데이터 수신 실패 |
| -206 | 조회 가능 FID수 초과 (최대 100개) |
| -209 | 시세조회제한 |
| -300 | 입력값 오류 |
| -301 | 계좌비밀번호 없음 |
| -302 | 타인계좌 사용오류 |
| **-308** | **주문전송 과부하** (1초 5회 초과) |
| -340 | 계좌정보 없음 |
| -500 | 종목코드 없음 |
| -100 | 사용자정보교환 실패 (로그인) |
| -101 | 서버 접속 실패 |
| -102 | 버전처리 실패 |

---

## 8. 속도 제한 & 주의사항

### 속도 제한

| 구분 | 제한 | 대상 함수 |
|------|------|---------|
| 조회 | **1초당 5회** | CommRqData, CommKwRqData, SendCondition |
| 주문 | **1초당 5회** | SendOrder, SendOrderFO, SendOrderCredit |
| 조건검색 | 1분당 1회 (동일 조건식) | SendCondition |

- 조회와 주문은 **별개**로 카운트됨
- 장시간 1초 5회 유지하면 서버부하방지 제한 걸릴 수 있음 → `cf.TR_REQ_TIME_INTERVAL = 0.3` 유지
- 제한 걸리면 `-200` 리턴 → 1초 후 자동 해제

### 화면번호 규칙

- 4자리 숫자 문자열 사용 (`"0101"` ~ `"9999"`, `"0000"` 제외)
- 프로그램 전체에서 **최대 200개** 화면번호 사용 가능
- 같은 화면번호로 **빠르게 반복 요청 금지** → 데이터 유효성 보장 안 됨
- 화면번호에 실시간이 등록된 상태에서 같은 번호로 다른 TR 요청 시 실시간 자동 해제됨

### 프로젝트 화면번호 할당

| 화면번호 | 용도 |
|----------|------|
| `"0101"` | OPT10081 — 주식 일봉 |
| `"0102"` | OPT20006 — 지수 일봉 |
| `"0103"` | OPT10001 — 펀더멘털 |
| `"0328"` | OPT10073 — 종목별 실현손익 |
| `"0329"` | OPT10074 — 당일 매매 현황 |
| `"0350"` | OPT10076 — 체결/미체결 조회 |
| `"1999"` | OPT10080 — 분봉 |
| `"2000"` | OPW00001, OPW00018 — 계좌 조회 |

> 새 TR 추가 시 위 목록에 없는 번호 사용. 범위 `"0200"` ~ `"1998"` 권장.

### 데이터 처리 주의

- **현재가 부호**: `"+005930"` → 색상 구분용. `abs(int(value.strip()))` 처리
- **종목코드 앞 문자**: `A`=장내주식, `J`=ELW, `Q`=ETN → 6자리 초과 시 앞 잘라냄
- **연속조회 중단 주의**: 연속조회 중간에 다른 TR 요청 시 연속조회 끊김
- **비밀번호 입력**: TR 조회 시 `SetInputValue("비밀번호", "")` 공백으로 입력
- **차트 최대 건수**: OPT10081 한 번에 최대 600건

---

## 9. 기타 유틸리티 함수

```python
# 시장구분별 종목코드 리스트
GetCodeListByMarket("0")   # 코스피
GetCodeListByMarket("10")  # 코스닥
GetCodeListByMarket("8")   # ETF
GetCodeListByMarket("3")   # ELW
# 반환: "005930;000660;035420;..." (';' 구분)

# 종목 정보
GetMasterCodeName(code)          # 종목명
GetMasterListedStockCnt(code)    # 상장주식수 (overflow 위험 → KOA_Functions 사용 권장)
GetMasterListedStockDate(code)   # 상장일
GetMasterLastPrice(code)         # 당일 기준가
GetMasterStockState(code)        # 증거금비율/거래정지/관리종목 등
GetBranchCodeName()              # 회원사 코드/이름 목록

# KOA_Functions 활용
KOA_Functions("ShowAccountWindow", "")           # 계좌비밀번호 입력창
KOA_Functions("GetServerGubun", "")             # "1"=모의투자, else=실서버
KOA_Functions("GetMasterStockInfo", "005930")   # 시장구분|중분류|업종구분
KOA_Functions("GetStockMarketKind", "005930")   # "0"=코스피, "10"=코스닥
KOA_Functions("IsOrderWarningStock", "005930")  # "0"=해당없음, "2"=정리매매...
KOA_Functions("GetUpjongCode", "0")             # 업종코드 목록 (0=코스피)
KOA_Functions("GetThemeGroupList", "0")         # 테마그룹 목록
KOA_Functions("GetMasterListedStockCntEx", code) # 상장주식수 (overflow 안전)

# 대체거래소(NXT) 종목코드
# KRX:  "005930"
# NXT:  "005930_NX"
# 통합: "005930_AL"
```

---

*작성: 2026-06-05 / 소스: `docs/키움 OpenAPI.txt` + hyunsoft.tistory.com/entry/trCodeList*
