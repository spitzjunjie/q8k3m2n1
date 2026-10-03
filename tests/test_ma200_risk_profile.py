# -*- coding: utf-8 -*-
"""MA200 风险画像 · 单元测试（离线，合成数据，用 ma=3 缩小窗口）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ma200_risk_profile import signals, segments, profile


DATES = [f'2020{m:02d}{d:02d}' for m in (1, 2) for d in range(1, 11)]  # 20 个"交易日"


def test_signals_and_segments():
    closes = [10, 10, 10, 11, 12, 9, 8, 7, 12, 13]
    s = signals(DATES[:10], closes, ma=3)
    assert s[:2] == [None, None]
    assert s[2:] == [True, True, True, False, False, False, True, True]
    assert segments(DATES[:10], s) == [(True, 2, 4), (False, 5, 7), (True, 8, 9)]


def test_profile_counts_flips_short_lived_and_missed_rally():
    # 上行 → 急跌空仓 → 空仓中反弹 → 翻多
    closes = [10, 10, 10, 11, 12, 9, 8, 7, 12, 13]
    p = profile(DATES[:10], closes, ma=3, short_lived=5)
    assert p['n_flips'] == 2
    assert p['flips_by_year'] == {'2020': 2}
    # 中间空仓段（3 日）是短命信号：9 卖出、12 买回 → 打脸损耗 = 12/9 - 1
    assert len(p['short_lived']) == 1
    sl = p['short_lived'][0]
    assert sl['state'] == 'cash' and sl['days'] == 3
    assert sl['whipsaw_loss'] == round(12 / 9 - 1, 4)
    assert p['longest_cash']['days'] == 3


def test_underperformance_when_cash_during_rally():
    # 空仓段内指数大涨（踏空）→ 相对净值回撤
    closes = [10, 10, 10, 9, 8, 9, 10, 11, 12, 13]
    p = profile(DATES[:10], closes, ma=3)
    assert p['worst_missed_rally_in_cash']['gain'] > 0
    assert p['longest_underperformance_vs_bh']['days'] > 0


def test_short_hold_segment_bought_high_sold_low_is_a_loss():
    # 空仓 → 短暂翻多（11 买入）→ 跌回均线下（9 卖出）→ 再翻多
    closes = [10, 10, 10, 9, 8, 11, 9, 8, 7, 12, 13, 14]
    p = profile(DATES[:12], closes, ma=3, short_lived=5)
    hold = [x for x in p['short_lived'] if x['state'] == 'hold']
    assert hold and hold[0]['whipsaw_loss'] == round(1 - 9 / 11, 4)
    assert p['short_lived_total_loss'] > 0
