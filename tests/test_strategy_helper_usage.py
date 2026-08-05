# -*- coding: utf-8 -*-
"""Regression tests ensuring strategies expose provider access through the helper."""
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import strategies.earnings_preview_strategy as earnings_module
import strategies.continuous_volume_strategy as continuous_module
import strategies.moat_strategy as moat_module
import strategies.news_sentiment_strategy as news_module
import strategies.northbound_change_strategy as northbound_module
import strategies.piotroski_strategy as piotroski_module
import strategies.sector_rotation_strategy as sector_module
from strategies.advanced_strategies import VolumeBreakoutStrategy as AdvancedVolumeBreakoutStrategy
from strategies.continuous_volume_strategy import ContinuousVolumeStrategy
from strategies.earnings_preview_strategy import EarningsPreviewStrategy
from strategies.market_sentiment_strategy import SentimentIcePointStrategy
from strategies.moat_strategy import MoatStrategy
from strategies.news_sentiment_strategy import HotNewsTrackingStrategy, NewsSentimentStrategy
from strategies.northbound_change_strategy import NorthboundChangeStrategy
from strategies.piotroski_strategy import PiotroskiStrategy
from strategies.sector_rotation_strategy import SectorRotationStrategy


class _TrackingHelper:
    def __init__(self):
        self.wrap_calls = 0

    def wrap_akshare(self, func, *args, **kwargs):
        self.wrap_calls += 1
        return func(*args, **kwargs)

    def get_stock_list(self):
        return []

    def get_stock_news(self):
        return self.wrap_akshare(news_module.ak.stock_news_em)


@pytest.mark.parametrize(
    "strategy",
    [
        EarningsPreviewStrategy(),
        NorthboundChangeStrategy(),
        NewsSentimentStrategy(),
        HotNewsTrackingStrategy(),
        SectorRotationStrategy(),
    ],
    ids=["earnings", "northbound", "news", "hot-news", "sector"],
)
def test_provider_access_is_observable_through_helper(strategy, monkeypatch):
    """Even an empty provider response must be recorded through the helper."""
    empty = lambda *args, **kwargs: pd.DataFrame()
    monkeypatch.setattr(earnings_module.ak, "stock_report_disclosure", empty)
    monkeypatch.setattr(northbound_module.ak, "stock_hsgt_hold_stock_em", empty)
    monkeypatch.setattr(news_module.ak, "stock_news_em", empty)
    monkeypatch.setattr(sector_module.ak, "stock_board_industry_name_em", empty)
    monkeypatch.setattr(sector_module.ak, "stock_zh_index_daily", empty)
    monkeypatch.setattr(sector_module.ak, "stock_board_industry_hist_em", empty)
    monkeypatch.setattr(sector_module.ak, "stock_board_industry_cons_em", empty)

    helper = _TrackingHelper()
    strategy.select_stocks(helper)

    assert helper.wrap_calls > 0


def test_sentiment_icepoint_uses_existing_limit_up_helper_method():
    class SentimentHelper:
        def __init__(self):
            self.limit_calls = 0

        def get_limit_up_list(self, date=None):
            self.limit_calls += 1
            return pd.DataFrame()

        def get_stock_list(self):
            return []

    helper = SentimentHelper()
    SentimentIcePointStrategy().select_stocks(helper)

    assert helper.limit_calls == 1


@pytest.mark.parametrize("strategy", [NewsSentimentStrategy(), HotNewsTrackingStrategy()])
def test_news_strategies_use_helper_news_fallback(strategy):
    class NewsHelper:
        def __init__(self):
            self.news_calls = 0

        def get_stock_news(self):
            self.news_calls += 1
            return pd.DataFrame()

    helper = NewsHelper()
    strategy.detect_events(helper)

    assert helper.news_calls == 1


