# -*- coding: utf-8 -*-
"""
data.akshare_helper 的按股票查询估值方法测试
"""
import pathlib
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.akshare_helper import AKShareHelper
import data.tushare_helper as tushare_helper_module


class _FailingTushareHelper:
    """强制 get_valuation_data 走 akshare 分支，不依赖测试环境是否配了 TUSHARE_TOKEN"""

    def __init__(self, *a, **kw):
        raise RuntimeError("no token in test env")


def _fake_spot_em_df():
    return pd.DataFrame([
        {"代码": "000001", "市盈率-动态": 8.1, "市净率": 0.9, "市销率": 1.2,
         "市销率TTM": 1.1, "股息率": 3.0, "股息率TTM": 3.0, "总市值": 1.0e11},
        {"代码": "000002", "市盈率-动态": 9.5, "市净率": 1.1, "市销率": 1.3,
         "市销率TTM": 1.2, "股息率": 2.5, "股息率TTM": 2.5, "总市值": 2.0e11},
    ])


def test_get_valuation_data_reuses_market_snapshot_across_symbols(tmp_path, monkeypatch):
    """get_valuation_data 对不同股票查询估值时，全市场快照只应该抓一次

    现状（bug）：data/akshare_helper.py 的 get_valuation_data 每次都调用
    ak.stock_zh_a_spot_em() 抓全市场几千只股票的行情，只为了取其中一行。
    体检脚本实测：91 个策略跑到估值类策略后，每只候选股票都要重新拉一次
    全市场快照，东财接口本身还经常连接失败（Connection aborted /
    RemoteDisconnected），重试 3 次每次退避 2s/4s，导致原本几秒能跑完的
    选股卡了几分钟——这正是 21 个用 get_valuation_data 的策略里，
    大量"零成交"背后的真实原因，不是策略没信号，是这个函数太慢太脆。

    正确行为：同一个 helper 实例查询多只不同股票的估值，全市场快照
    应该只抓一次、缓存复用，而不是每只股票都重新抓一遍。
    """
    monkeypatch.setattr(tushare_helper_module, "TushareHelper", _FailingTushareHelper)

    call_count = {"n": 0}

    def fake_spot_em():
        call_count["n"] += 1
        return _fake_spot_em_df()

    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot_em", fake_spot_em)

    helper = AKShareHelper(cache_dir=str(tmp_path))

    d1 = helper.get_valuation_data("000001")
    d2 = helper.get_valuation_data("000002")

    assert d1["pe"] == pytest.approx(8.1)
    assert d2["pe"] == pytest.approx(9.5)
    assert call_count["n"] == 1, (
        f"全市场快照被抓了 {call_count['n']} 次，应该只抓 1 次并复用"
    )


def test_get_valuation_data_falls_through_to_ths_when_spot_em_empty(tmp_path, monkeypatch):
    """东财快照返回空时，估值降级到同花顺 EPS/每股净资产 计算，不再依赖新浪。

    修复前：方案3（新浪快照）取不到市盈率列却返回全 0 并落盘缓存，
    导致护城河/质量因子/戴维斯双击等估值类策略被 PE=0 关卡全部淘汰。
    """
    monkeypatch.setattr(tushare_helper_module, "TushareHelper", _FailingTushareHelper)

    # 东财快照返回空 —— 触发降级
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zh_a_spot_em",
        lambda: pd.DataFrame(),
    )

    # 同花顺财务 + 历史K线：EPS=2.0 → 15/2 = PE 7.5
    ths_df = pd.DataFrame([
        {"报告期": "2026-03-31", "基本每股收益": "2.0", "每股净资产": "10.0"},
    ])
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_abstract_ths",
        lambda symbol, indicator: ths_df,
    )
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper.get_history_kline",
        lambda self, symbol, days=5, end_date=None: pd.DataFrame(
            [{"close": 15.0}] * 5
        ),
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_valuation_data("000001")

    assert result["pe"] == pytest.approx(7.5), (
        f"东财空→同花顺计算路径应该正常工作，实际返回 {result}"
    )
    assert result["pb"] == pytest.approx(1.5)


