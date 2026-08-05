# -*- coding: utf-8 -*-
"""回归测试：helper 财务字段为小数（roe=0.15），策略阈值按百分数比较。

历史上多个策略把 fin 返回的小数与百分数阈值直接比较（如 roe > 8），
导致永远选不出股票。修复后统一 roe*100 转百分数再比较。
"""
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategies.convertible_bond_downward_strategy import ConvertibleBondDownwardStrategy
from strategies.davis_double_hit_strategy import DavisDoubleHitStrategy
from strategies.event_strategies import STRemoveStrategy
from strategies.lockup_expiry_arbitrage_strategy import LockupExpiryArbitrageStrategy
from strategies.shareholder_change_strategy import ShareholderChangeStrategy
from strategies.turnaround_strategy import TurnaroundStrategy


FIN = {
    'roe': 0.15,           # 15%
    'gross_margin': 0.40,  # 40%
    'net_margin': 0.20,    # 20%
    'debt_ratio': 0.30,    # 30%
    'current_ratio': 1.5,
}


class _FinancialHelper:
    """统一 mock：所有数据正常，财务字段均为小数。"""

    def __init__(self, kline):
        self.kline = kline

    def get_stock_pool(self, pool, sorted_by_market_value=False):
        return ['000001']

    def get_history_kline(self, symbol, days=30, end_date=None):
        return self.kline

    def get_financial_indicator(self, symbol):
        return dict(FIN)

    def get_growth_data(self, symbol):
        return {'profit_growth': 25.0, 'revenue_growth': 15.0}

    def get_valuation_data(self, symbol):
        return {'pe_ttm': 15.0, 'pe': 15.0, 'pb': 1.8}

    def get_cash_flow(self, symbol):
        return {'operating_cf': 1e8, 'net_profit': 1e7}

    def get_north_holding(self, symbol):
        return {'hold_ratio': 0.03}


def _rising_kline(n=30, start=10.0, end=10.5):
    closes = [start + (end - start) * i / (n - 1) for i in range(n)]
    return pd.DataFrame({'close': closes, 'volume': [100.0] * n})


def _deep_drop_kline(n=90, high=20.0, low=14.0, drop_from=80):
    closes = [high] * drop_from + [low] * (n - drop_from)
    return pd.DataFrame({'close': closes, 'high': closes, 'volume': [100.0] * n})


def test_davis_double_hit_uses_percent_roe():
    helper = _FinancialHelper(_rising_kline(30))
    results = DavisDoubleHitStrategy().select_stocks(helper)
    assert results and results[0]['symbol'] == '000001'
    assert 'ROE=15.0%' in results[0]['reason']


def test_turnaround_uses_percent_margins_and_roe():
    closes = [10.0] * 59 + [9.5]
    helper = _FinancialHelper(pd.DataFrame({'close': closes, 'volume': [100.0] * 60}))
    results = TurnaroundStrategy().select_stocks(helper)
    assert results and results[0]['symbol'] == '000001'
    assert 'ROE=15.0%' in results[0]['reason']


def test_shareholder_change_uses_percent_roe():
    helper = _FinancialHelper(_rising_kline(30))
    results = ShareholderChangeStrategy().select_stocks(helper)
    assert results and results[0]['symbol'] == '000001'


def test_convertible_bond_downward_uses_percent_roe():
    helper = _FinancialHelper(_deep_drop_kline(60, high=20.0, low=8.0, drop_from=59))
    results = ConvertibleBondDownwardStrategy().select_stocks(helper)
    assert results and results[0]['symbol'] == '000001'


def test_lockup_expiry_arbitrage_uses_percent_roe():
    helper = _FinancialHelper(_deep_drop_kline(90, high=20.0, low=14.0, drop_from=80))
    results = LockupExpiryArbitrageStrategy().select_stocks(helper)
    assert results and results[0]['symbol'] == '000001'


def test_st_remove_requires_roe_below_5_percent():
    """ST摘帽：ROE 20% 不应命中困境反转；ROE 3% 应命中。"""
    high_roe_helper = _FinancialHelper(_rising_kline(5))
    high_roe_helper.get_financial_indicator = lambda symbol: {**FIN, 'roe': 0.20}
    high_roe_helper.get_growth_data = lambda symbol: {'profit_growth': 60.0, 'revenue_growth': 15.0}
    assert STRemoveStrategy().detect_events(high_roe_helper) == []

    low_roe_helper = _FinancialHelper(_rising_kline(5))
    low_roe_helper.get_financial_indicator = lambda symbol: {**FIN, 'roe': 0.03}
    low_roe_helper.get_growth_data = lambda symbol: {'profit_growth': 60.0, 'revenue_growth': 15.0}
    results = STRemoveStrategy().detect_events(low_roe_helper)
    assert results and results[0]['symbol'] == '000001'
