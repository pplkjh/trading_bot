# -*- coding: utf-8 -*-
"""
실전 투자 운용보고서 — Excel 자동 생성기

- jackbot4_imi1 all_item_db 데이터 기반
- 매도/매수 체결 후 generate_async() 호출 → 백그라운드 업데이트
- scripts/generate_report.py 로 수동 생성 가능

시트 구성:
  1. 📊 요약        — 핵심 KPI 한눈에
  2. 📅 일자별      — 날짜별 매수/매도 건수·실현손익·누적손익
  3. 📋 거래내역    — 전 거래 상세 (매수·매도·보유중 전부)
  4. 💼 보유현황    — 현재 보유 종목
  5. ⚡ 전략 비교   — Strategy A vs B 지표 비교
"""

import logging
import pathlib
import datetime
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

REPORT_DIR = pathlib.Path(__file__).parent.parent / 'reports'

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False
    logger.warning("openpyxl 미설치 — 투자보고서 기능 비활성화 (pip install openpyxl)")


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def _parse_date(s):
    """YYYYMMDD → datetime.date | '0'/''/None → None"""
    if not s or str(s).strip() in ('0', ''):
        return None
    try:
        s = str(s).strip()[:8]
        return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except Exception:
        return None


def _hold_days(buy_date_str, sell_date_str):
    """보유기간 (일). 보유중이면 오늘까지."""
    bd = _parse_date(buy_date_str)
    if not bd:
        return 0
    sd = _parse_date(sell_date_str)
    end = sd if sd else datetime.date.today()
    return max(0, (end - bd).days)


def _fmt_date(s):
    """YYYYMMDD → 'YYYY-MM-DD' | None → ''"""
    d = _parse_date(s)
    return d.strftime('%Y-%m-%d') if d else ''


def _f(val, default=0):
    """안전한 float 변환"""
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _i(val, default=0):
    """안전한 int 변환"""
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


# ─── 스타일 상수 ──────────────────────────────────────────────────────────────

class _S:
    """Excel 스타일 팩토리"""

    @staticmethod
    def font(bold=False, color='000000', size=9, name='맑은 고딕'):
        return Font(name=name, bold=bold, color=color, size=size)

    @staticmethod
    def fill(hex_color):
        return PatternFill('solid', fgColor=hex_color)

    @staticmethod
    def align(h='center', v='center', wrap=False):
        return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

    @staticmethod
    def border(color='BDD7EE', style='thin'):
        side = Side(style=style, color=color)
        return Border(left=side, right=side, top=side, bottom=side)

    # 미리 선언한 공통 스타일
    FT_HDR   = Font(name='맑은 고딕', bold=True,  color='FFFFFF', size=9)
    FT_BOLD  = Font(name='맑은 고딕', bold=True,  color='1F3864', size=9)
    FT_NRM   = Font(name='맑은 고딕', bold=False, color='1F3864', size=9)
    FT_PROF  = Font(name='맑은 고딕', bold=True,  color='375623', size=9)
    FT_LOSS  = Font(name='맑은 고딕', bold=True,  color='9C0006', size=9)
    FT_HOLD  = Font(name='맑은 고딕', bold=False, color='7F6000', size=9)
    FT_TITLE = Font(name='맑은 고딕', bold=True,  color='1F3864', size=12)

    FILL_HDR   = PatternFill('solid', fgColor='1F497D')
    FILL_HDR2  = PatternFill('solid', fgColor='4472C4')
    FILL_HDR3  = PatternFill('solid', fgColor='2E75B6')
    FILL_PROF  = PatternFill('solid', fgColor='E2EFDA')
    FILL_LOSS  = PatternFill('solid', fgColor='FCE4D6')
    FILL_HOLD  = PatternFill('solid', fgColor='FFF2CC')
    FILL_ALT   = PatternFill('solid', fgColor='EEF4FF')
    FILL_TOT   = PatternFill('solid', fgColor='D9E1F2')
    FILL_TITLE = PatternFill('solid', fgColor='DEEAF1')
    FILL_A     = PatternFill('solid', fgColor='DEEAF1')
    FILL_B     = PatternFill('solid', fgColor='FFF2CC')
    FILL_WHITE = PatternFill('solid', fgColor='FFFFFF')

    AL_C  = Alignment(horizontal='center', vertical='center')
    AL_L  = Alignment(horizontal='left',   vertical='center')
    AL_R  = Alignment(horizontal='right',  vertical='center')

    BD    = Border(
        left=Side(style='thin', color='BDD7EE'),
        right=Side(style='thin', color='BDD7EE'),
        top=Side(style='thin', color='BDD7EE'),
        bottom=Side(style='thin', color='BDD7EE'),
    )