def test_get_valuation_data_prefers_ths_over_sina_snapshot(tmp_path, monkeypatch):
    """同花顺计算优先于新浪快照，即使新浪快照带市盈率列也不回退。"""
    monkeypatch.setattr(tushare_helper_module, "TushareHelper", _FailingTushareHelper)
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zh_a_spot_em",
        lambda: pd.DataFrame(),
    )

    def fake_sina_spot():
        raise AssertionError("同花顺可用时不应再请求新浪快照")

    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot", fake_sina_spot)
    ths_df = pd.DataFrame([
        {"报告期": "2026-03-31", "基本每股收益": "2.0", "每股净资产": "10.0"},
    ])
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_abstract_ths",
        lambda symbol, indicator: ths_df,
    )
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper.get_history_kline",
        lambda self, symbol, days=5, end_date=None: pd.DataFrame(
            [{"close": 15.0}] * 5
        ),
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_valuation_data("000001")

    assert result["pe"] == pytest.approx(7.5)


def test_get_realtime_quote_reuses_market_snapshot_across_symbols(tmp_path, monkeypatch):
    """Realtime quotes must locally filter one shared whole-market snapshot."""
    call_count = {"n": 0}

    def fake_spot_em():
        call_count["n"] += 1
        return pd.DataFrame([
            {"代码": "000001", "名称": "平安银行", "最新价": 10.1},
            {"代码": "000002", "名称": "万科A", "最新价": 8.2},
        ])

    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot_em", fake_spot_em)

    helper = AKShareHelper(cache_dir=str(tmp_path))
    first = helper.get_realtime_quote("000001")
    second = helper.get_realtime_quote("000002")

    assert first["名称"] == "平安银行"
    assert second["名称"] == "万科A"
    assert call_count["n"] == 1


def test_get_realtime_quote_reuses_sina_snapshot_when_eastmoney_empty(tmp_path, monkeypatch):
    """The Sina fallback uses its whole-market API without a per-symbol argument."""
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zh_a_spot_em",
        lambda: pd.DataFrame(),
    )
    call_count = {"n": 0}

    def fake_sina_spot():
        call_count["n"] += 1
        return pd.DataFrame([
            {"代码": "sz000001", "名称": "平安银行", "最新价": 10.1},
            {"代码": "sz000002", "名称": "万科A", "最新价": 8.2},
        ])

    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot", fake_sina_spot)

    helper = AKShareHelper(cache_dir=str(tmp_path))
    first = helper.get_realtime_quote("000001")
    second = helper.get_realtime_quote("000002")

    assert first["名称"] == "平安银行"
    assert second["名称"] == "万科A"
    assert call_count["n"] == 1


def test_get_stock_news_falls_back_and_normalizes_columns(tmp_path, monkeypatch):
    """A broken Eastmoney response falls back to normalized Caixin news."""
    def broken_primary():
        raise ValueError(r"invalid escape sequence: \u")

    fallback = pd.DataFrame([
        {
            "tag": "人工智能",
            "summary": "AI 芯片公司取得技术突破",
            "url": "https://example.test/news/1",
        }
    ])
    monkeypatch.setattr("data.akshare_helper.ak.stock_news_em", broken_primary)
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_news_main_cx",
        lambda: fallback,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_stock_news()

    assert result.to_dict("records") == [{
        "关键词": "人工智能",
        "新闻标题": "AI 芯片公司取得技术突破",
        "新闻内容": "AI 芯片公司取得技术突破",
        "文章来源": "财新数据通",
        "发布时间": "",
        "新闻链接": "https://example.test/news/1",
    }]


def test_get_stock_news_falls_through_to_cls_telegraph(tmp_path, monkeypatch):
    """When Eastmoney and Caixin both fail, fall back to normalized CLS news."""
    def broken_primary():
        raise ValueError(r"invalid escape sequence: \u")

    def broken_caixin():
        raise ConnectionError("cxdata.caixin.com: Max retries exceeded")

    cls_df = pd.DataFrame([
        {
            "标题": "AI 芯片公司取得技术突破",
            "内容": "多家厂商发布新品",
            "发布时间": "2026-08-04 19:30:00",
        }
    ])
    monkeypatch.setattr("data.akshare_helper.ak.stock_news_em", broken_primary)
    monkeypatch.setattr("data.akshare_helper.ak.stock_news_main_cx", broken_caixin)
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper._fetch_cls_telegraph",
        lambda self: cls_df,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_stock_news()

    assert result.to_dict("records") == [{
        "关键词": "",
        "新闻标题": "AI 芯片公司取得技术突破",
        "新闻内容": "多家厂商发布新品",
        "文章来源": "财联社",
        "发布时间": "2026-08-04 19:30:00",
        "新闻链接": "",
    }]


