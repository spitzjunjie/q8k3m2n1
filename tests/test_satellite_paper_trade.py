# -*- coding: utf-8 -*-
"""红利低波卫星前向模拟盘 · 单元测试（离线，合成数据）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip('tushare')

import satellite_paper_trade as sp


def series(vals, start=8):
    return {f'202610{start + i:02d}': v for i, v in enumerate(vals)}


def test_flat_prices_only_cost_and_cash():
    hs, dv = series([4.0] * 5), series([1.0] * 5)
    cash = series([100.0, 100.01, 100.02, 100.03, 100.04])
    dates, s, b = sp.compute(hs, dv, cash)
    assert len(dates) == 5
    assert s[-1] == pytest.approx(b[-1])          # 股票不动：两者只差在现金，完全相同
    assert s[-1] > 100                            # 现金腿按 511360 价格计息


def test_satellite_leg_moves_s_only_by_its_weight():
    hs, cash = series([4.0] * 3), series([100.0] * 3)
    dv = series([1.0, 1.0, 1.1])                  # 红利低波 +10%
    _, s, b = sp.compute(hs, dv, cash)
    assert b[-1] == pytest.approx(b[0])
    assert s[-1] / s[0] - 1 == pytest.approx(0.2 * 0.1, rel=1e-6)


def test_uses_only_common_dates():
    hs = series([4.0] * 4)
    dv = series([1.0] * 3)
    cash = series([100.0] * 4)
    dates, _, _ = sp.compute(hs, dv, cash)
    assert len(dates) == 3