# ─── 메인 클래스 ──────────────────────────────────────────────────────────────

class InvestmentReport:
    """실전 투자 운용보고서 Excel 자동 생성기"""

    REPORT_FILE = REPORT_DIR / '투자운용보고서.xlsx'

    def __init__(self, engine_jb):
        self.engine_jb = engine_jb
        REPORT_DIR.mkdir(exist_ok=True)

    # ─── Public API ───────────────────────────────────────────────────────────

    def generate_async(self):
        """별도 스레드에서 비동기 생성 — 트레이딩 메인 스레드 차단 없음"""
        t = threading.Thread(target=self._safe_generate, daemon=True, name='ReportWriter')
        t.start()

    def generate(self):
        """동기 생성 — 완료까지 블로킹 (스탠드얼론 스크립트용)"""
        if not OPENPYXL_OK:
            print("❌ openpyxl 미설치: pip install openpyxl")
            return None
        return self._build()

    def ensure_exit_reason_column(self):
        """exit_reason 컬럼이 없으면 추가 (최초 1회 마이그레이션)"""
        try:
            self.engine_jb.execute(
                "ALTER TABLE all_item_db "
                "ADD COLUMN exit_reason VARCHAR(100) DEFAULT NULL COMMENT '매도사유'"
            )
            logger.info("all_item_db.exit_reason 컬럼 추가 완료")
            print("✅ all_item_db.exit_reason 컬럼 추가 완료")
        except Exception:
            pass  # 이미 존재

    # ─── Private ──────────────────────────────────────────────────────────────

    def _safe_generate(self):
        try:
            self._build()
        except Exception as e:
            logger.warning(f"투자보고서 생성 실패 (무시): {e}")

    def _build(self):
        trades = self._fetch_trades()
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        self._sheet_summary(wb, trades)
        self._sheet_daily(wb, trades)
        self._sheet_trades(wb, trades)
        self._sheet_holding(wb, trades)
        self._sheet_strategy(wb, trades)

        path = self._save(wb)
        return path

    def _save(self, wb):
        """저장. 파일 잠금 시 타임스탬프 붙인 대체 파일로 저장."""
        try:
            wb.save(str(self.REPORT_FILE))
            logger.info(f"✅ 투자보고서 저장: {self.REPORT_FILE}")
            return self.REPORT_FILE
        except PermissionError:
            ts  = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            alt = REPORT_DIR / f'투자운용보고서_{ts}.xlsx'
            wb.save(str(alt))
            logger.warning(f"⚠️ 파일 열림 — 대체 저장: {alt.name}")
            return alt

    def _fetch_trades(self):
        """all_item_db 전체 조회 (SELECT * 사용 — 컬럼 존재 여부 무관)"""
        try:
            rows = self.engine_jb.execute(
                "SELECT * FROM all_item_db ORDER BY buy_date DESC, buy_time DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"거래내역 조회 실패: {e}")
            return []

    # ─── 헬퍼 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _is_holding(t):
        sd = str(t.get('sell_date', '0') or '0').strip()
        return sd in ('0', '')

    @staticmethod
    def _set_hdr(ws, row, col, text, fill=None, width=None, height=None):
        """헤더 셀 일괄 스타일 적용"""
        c = ws.cell(row=row, column=col, value=text)
        c.font = _S.FT_HDR
        c.fill = fill or _S.FILL_HDR
        c.alignment = _S.AL_C
        c.border = _S.BD
        if width is not None:
            ws.column_dimensions[get_column_letter(col)].width = width
        if height is not None:
            ws.row_dimensions[row].height = height
        return c

    @staticmethod
    def _set_cell(ws, row, col, value, font=None, fill=None, align=None):
        c = ws.cell(row=row, column=col, value=value)
        if font:  c.font      = font
        if fill:  c.fill      = fill
        if align: c.alignment = align
        c.border = _S.BD
        return c

    # ─── Sheet 1: 요약 ────────────────────────────────────────────────────────

    def _sheet_summary(self, wb, trades):
        ws = wb.create_sheet('📊 요약')
        ws.sheet_view.showGridLines = False

        # 컬럼 너비
        for col, w in zip('ABCDE', [2, 22, 16, 22, 16]):
            ws.column_dimensions[col].width = w

        # ── 제목 ──
        ws.merge_cells('B2:E2')
        c = ws['B2']
        c.value = f"🏦  투자 운용보고서  —  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} 기준"
        c.font  = _S.FT_TITLE
        c.fill  = _S.FILL_TITLE
        c.alignment = _S.AL_C
        c.border = _S.BD
        ws.row_dimensions[2].height = 32

        completed = [t for t in trades if not self._is_holding(t)]
        holding   = [t for t in trades if     self._is_holding(t)]

        # ── 지표 계산 ──
        total   = len(completed)
        wins    = [_f(t.get('sell_rate')) for t in completed if _f(t.get('sell_rate')) >= 0]
        losses  = [_f(t.get('sell_rate')) for t in completed if _f(t.get('sell_rate')) <  0]
        all_ret = [_f(t.get('sell_rate')) for t in completed]
        wr      = len(wins) / total * 100 if total else 0
        avg_w   = sum(wins)   / len(wins)   if wins   else 0
        avg_l   = sum(losses) / len(losses) if losses else 0
        avg_r   = sum(all_ret)/ total       if total  else 0
        r_ratio = abs(avg_w / avg_l) if avg_l != 0 else 0
        total_profit = sum(_i(t.get('realized_profit')) for t in completed)
        hold_days_list = [_hold_days(t.get('buy_date'), t.get('sell_date')) for t in completed]
        avg_hold = sum(hold_days_list) / len(hold_days_list) if hold_days_list else 0

        # ── 섹션 1: 전체 현황 ──
        sections = [
            # (label_left, val_left, label_right, val_right)
            ('─── 💹 전체 거래 현황', None, '─── 📈 수익 지표', None),
            ('총 매도 완료 건수',  f"{total:,} 건",        '평균 수익률',    f"{avg_r:+.2f}%"),
            ('현재 보유 종목',     f"{len(holding):,} 종목", '평균 익절률',  f"{avg_w:+.2f}%"),
            ('승률',              f"{wr:.1f}%",             '평균 손절률',   f"{avg_l:+.2f}%"),
            ('평균 보유기간',      f"{avg_hold:.1f} 일",    '손익비 (R)',    f"{r_ratio:.2f}"),
            ('총 실현손익',        f"{total_profit:+,.0f} 원", ' ', ''),
        ]

        row = 4
        for ll, vl, lr, vr in sections:
            is_hdr = vl is None
            ws.row_dimensions[row].height = 22

            if is_hdr:
                # 섹션 헤더
                for merge_range, txt, fill in [
                    (f'B{row}:C{row}', ll, _S.FILL_HDR),
                    (f'D{row}:E{row}', lr, _S.FILL_HDR2),
                ]:
                    ws.merge_cells(merge_range)
                    start_col = merge_range[0]
                    c = ws[f'{start_col}{row}']
                    c.value = txt
                    c.font  = _S.FT_HDR
                    c.fill  = fill
                    c.alignment = _S.AL_C
                    c.border = _S.BD
            else:
                fill_row = _S.FILL_ALT if row % 2 == 0 else _S.FILL_WHITE
                for col_l, col_v, txt, is_val in [
                    ('B', 'C', ll, False), ('C', None, vl,  True),
                    ('D', 'E', lr, False), ('E', None, vr,  True),
                ]:
                    if col_v is None:
                        continue
                    c = ws.cell(row=row, column=ord(col_l)-64, value=txt)
                    c.font  = _S.FT_BOLD if not is_val else _S.FT_NRM
                    c.fill  = fill_row
                    c.alignment = _S.AL_R if is_val else _S.AL_L
                    c.border = _S.BD
                # val cells
                for col_let, val in [('C', vl), ('E', vr)]:
                    c = ws[f'{col_let}{row}']
                    c.value = val
                    c.font  = _S.FT_NRM
                    c.fill  = fill_row
                    c.alignment = _S.AL_R
                    c.border = _S.BD
            row += 1

        # ── 섹션 2: 전략별 미니 비교표 ──
        row += 1
        ws.row_dimensions[row].height = 24
        ws.merge_cells(f'B{row}:E{row}')
        c = ws[f'B{row}']
        c.value = '⚡  전략별 성과 요약'
        c.font  = _S.FT_HDR
        c.fill  = _S.FILL_HDR3
        c.alignment = _S.AL_C
        c.border = _S.BD
        row += 1

        sub_hdrs = ['전략', '거래수', '승률', '평균수익률', '평균보유']
        for i, (col, hdr) in enumerate(zip('BCDE' + ('E',), sub_hdrs)):
            actual_col = i + 2  # B=2
            c = ws.cell(row=row, column=actual_col, value=hdr)
            c.font  = _S.FT_HDR
            c.fill  = PatternFill('solid', fgColor='5B9BD5')
            c.alignment = _S.AL_C
            c.border = _S.BD
            if i == 4:  # 5번째 컬럼 E
                ws.column_dimensions['F'].width = 12
        ws.row_dimensions[row].height = 20
        row += 1

        strat_fills = {'A': _S.FILL_A, 'B': _S.FILL_B}
        for strat in ['A', 'B']:
            st = [t for t in completed if t.get('strategy_type') == strat]
            if not st:
                continue
            sw = [_f(t.get('sell_rate')) for t in st if _f(t.get('sell_rate')) >= 0]
            swr = len(sw) / len(st) * 100
            savg = sum(_f(t.get('sell_rate')) for t in st) / len(st)
            shd  = sum(_hold_days(t.get('buy_date'), t.get('sell_date')) for t in st) / len(st)
            sfil = strat_fills.get(strat, _S.FILL_WHITE)
            for ci, val in enumerate([f'전략 {strat}', len(st), f'{swr:.1f}%',
                                       f'{savg:+.2f}%', f'{shd:.1f}일'], 2):
                c = ws.cell(row=row, column=ci, value=val)
                c.font = _S.FT_NRM
                c.fill = sfil
                c.alignment = _S.AL_C
                c.border = _S.BD
            ws.row_dimensions[row].height = 20
            row += 1

    # ─── Sheet 2: 일자별 요약 ─────────────────────────────────────────────────

    def _sheet_daily(self, wb, trades):
        ws = wb.create_sheet('📅 일자별')
        ws.freeze_panes = 'A2'
        ws.sheet_view.showGridLines = False

        headers = [
            ('날짜',      11), ('매수 건수', 8), ('매도 건수', 8),
            ('승리',       6), ('패배',      6), ('승률',      7),
            ('평균수익률', 10), ('당일 실현손익', 14), ('누적 실현손익', 14),
        ]
        for i, (hdr, w) in enumerate(headers, 1):
            self._set_hdr(ws, 1, i, hdr, width=w, height=22)

        # sell_date 기준 집계
        sell_day  = defaultdict(lambda: {'cnt': 0, 'wins': 0, 'sum_ret': 0.0, 'realized': 0})
        buy_day   = defaultdict(int)

        for t in trades:
            bd = str(t.get('buy_date', '') or '').strip()
            if bd and bd != '0':
                buy_day[bd] += 1

            if not self._is_holding(t):
                sd  = str(t.get('sell_date', '') or '').strip()
                ret = _f(t.get('sell_rate'))
                rl  = _i(t.get('realized_profit'))
                sell_day[sd]['cnt']      += 1
                sell_day[sd]['sum_ret']  += ret
                sell_day[sd]['realized'] += rl
                if ret >= 0:
                    sell_day[sd]['wins'] += 1

        dates = sorted(sell_day.keys(), reverse=True)
        cumulative = 0
        for r, d in enumerate(dates, 2):
            info = sell_day[d]
            cnt  = info['cnt']
            wins = info['wins']
            loss = cnt - wins
            wr   = wins / cnt * 100 if cnt else 0
            avg  = info['sum_ret'] / cnt if cnt else 0
            rl   = info['realized']
            cumulative += rl

            is_pos = rl >= 0
            fill = (PatternFill('solid', fgColor='E8F4E8') if is_pos
                    else PatternFill('solid', fgColor='FAE0D8')) if r % 2 == 0 else \
                   (PatternFill('solid', fgColor='D5EDDA') if is_pos
                    else PatternFill('solid', fgColor='F9D6CE'))

            row_vals = [
                _fmt_date(d),
                buy_day.get(d, 0),
                cnt,
                wins,
                loss,
                f'{wr:.1f}%',
                f'{avg:+.2f}%',
                rl,
                cumulative,
            ]
            for ci, val in enumerate(row_vals, 1):
                c = ws.cell(row=r, column=ci, value=val)
                c.font = (_S.FT_PROF if is_pos else _S.FT_LOSS) if ci >= 8 else _S.FT_NRM
                c.fill = fill
                c.alignment = _S.AL_C if ci == 1 else _S.AL_R
                c.border = _S.BD
            ws.row_dimensions[r].height = 18

        # 합계 행
        if dates:
            r = len(dates) + 2
            all_cnt  = sum(sell_day[d]['cnt']      for d in dates)
            all_wins = sum(sell_day[d]['wins']      for d in dates)
            all_ret  = sum(sell_day[d]['sum_ret']   for d in dates)
            all_rl   = sum(sell_day[d]['realized']  for d in dates)
            all_wr   = all_wins / all_cnt * 100 if all_cnt else 0
            all_avg  = all_ret / all_cnt           if all_cnt else 0

            for ci, val in enumerate(['합 계', '', all_cnt, all_wins, all_cnt - all_wins,
                                       f'{all_wr:.1f}%', f'{all_avg:+.2f}%',
                                       all_rl, all_rl], 1):
                c = ws.cell(row=r, column=ci, value=val)
                c.font = _S.FT_BOLD
                c.fill = _S.FILL_TOT
                c.alignment = _S.AL_C if ci == 1 else _S.AL_R
                c.border = _S.BD
            ws.row_dimensions[r].height = 22

    # ─── Sheet 3: 전체 거래내역 ───────────────────────────────────────────────

    def _sheet_trades(self, wb, trades):
        ws = wb.create_sheet('📋 거래내역')
        ws.freeze_panes = 'A2'
        ws.sheet_view.showGridLines = False

        headers = [
            ('#',         4),  ('전략',     6),  ('종목코드',  9),  ('종목명',   16),
            ('매수일',   11),  ('매수시간',  9),  ('매수가',   10),  ('수량',      7),
            ('매수금액', 13),  ('종합점수',  8),  ('A',         5),  ('B',         5),
            ('C',         5),  ('D',         5),  ('E',         5),  ('F',         5),
            ('상태',      8),
            ('매도일',   11),  ('매도시간',  9),  ('매도가',   10),
            ('매도사유', 16),  ('보유일',    6),  ('수익률',    8),  ('실현손익', 13),
        ]

        for i, (hdr, w) in enumerate(headers, 1):
            self._set_hdr(ws, 1, i, hdr, width=w, height=22)

        for r, t in enumerate(trades, 2):
            holding = self._is_holding(t)
            rate    = _f(t.get('sell_rate'))
            bd      = _parse_date(t.get('buy_date'))
            sd      = _parse_date(t.get('sell_date'))
            hd      = _hold_days(t.get('buy_date'), t.get('sell_date'))

            # 행 배경
            if holding:
                fill = _S.FILL_HOLD
                ft   = _S.FT_HOLD
            elif rate >= 0:
                fill = _S.FILL_PROF
                ft   = _S.FT_PROF
            else:
                fill = _S.FILL_LOSS
                ft   = _S.FT_LOSS

            row_vals = [
                r - 1,                                              # #
                t.get('strategy_type', ''),                         # 전략
                str(t.get('code', '')),                             # 종목코드
                str(t.get('code_name', '')),                        # 종목명
                bd.strftime('%Y-%m-%d') if bd else '',              # 매수일
                str(t.get('buy_time', '') or ''),                   # 매수시간
                _i(t.get('purchase_price')),                        # 매수가
                _i(t.get('holding_amount')),                        # 수량
                _i(t.get('item_total_purchase')),                   # 매수금액
                _f(t.get('composite_score')),                       # 종합점수
                _f(t.get('score_a')),                               # A
                _f(t.get('score_b')),                               # B
                _f(t.get('score_c')),                               # C
                _f(t.get('score_d')),                               # D
                _f(t.get('score_e')),                               # E
                _f(t.get('score_f')),                               # F
                '보유중' if holding else '매도완료',                 # 상태
                sd.strftime('%Y-%m-%d') if sd else '',              # 매도일
                str(t.get('sell_time', '') or '') if not holding else '',  # 매도시간
                _i(t.get('sell_price')) if not holding else '',     # 매도가
                str(t.get('exit_reason', '') or '') if not holding else '',  # 매도사유
                hd,                                                 # 보유일
                rate if not holding else '',                        # 수익률
                _i(t.get('realized_profit')) if not holding else '',  # 실현손익
            ]

            aligns = [
                _S.AL_C, _S.AL_C, _S.AL_C, _S.AL_L,   # #, 전략, 코드, 이름
                _S.AL_C, _S.AL_C, _S.AL_R, _S.AL_R,   # 매수일, 시간, 가, 수량
                _S.AL_R, _S.AL_R, _S.AL_R, _S.AL_R,   # 매수금액, 종합, A, B
                _S.AL_R, _S.AL_R, _S.AL_R, _S.AL_R,   # C, D, E, F
                _S.AL_C,                                # 상태
                _S.AL_C, _S.AL_C, _S.AL_R,             # 매도일, 시간, 가
                _S.AL_L, _S.AL_C, _S.AL_R, _S.AL_R,   # 사유, 보유일, 수익률, 실현손익
            ]

            for ci, (val, al) in enumerate(zip(row_vals, aligns), 1):
                c = ws.cell(row=r, column=ci, value=val)
                c.font      = ft
                c.fill      = fill
                c.alignment = al
                c.border    = _S.BD

                # 수익률 컬럼만 별도 색상
                if ci == 23 and not holding:
                    c.font = _S.FT_PROF if rate >= 0 else _S.FT_LOSS

            ws.row_dimensions[r].height = 18

    # ─── Sheet 4: 보유현황 ────────────────────────────────────────────────────

    def _sheet_holding(self, wb, trades):
        ws = wb.create_sheet('💼 보유현황')
        ws.freeze_panes = 'A2'
        ws.sheet_view.showGridLines = False

        holding = [t for t in trades if self._is_holding(t)]

        headers = [
            ('#',         4), ('전략',     6), ('종목코드',  9), ('종목명',   16),
            ('매수일',   11), ('매수가',  10), ('수량',      7), ('매수금액', 13),
            ('종합점수',  8), ('보유기간', 8), ('D+1변동%',  9), ('RSI14',    7),
        ]
        hdr_fill = PatternFill('solid', fgColor='7F6000')
        for i, (hdr, w) in enumerate(headers, 1):
            self._set_hdr(ws, 1, i, hdr, fill=hdr_fill, width=w, height=22)

        if not holding:
            ws.merge_cells(f'A2:{get_column_letter(len(headers))}2')
            c = ws['A2']
            c.value = '현재 보유 종목 없음'
            c.font  = _S.FT_BOLD
            c.fill  = _S.FILL_HOLD
            c.alignment = _S.AL_C
            ws.row_dimensions[2].height = 24
            return

        for r, t in enumerate(holding, 2):
            bd  = _parse_date(t.get('buy_date'))
            hd  = _hold_days(t.get('buy_date'), t.get('sell_date'))
            fill = _S.FILL_HOLD if r % 2 == 0 else PatternFill('solid', fgColor='FFFACD')

            row_vals = [
                r - 1,
                t.get('strategy_type', ''),
                str(t.get('code', '')),
                str(t.get('code_name', '')),
                bd.strftime('%Y-%m-%d') if bd else '',
                _i(t.get('purchase_price')),
                _i(t.get('holding_amount')),
                _i(t.get('item_total_purchase')),
                _f(t.get('composite_score')),
                f'{hd}일',
                _f(t.get('d1_diff_rate')),
                _f(t.get('rsi14')),
            ]
            aligns = [_S.AL_C, _S.AL_C, _S.AL_C, _S.AL_L,
                      _S.AL_C, _S.AL_R,  _S.AL_R, _S.AL_R,
                      _S.AL_R, _S.AL_C,  _S.AL_R, _S.AL_R]

            for ci, (val, al) in enumerate(zip(row_vals, aligns), 1):
                c = ws.cell(row=r, column=ci, value=val)
                c.font      = _S.FT_HOLD
                c.fill      = fill
                c.alignment = al
                c.border    = _S.BD
            ws.row_dimensions[r].height = 18

    # ─── Sheet 5: 전략별 성과 비교 ────────────────────────────────────────────

    def _sheet_strategy(self, wb, trades):
        ws = wb.create_sheet('⚡ 전략 비교')
        ws.sheet_view.showGridLines = False
        ws.column_dimensions['A'].width = 2

        completed = [t for t in trades if not self._is_holding(t)]

        col_widths = [16, 8, 7, 10, 10, 8, 14, 8, 10]
        headers    = ['전략', '거래수', '승률', '평균익절', '평균손절',
                      '손익비R', '총 실현손익', '평균보유', '평균수익률']

        # 제목
        ws.merge_cells(f'B2:{get_column_letter(1+len(headers))}2')
        c = ws['B2']
        c.value = '⚡  전략별 성과 비교'
        c.font  = _S.FT_TITLE
        c.fill  = _S.FILL_TITLE
        c.alignment = _S.AL_C
        c.border = _S.BD
        ws.row_dimensions[2].height = 30

        for i, (hdr, w) in enumerate(zip(headers, col_widths), 2):
            ws.column_dimensions[get_column_letter(i)].width = w
            c = ws.cell(row=4, column=i, value=hdr)
            c.font      = _S.FT_HDR
            c.fill      = _S.FILL_HDR
            c.alignment = _S.AL_C
            c.border    = _S.BD
        ws.row_dimensions[4].height = 22

        strat_fills = {'A': _S.FILL_A, 'B': _S.FILL_B,
                       '전체': _S.FILL_TOT}
        r = 5
        for strat in ['A', 'B', '전체']:
            st = completed if strat == '전체' else [t for t in completed
                                                    if t.get('strategy_type') == strat]
            if not st:
                continue

            w_list = [_f(t.get('sell_rate')) for t in st if _f(t.get('sell_rate')) >= 0]
            l_list = [_f(t.get('sell_rate')) for t in st if _f(t.get('sell_rate')) <  0]
            total  = len(st)
            wr     = len(w_list) / total * 100 if total else 0
            avg_w  = sum(w_list) / len(w_list) if w_list else 0
            avg_l  = sum(l_list) / len(l_list) if l_list else 0
            r_rat  = abs(avg_w / avg_l) if avg_l != 0 else 0
            real   = sum(_i(t.get('realized_profit')) for t in st)
            avg_hd = sum(_hold_days(t.get('buy_date'), t.get('sell_date'))
                         for t in st) / total if total else 0
            avg_rt = sum(_f(t.get('sell_rate')) for t in st) / total if total else 0

            label  = f'전략 {strat}' if strat != '전체' else '전 체'
            fill   = strat_fills.get(strat, _S.FILL_WHITE)
            ft     = _S.FT_BOLD if strat == '전체' else _S.FT_NRM

            for ci, val in enumerate([label, total, f'{wr:.1f}%', f'{avg_w:+.2f}%',
                                       f'{avg_l:+.2f}%', f'{r_rat:.2f}',
                                       real, f'{avg_hd:.1f}일', f'{avg_rt:+.2f}%'], 2):
                c = ws.cell(row=r, column=ci, value=val)
                c.font      = ft
                c.fill      = fill
                c.alignment = _S.AL_C
                c.border    = _S.BD
            ws.row_dimensions[r].height = 22
            r += 1

        # ── 스코어 구간별 성과 미니표 ──
        r += 1
        ws.merge_cells(f'B{r}:{get_column_letter(1+len(headers))}{r}')
        c = ws[f'B{r}']
        c.value = '📊  종합점수 구간별 성과 (매도 완료 기준)'
        c.font  = _S.FT_HDR
        c.fill  = _S.FILL_HDR3
        c.alignment = _S.AL_C
        c.border = _S.BD
        ws.row_dimensions[r].height = 22
        r += 1

        score_hdrs = ['구간', '거래수', '승률', '평균익절', '평균손절', '손익비R', '평균수익률']
        for ci, hdr in enumerate(score_hdrs, 2):
            c = ws.cell(row=r, column=ci, value=hdr)
            c.font = _S.FT_HDR
            c.fill = PatternFill('solid', fgColor='5B9BD5')
            c.alignment = _S.AL_C
            c.border = _S.BD
        ws.row_dimensions[r].height = 20
        r += 1

        buckets = [(60, 70), (70, 80), (80, 90), (90, 100),
                   (100, 110), (110, 120), (120, 9999)]
        for lo, hi in buckets:
            subset = [t for t in completed
                      if lo <= _f(t.get('composite_score')) < hi]
            if not subset:
                continue
            sw = [_f(t.get('sell_rate')) for t in subset if _f(t.get('sell_rate')) >= 0]
            sl = [_f(t.get('sell_rate')) for t in subset if _f(t.get('sell_rate')) <  0]
            cnt = len(subset)
            swr = len(sw) / cnt * 100 if cnt else 0
            saw = sum(sw) / len(sw) if sw else 0
            sal = sum(sl) / len(sl) if sl else 0
            srr = abs(saw / sal) if sal != 0 else 0
            sav = sum(_f(t.get('sell_rate')) for t in subset) / cnt if cnt else 0

            label = f'{lo}~{hi-1}' if hi < 9999 else f'{lo}+'
            fill  = PatternFill('solid', fgColor='EEF4FF') if r % 2 == 0 else _S.FILL_WHITE

            for ci, val in enumerate([label, cnt, f'{swr:.1f}%',
                                       f'{saw:+.2f}%', f'{sal:+.2f}%',
                                       f'{srr:.2f}', f'{sav:+.2f}%'], 2):
                c = ws.cell(row=r, column=ci, value=val)
                c.font = _S.FT_NRM
                c.fill = fill
                c.alignment = _S.AL_C
                c.border = _S.BD
            ws.row_dimensions[r].height = 18
            r += 1