def test_get_stock_news_all_sources_fail_returns_empty(tmp_path, monkeypatch):
    """All news sources failing must return an empty DataFrame, not raise."""
    def broken(*args, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr("data.akshare_helper.ak.stock_news_em", broken)
    monkeypatch.setattr("data.akshare_helper.ak.stock_news_main_cx", broken)
    monkeypatch.setattr("data.akshare_helper.ak.stock_info_global_futu", broken)
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper._fetch_cls_telegraph",
        broken,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_stock_news()

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_get_limit_up_list_falls_back_to_strong_pool(tmp_path, monkeypatch):
    """The limit-up helper falls back to the strong pool when the main API breaks."""
    calls = {"em": 0, "strong": 0}

    def broken_zt_pool(*args, **kwargs):
        calls["em"] += 1
        raise ConnectionError("push2ex.eastmoney.com: network down")

    def strong_pool(*args, **kwargs):
        calls["strong"] += 1
        return pd.DataFrame([
            {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "涨跌幅": 10.0},
        ])

    monkeypatch.setattr("data.akshare_helper.ak.stock_zt_pool_em", broken_zt_pool)
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zt_pool_strong_em",
        strong_pool,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_limit_up_list("20260803")

    assert calls["em"] == 1
    assert calls["strong"] == 1
    assert result.to_dict("records")[0]["代码"] == "600000"


def test_get_financial_indicator_parses_ths_roic_and_margin(tmp_path, monkeypatch):
    """THS financial abstract must not hardcode ROIC/gross margin to zero."""
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper._fetch_sina_financial_abstract",
        lambda self, symbol: {},
    )
    ths_df = pd.DataFrame([
        {
            "报告期": "2025-12-31",
            "净资产收益率-加权": "15.23%",
            "投入资本回报率": "9.8%",
            "毛利率": "42.5%",
            "资产负债率": "51.2%",
            "流动比率": "1.35",
            "销售净利率": "12.1%",
        },
        {
            "报告期": "2026-03-31",
            "净资产收益率-加权": "4.1%",
            "投入资本回报率": "2.7%",
            "毛利率": "44.0%",
            "资产负债率": "50.5%",
            "流动比率": "1.42",
            "销售净利率": "13.0%",
        },
    ])
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_abstract_ths",
        lambda symbol, indicator: ths_df,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_financial_indicator("600000")

    assert result["roe"] == pytest.approx(0.041)
    assert result["roic"] == pytest.approx(0.027)
    assert result["gross_margin"] == pytest.approx(0.44)
    assert result["debt_ratio"] == pytest.approx(0.505)
    assert result["net_margin"] == pytest.approx(0.13)


def test_get_financial_indicator_uses_sina_roic(tmp_path, monkeypatch):
    """Sina financial abstract is the primary source and provides ROIC."""
    sina_values = {
        "净资产收益率(ROE)": "10.570000",
        "投入资本回报率": "9.898213",
        "毛利率": "89.759217",
        "销售净利率": "52.224488",
        "资产负债率": "12.122748",
        "流动比率": "7.060728",
    }
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper._fetch_sina_financial_abstract",
        lambda self, symbol: sina_values,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_financial_indicator("600519")

    assert result["roe"] == pytest.approx(0.1057)
    assert result["roic"] == pytest.approx(0.09898213)
    assert result["gross_margin"] == pytest.approx(0.89759217)
    assert result["net_margin"] == pytest.approx(0.52224488)
    assert result["debt_ratio"] == pytest.approx(0.12122748)
    assert result["current_ratio"] == pytest.approx(7.060728)


def test_get_financial_indicator_falls_back_to_em_with_market_suffix(tmp_path, monkeypatch):
    """Eastmoney fallback must use SECUCODE with market suffix and parse fields."""
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper._fetch_sina_financial_abstract",
        lambda self, symbol: {},
    )

    def broken_ths(*args, **kwargs):
        raise ConnectionError("10jqka.com.cn: network down")

    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_abstract_ths",
        broken_ths,
    )
    calls = {}
    em_df = pd.DataFrame([{
        "SECUCODE": "600519.SH",
        "ROE_DILUTED": 10.5687022287,
        "GROSS_PROFIT_RATIO": 89.759217,
        "NET_PROFIT_RATIO": 52.224488,
    }])

    def fake_em(symbol, indicator="按报告期"):
        calls["symbol"] = symbol
        return em_df

    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_analysis_indicator_em",
        fake_em,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_financial_indicator("600519")

    assert calls["symbol"] == "600519.SH"
    assert result["roe"] == pytest.approx(0.105687022287)
    assert result["gross_margin"] == pytest.approx(0.89759217)
    assert result["net_margin"] == pytest.approx(0.52224488)