def test_sector_rotation_stops_after_three_consecutive_empty_histories(monkeypatch):
    industries = pd.DataFrame([
        {"板块名称": name} for name in ["行业1", "行业2", "行业3", "行业4", "行业5"]
    ])
    calls = {"history": 0}

    def fake_industry_list():
        return industries

    def empty_history(*args, **kwargs):
        calls["history"] += 1
        return pd.DataFrame()

    monkeypatch.setattr(sector_module.ak, "stock_board_industry_name_em", fake_industry_list)
    monkeypatch.setattr(sector_module.ak, "stock_board_industry_hist_em", empty_history)
    monkeypatch.setattr(sector_module.ak, "stock_zh_index_daily", lambda **kwargs: pd.DataFrame())

    helper = _TrackingHelper()
    SectorRotationStrategy().detect_events(helper)

    assert calls["history"] == 3


def test_sector_rotation_stops_immediately_when_helper_degraded(monkeypatch):
    """Once the helper is in fast-fail mode, only the first industry is requested."""
    industries = pd.DataFrame([
        {"板块名称": name} for name in ["行业1", "行业2", "行业3", "行业4", "行业5"]
    ])
    calls = {"history": 0}

    def fake_industry_list():
        return industries

    def failing_history(*args, **kwargs):
        calls["history"] += 1
        raise ConnectionError(
            "HTTPSConnectionPool(host='17.push2.eastmoney.com', port=443): "
            "Max retries exceeded (Caused by ProxyError('Unable to connect to proxy', "
            "RemoteDisconnected('Remote end closed connection without response')))"
        )

    monkeypatch.setattr(sector_module.ak, "stock_board_industry_name_em", fake_industry_list)
    monkeypatch.setattr(sector_module.ak, "stock_board_industry_hist_em", failing_history)
    monkeypatch.setattr(sector_module.ak, "stock_zh_index_daily", lambda **kwargs: pd.DataFrame())

    class DegradedHelper(_TrackingHelper):
        _consecutive_network_failures = 3

    helper = DegradedHelper()
    SectorRotationStrategy().detect_events(helper)

    assert calls["history"] == 1


def test_continuous_volume_uses_helper_pool_instead_of_hardcoded_only():
    """量价齐升应从 helper 获取真实股票池，而非只扫描硬编码的 8 只股票。"""
    class PoolHelper:
        def __init__(self):
            self.pool_calls = 0
            self.quote_calls = 0

        def get_stock_pool(self, pool, sorted_by_market_value=False):
            self.pool_calls += 1
            return ['000001', '000002']  # 均不在硬编码兜底池中

        def get_history_kline(self, symbol, days=30, end_date=None):
            closes = [9.5] * 25
            closes[-1] = 10.0  # 涨幅 5.26%，落在 (5, 15)
            volumes = [100.0] * 25
            volumes[-1] = 1000.0  # 量比远大于 2
            return pd.DataFrame({'close': closes, 'volume': volumes})

        def get_realtime_quote(self, symbol):
            self.quote_calls += 1
            return {'名称': '测试' + symbol}

    helper = PoolHelper()
    results = ContinuousVolumeStrategy().select_stocks(helper)

    assert helper.pool_calls == 1
    assert results and results[0]['symbol'] == '000001'
    assert '量比' in results[0]['reason']
    assert helper.quote_calls >= 1


def _kline_series(n=70, ret_pct=5.0):
    """构造收盘价序列：60 日累计涨幅为 ret_pct%。"""
    closes = [10.0 + i * 0.01 for i in range(n)]
    # 调整首尾使区间涨幅符合要求
    start = closes[0]
    closes[-1] = start * (1 + ret_pct / 100)
    closes[-2] = closes[-1] * 0.995
    return pd.DataFrame({'close': closes, 'volume': [100.0] * n})


