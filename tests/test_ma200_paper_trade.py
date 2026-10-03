# -*- coding: utf-8 -*-
"""MA200 模拟盘 v2 · 单元测试（离线，合成数据）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip('tushare')  # ma200_common 顶层 import tushare

import ma200_paper_trade as pt


def bar(d, op, cl, ma):
    return {'date': d, 'open': op, 'close': cl, 'ma': ma}


def test_signal_executes_next_open_not_same_close():
    st = pt.new_state('20260818')
    pt.process_day(st, bar('20260818', 100, 105, 100), 0.0)
    # 当天只挂单，不成交
    assert st['units'] == 0.0 and st['cash'] == pt.INITIAL
    assert st['pending'] == pt.STOCK_PCT
    pt.process_day(st, bar('20260819', 110, 110, 100), 0.0)
    # 次日按开盘价 110 成交 60%，扣单边成本
    expect_cost = pt.INITIAL * pt.STOCK_PCT * pt.COST_RATE
    assert st['units'] == pytest.approx(pt.INITIAL * pt.STOCK_PCT / 110)
    assert st['cash'] == pytest.approx(pt.INITIAL * (1 - pt.STOCK_PCT) - expect_cost)
    assert st['pending'] is None and st['target'] == pt.STOCK_PCT
    assert st['history'][-1]['trade']['price'] == 110


def test_cash_accrues_interest_daily():
    st = pt.new_state('20260818')
    pt.process_day(st, bar('20260818', 100, 95, 100), 0.02)  # 首日不计息，信号空仓
    assert st['pending'] == 0.0
    pt.process_day(st, bar('20260819', 95, 95, 100), 0.02)
    # 空仓挂单 0→0 成交无成本，现金计息一天
    assert st['cash'] == pytest.approx(pt.INITIAL * 1.02 ** (1 / 252))


def test_semiannual_rebalance_on_first_trading_day_of_july():
    st = pt.new_state('20260629')
    pt.process_day(st, bar('20260629', 100, 100, 90), 0.0)
    pt.process_day(st, bar('20260630', 100, 150, 90), 0.0)   # 开盘买入，收盘大涨，股票占比漂移
    assert st['history'][-1].get('trade', {}).get('reason') == 'signal'
    rec = pt.process_day(st, bar('20260701', 150, 150, 90), 0.0)
    assert rec['trade']['reason'] == 'rebalance'
    stock = st['units'] * 150
    assert stock / (stock + st['cash']) == pytest.approx(pt.STOCK_PCT, rel=1e-3)  # 成本从现金扣，略偏


def test_replay_fills_missing_days_and_is_idempotent():
    st = pt.new_state('20260818')
    bars = [bar('20260817', 99, 99, 100), bar('20260818', 100, 101, 100),
            bar('20260819', 101, 102, 100), bar('20260820', 102, 103, 100)]
    assert pt.replay(st, bars, {}) == 3          # start 之前的 0817 不记
    assert [h['date'] for h in st['history']] == ['20260818', '20260819', '20260820']
    assert pt.replay(st, bars, {}) == 0          # 重复运行不重复记账
    bars.append(bar('20260821', 103, 104, 100))
    assert pt.replay(st, bars, {}) == 1


def test_rate_lookup_uses_latest_published_and_fallback():
    rates = {'20260901': 0.015, '20260905': 0.013}
    assert pt.rate_on(rates, '20260904', 0.02) == 0.015
    assert pt.rate_on(rates, '20260910', 0.02) == 0.013
    assert pt.rate_on(rates, '20260801', 0.02) == 0.02


def test_missing_ma_raises():
    st = pt.new_state('20260818')
    with pytest.raises(ValueError):
        pt.process_day(st, bar('20260818', 100, 100, None), 0.0)