def test_get_valuation_data_ignores_sina_snapshot_without_pe_columns(tmp_path, monkeypatch):
    """Sina spot has no PE/PB columns; valuation must fall through to THS+kline calc."""
    monkeypatch.setattr(tushare_helper_module, "TushareHelper", _FailingTushareHelper)
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zh_a_spot_em",
        lambda: pd.DataFrame(),
    )
    # 真实新浪快照列：无市盈率/市净率
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_zh_a_spot",
        lambda: pd.DataFrame([{"代码": "sz000001", "名称": "平安银行", "最新价": 1000.0}]),
    )
    ths_df = pd.DataFrame([
        {
            "报告期": "2026-03-31",
            "基本每股收益": "65.66",
            "每股净资产": "195.36",
        }
    ])
    monkeypatch.setattr(
        "data.akshare_helper.ak.stock_financial_abstract_ths",
        lambda symbol, indicator: ths_df,
    )
    monkeypatch.setattr(
        "data.akshare_helper.AKShareHelper.get_history_kline",
        lambda self, symbol, days=5, end_date=None: pd.DataFrame(
            [{"close": 1000.0}, {"close": 1000.0}, {"close": 1000.0}, {"close": 1000.0}, {"close": 1000.0}]
        ),
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_valuation_data("000001")

    assert result["pe"] == pytest.approx(1000.0 / 65.66)
    assert result["pb"] == pytest.approx(1000.0 / 195.36)


def test_spot_em_failure_cached_so_second_call_skips_retries(tmp_path, monkeypatch):
    """A failed Eastmoney snapshot must be cached so later calls skip retries."""
    call_count = {"n": 0}

    def failing_spot_em():
        call_count["n"] += 1
        raise ConnectionError("push2.eastmoney.com: network down")

    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot_em", failing_spot_em)
    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_spot", failing_spot_em)

    helper = AKShareHelper(cache_dir=str(tmp_path))
    helper._get_spot_em_snapshot()
    helper._get_spot_em_snapshot()

    assert call_count["n"] == 1


def test_get_etf_history_kline_falls_back_to_sina_etf(tmp_path, monkeypatch):
    """ETF K-line falls back to the Sina ETF endpoint when Eastmoney fails."""
    def broken_em(*args, **kwargs):
        raise ConnectionError("push2his.eastmoney.com: network down")

    def broken_stock_daily(*args, **kwargs):
        raise ValueError("JSONDecodeError: No value to decode")

    sina_df = pd.DataFrame([
        {"date": "2026-08-03", "open": 4.5, "high": 4.6, "low": 4.4,
         "close": 4.55, "volume": 1e8, "amount": 4e9},
        {"date": "2026-08-04", "open": 4.6, "high": 4.7, "low": 4.5,
         "close": 4.65, "volume": 1.1e8, "amount": 4.5e9},
    ])
    monkeypatch.setattr("data.akshare_helper.ak.fund_etf_hist_em", broken_em)
    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_daily", broken_stock_daily)
    monkeypatch.setattr(
        "data.akshare_helper.ak.fund_etf_hist_sina",
        lambda symbol: sina_df,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_etf_history_kline("510300", days=5)

    assert result["close"].iloc[-1] == pytest.approx(4.65)


def test_get_history_kline_falls_back_to_sina_etf_for_etf_code(tmp_path, monkeypatch):
    """Generic history kline must use the Sina ETF endpoint for ETF codes."""
    def broken_stock_daily(*args, **kwargs):
        raise ValueError("JSONDecodeError: No value to decode")

    def broken_em_hist(*args, **kwargs):
        raise ConnectionError("push2his.eastmoney.com: network down")

    sina_df = pd.DataFrame([
        {"date": "2026-08-03", "open": 4.5, "high": 4.6, "low": 4.4,
         "close": 4.55, "volume": 1e8, "amount": 4e9},
        {"date": "2026-08-04", "open": 4.6, "high": 4.7, "low": 4.5,
         "close": 4.65, "volume": 1.1e8, "amount": 4.5e9},
    ])
    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_daily", broken_stock_daily)
    monkeypatch.setattr("data.akshare_helper.ak.stock_zh_a_hist", broken_em_hist)
    monkeypatch.setattr(
        "data.akshare_helper.ak.fund_etf_hist_sina",
        lambda symbol: sina_df,
    )

    helper = AKShareHelper(cache_dir=str(tmp_path))
    result = helper.get_history_kline("510300", days=5)

    assert result["close"].iloc[-1] == pytest.approx(4.65)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