def test_moat_enters_financial_screen_when_drawdown_within_limit(monkeypatch):
    """护城河：60 日跌幅在阈值内时，应进入财务筛选而不是被均线过滤清零。"""
    class MoatHelper:
        def __init__(self):
            self.fin_calls = 0

        def get_stock_pool(self, pool, sorted_by_market_value=False):
            return ['000001']

        def get_history_kline(self, symbol, days=70, end_date=None):
            return _kline_series(n=70, ret_pct=-5.0)

        def get_financial_indicator(self, symbol):
            self.fin_calls += 1
            return {'roe': 0.12, 'gross_margin': 0.45, 'debt_ratio': 0.30, 'net_margin': 0.15}

        def get_valuation_data(self, symbol):
            return {'pe': 15.0, 'pb': 2.0}

        def get_realtime_quote(self, symbol):
            return {'名称': '测试股'}

    helper = MoatHelper()
    results = MoatStrategy().select_stocks(helper)

    assert helper.fin_calls == 1
    assert results and results[0]['symbol'] == '000001'


def test_moat_skips_stock_when_drawdown_exceeds_limit():
    """护城河：60 日跌幅超过阈值时直接排除，不进入财务筛选。"""
    class SteepDropHelper:
        def __init__(self):
            self.fin_calls = 0

        def get_stock_pool(self, pool, sorted_by_market_value=False):
            return ['000001']

        def get_history_kline(self, symbol, days=70, end_date=None):
            return _kline_series(n=70, ret_pct=-30.0)

        def get_financial_indicator(self, symbol):
            self.fin_calls += 1
            return {'roe': 0.12, 'gross_margin': 0.45, 'debt_ratio': 0.30}

        def get_valuation_data(self, symbol):
            return {'pe': 15.0, 'pb': 2.0}

        def get_realtime_quote(self, symbol):
            return {'名称': '测试股'}

    helper = SteepDropHelper()
    results = MoatStrategy().select_stocks(helper)

    assert helper.fin_calls == 0
    assert results == []


def test_piotroski_enters_financial_screen_when_drawdown_within_limit():
    """质量因子：20 日跌幅在阈值内时进入财务评分。"""
    class PiotroskiHelper:
        def __init__(self):
            self.fin_calls = 0

        def get_stock_pool(self, pool, sorted_by_market_value=False):
            return ['000001']

        def get_history_kline(self, symbol, days=30, end_date=None):
            return _kline_series(n=30, ret_pct=-3.0)

        def get_financial_indicator(self, symbol):
            self.fin_calls += 1
            return {
                'roe': 0.12, 'net_margin': 0.15, 'debt_ratio': 0.3,
                'current_ratio': 1.5, 'gross_margin': 0.4,
            }

        def get_cash_flow(self, symbol):
            return {'operating_cf': 1e8}

        def get_valuation_data(self, symbol):
            return {'pe': 15.0, 'pb': 2.0}

        def get_realtime_quote(self, symbol):
            return {'名称': '测试股'}

    helper = PiotroskiHelper()
    results = PiotroskiStrategy().select_stocks(helper)

    assert helper.fin_calls == 1
    assert results and results[0]['symbol'] == '000001'


def test_advanced_volume_breakout_uses_helper_pool():
    """advanced 量价齐升应从 helper 获取真实股票池。"""
    class BreakoutHelper:
        def __init__(self):
            self.pool_calls = 0

        def get_stock_pool(self, pool, sorted_by_market_value=False):
            self.pool_calls += 1
            return ['000001', '000002']

        def get_history_kline(self, symbol, days=30, end_date=None):
            closes = [10.0] * 25
            closes[-1] = 10.5
            volumes = [100.0] * 25
            volumes[-1] = 1000.0
            return pd.DataFrame({'close': closes, 'volume': volumes})

        def get_realtime_quote(self, symbol):
            return {'名称': '测试' + symbol}

    helper = BreakoutHelper()
    results = AdvancedVolumeBreakoutStrategy().select_stocks(helper)

    assert helper.pool_calls == 1
    assert results and results[0]['symbol'] == '000001'
