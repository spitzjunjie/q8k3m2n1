# -*- coding: utf-8 -*-
"""资产配置回测 · 执行口径（成本 / 信号滞后）单元测试（离线，合成数据）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip('tushare')  # asset_allocation_backtest 顶层 import tushare

from datetime import date, timedelta
from asset_allocation_backtest import run_portfolio, BOND_ANNUAL

W = {'000300.SH': 0.6, 'bond': 0.4}


def make_prices(path):
    """path: 每日收盘价列表 → {'000300.SH': {YYYYMMDD: close}}，工作日连续。"""
    out, d = {}, date(2020, 2, 3)
    for px in path:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out[d.strftime('%Y%m%d')] = px
        d += timedelta(days=1)
    return {'000300.SH': out}


# 5 日均线：先上行，第 10 日起急跌跌破均线，然后横盘
PATH = [100 + i for i in range(10)] + [90, 85, 85, 85, 85, 85]


def run(**kw):
    return run_portfolio(make_prices(PATH), W, BOND_ANNUAL, dd_control=False,
                         trend_ma=5, trend_floor=0.0, **kw)[0]


def test_defaults_reproduce_historical_convention():
    assert run() == run(cost_rate=0.0, signal_lag=0)


def test_cost_reduces_equity_only_when_trading():
    base, costed = run(), run(cost_rate=0.001)
    assert costed[:10] == base[:10]          # 未调仓前完全一致（建仓不计成本）
    assert costed[-1] < base[-1]


def test_signal_lag_executes_one_day_later():
    base, lagged = run(), run(signal_lag=1)
    # 第 10 日（90）跌破均线：滞后口径当日仍持股，多吃一天跌幅后次日才离场
    assert lagged[10] == base[10]            # 当日收盘估值相同（都在当日开始前持股）
    assert lagged[11] < base[11]             # 次日 85：历史口径已空仓，滞后口径仍持股吃跌幅
