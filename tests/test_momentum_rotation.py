# -*- coding: utf-8 -*-
"""三指数动量轮动 · 单元测试（离线，合成数据）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from momentum_rotation_backtest import (
    RISK_ASSETS, month_end_indices, cash_index_series, select_assets,
)


def make_dates(months):
    """生成连续工作日的 YYYYMMDD 字符串列表。months: [(年, 月, 天数), ...]"""
    from datetime import date, timedelta
    out = []
    for y, m, ndays in months:
        d = date(y, m, 1)
        while d.month == m and len([x for x in out if x[:6] == f'{y}{m:02d}']) < ndays:
            if d.weekday() < 5:
                out.append(d.strftime('%Y%m%d'))
            d += timedelta(days=1)
    return out


def make_close(dates, spec):
    """spec: {code: 起始价}，每天 +1 线性上行；或 {code: (起始价, 日涨幅)}"""
    out = {}
    for code, cfg in spec.items():
        px, daily = cfg if isinstance(cfg, tuple) else (cfg, 0.0)
        series, p = {}, px
        for d in dates:
            series[d] = round(p, 4)
            p *= (1 + daily)
        out[code] = series
    return out


class TestMonthEnd:
    def test_last_trading_day_of_each_month(self):
        dates = make_dates([(2026, 1, 20), (2026, 2, 15)])
        me = month_end_indices(dates)
        assert len(me) == 2
        assert dates[me[0]][:6] == '202601' and dates[me[1]][:6] == '202602'
        # 是该月最后一个交易日
        assert me[1] == len(dates) - 1 or dates[me[1] + 1][:6] == '202603'


class TestCashIndex:
    def test_grows_by_factor(self):
        dates = ['20260105', '20260106', '20260107']
        factors = {'20260106': 1.01, '20260107': 1.02}
        idx = cash_index_series(dates, factors)
        assert idx[0] == 1.0
        assert abs(idx[1] - 1.01) < 1e-9
        assert abs(idx[2] - 1.01 * 1.02) < 1e-9

    def test_missing_date_falls_back_to_bond_daily(self):
        from asset_allocation_backtest import BOND_DAILY_FACTOR
        dates = ['20260105', '20060106']   # 2006 无 SHIBOR → 回退
        idx = cash_index_series(dates, {})
        assert abs(idx[1] - BOND_DAILY_FACTOR) < 1e-9

    def test_none_factors_all_fallback(self):
        from asset_allocation_backtest import BOND_DAILY_FACTOR
        dates = ['20260105', '20260106']
        idx = cash_index_series(dates, None)
        assert abs(idx[1] - BOND_DAILY_FACTOR) < 1e-9


class TestSelectAssets:
    def test_picks_strongest_relative(self):
        # 12 个整月，B 上行最快 → 每个有效月末都选 B
        dates = make_dates([(2025, m, 20) for m in range(1, 13)])
        close = make_close(dates, {
            '000300.SH': (100, 0.0), '000905.SH': (100, 0.01), 'H30269.CSI': (100, 0.0),
        })
        cash_idx = cash_index_series(dates, None)
        h = select_assets(close, dates, 3, cash_idx)
        # 前 3 个月历史不足 → cash；之后全选 000905.SH（日涨 1% 远超现金）
        assert h[:3] == ['cash'] * 3
        assert set(h[3:]) == {'000905.SH'}

    def test_absolute_momentum_goes_cash(self):
        # 全部资产下跌、现金正收益 → 全现金
        dates = make_dates([(2025, m, 20) for m in range(1, 13)])
        close = make_close(dates, {
            '000300.SH': (100, -0.005), '000905.SH': (100, -0.001), 'H30269.CSI': (100, -0.002),
        })
        cash_idx = cash_index_series(dates, None)   # 回退 3.5% 年化 > 资产收益
        h = select_assets(close, dates, 3, cash_idx)
        assert set(h[3:]) == {'cash'}

    def test_insufficient_history_is_cash(self):
        dates = make_dates([(2025, 1, 20), (2025, 2, 20)])
        close = make_close(dates, {'000300.SH': 100, '000905.SH': 100, 'H30269.CSI': 100})
        h = select_assets(close, dates, 3, cash_index_series(dates, None))
        assert set(h) == {'cash'}
