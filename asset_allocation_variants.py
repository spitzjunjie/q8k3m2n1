# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
资产配置 · 变体研究脚本（不动线上 asset_allocation_backtest.py）
================================================================
在已样本外验证的 60/40 + MA200 基础上，追加四类增量并逐个对比：
  1. 双均线趋势过滤（快/慢均线金叉死叉）
  2. 波动率目标（vol targeting，按实现波动率缩放仓位，月频）
  3. 交易成本建模（再平衡换手 × bps）
  4. 扩资产池（黄金 ETF 518880 + 纳指 ETF 513100 + 红利低波 512890）

数据拉取 / 指标 / 基准复用 asset_allocation_backtest，本脚本只新增引擎与变体。
"""

import os
import sys
import json
import math
import argparse
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import (
    load_prices, run_buyhold, summarize, print_table, build_bond_factors,
    slice_prices, _common_dates, INITIAL_CAPITAL, BOND_ANNUAL,
    DEFAULT_START, DEFAULT_END, get_tushare_pro,
)

BOND_DAILY_FACTOR = (1 + BOND_ANNUAL) ** (1 / 252)


def run_portfolio_v2(prices, weights, bond_annual, dd_control,
                     min_stock=0.30, dd_threshold=0.15, restore_dd=None,
                     rebalance_months=(1, 7), initial=INITIAL_CAPITAL,
                     trend_ma=0, trend_ma_fast=0, trend_floor=0.0,
                     vol_target=None, vol_lookback=20, cost_bps=0.0,
                     bond_factors=None, report_start=None):
    """在 run_portfolio 基础上扩展：双均线 / 波动率目标 / 交易成本。

    trend_ma>0 且 trend_ma_fast>0  → 快/慢均线金叉死叉（快>=慢 视为满仓）
    trend_ma>0 且 trend_ma_fast=0  → 单均线 vs 价格（原语义）
    vol_target 不为 None           → 月频按实现波动率缩放仓位（cap=1，无杠杆）
    cost_bps>0                     → 再平衡时按换手 × bps 扣成本
    """
    assets = [a for a in weights if a != 'bond']
    bond_w = weights.get('bond', 0.0)
    full_stock = 1.0 - bond_w
    dates = _common_dates(prices, assets)
    if not dates:
        return [], []
    start_i = 0
    d0 = dates[start_i]
    stock_w_sum = sum(weights[a] for a in assets)
    p0 = {a: prices[a][d0.isoformat().replace('-', '')] for a in assets}
    units = {a: initial * weights[a] / stock_w_sum / p0[a] for a in assets}
    bond = initial * bond_w
    target_stock = full_stock
    peak = initial
    equity = []
    trigger = False

    closes = [prices[assets[0]][d.isoformat().replace('-', '')] for d in dates]

    # 趋势状态（单均线或双均线）
    trend_state = []
    if trend_ma > 0:
        for i in range(len(dates)):
            if i < trend_ma - 1:
                trend_state.append(True)
            elif trend_ma_fast > 0:
                slow = sum(closes[i - trend_ma + 1:i + 1]) / trend_ma
                if i >= trend_ma_fast - 1:
                    fast = sum(closes[i - trend_ma_fast + 1:i + 1]) / trend_ma_fast
                    trend_state.append(fast >= slow)
                else:
                    trend_state.append(True)  # 快线窗口不足，暂视为满仓
            else:
                ma = sum(closes[i - trend_ma + 1:i + 1]) / trend_ma
                trend_state.append(closes[i] >= ma)

    # 波动率目标：逐日实现波动率 → 仓位乘数
    vol_mult = [1.0] * len(dates)
    if vol_target is not None:
        rets = [0.0] + [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        for i in range(len(dates)):
            if i < vol_lookback:
                continue
            w = rets[i - vol_lookback + 1:i + 1]
            m = sum(w) / len(w)
            var = sum((r - m) ** 2 for r in w) / len(w)
            rv = math.sqrt(var) * math.sqrt(252)
            vol_mult[i] = min(1.0, vol_target / rv) if rv > 0 else 1.0

    for i in range(start_i, len(dates)):
        d = dates[i]
        dstr = d.isoformat().replace('-', '')
        pcur = {a: prices[a][dstr] for a in assets}
        bond *= (bond_factors.get(dstr, BOND_DAILY_FACTOR) if bond_factors else BOND_DAILY_FACTOR)
        stock_total = sum(units[a] * pcur[a] for a in assets)
        total = stock_total + bond

        # 控回撤（与原语义一致）
        if dd_control:
            if total > peak:
                peak = total
            dd = (peak - total) / peak if peak > 0 else 0.0
            if target_stock == full_stock and dd > dd_threshold:
                target_stock = min_stock
                trigger = True
            elif target_stock == min_stock:
                restored = (restore_dd is not None and dd <= restore_dd) or (restore_dd is None and total >= peak - 1e-9)
                if restored:
                    target_stock = full_stock
                    trigger = True

        # 趋势过滤（单均线或双均线）
        if trend_ma > 0 and i < len(trend_state):
            if not trend_state[i] and target_stock > trend_floor:
                target_stock = trend_floor
                trigger = True
            elif trend_state[i] and target_stock < full_stock:
                target_stock = full_stock
                trigger = True

        # 再平衡
        is_month_first = (i == start_i) or (dates[i - 1].month != d.month or dates[i - 1].year != d.year)
        if trigger or (is_month_first and d.month in rebalance_months):
            vm = vol_mult[i]
            old_stock_w = stock_total / total if total > 0 else 0.0
            desired_stock = target_stock * total * vm
            # 交易成本：换手 = |新旧股票权重差|
            turnover = abs(desired_stock / total - old_stock_w) if total > 0 else 0.0
            cost = turnover * total * cost_bps
            total -= cost
            sw = {a: weights[a] for a in assets}
            ssw = sum(sw.values())
            for a in assets:
                units[a] = desired_stock * (sw[a] / ssw) / pcur[a]
            bond = total - desired_stock
            trigger = False

        equity.append(sum(units[a] * pcur[a] for a in assets) + bond)

    if report_start:
        keep = [(d, e) for d, e in zip(dates[start_i:], equity) if d.isoformat().replace('-', '') >= report_start]
        return [e for _, e in keep], [d for d, _ in keep]
    return equity, dates[start_i:]


def run_main_variants(prices, args, bond_factors=None):
    """60/40 主线变体：基线 / MA200 / 双均线 / 波动率目标 / 成本。"""
    def port(**kw):
        return run_portfolio_v2(prices, {'000300.SH': 0.6, 'bond': 0.4}, BOND_ANNUAL,
                                dd_control=kw.pop('dd_control', False),
                                bond_factors=bond_factors, **kw)

    rows = [
        summarize('60/40 半年再平衡', port()[0]),
        summarize('+ MA200 趋势过滤', port(trend_ma=200, trend_floor=0.0)[0]),
        summarize('+ 双均线 50/200', port(trend_ma=200, trend_ma_fast=50, trend_floor=0.0)[0]),
        summarize('+ 波动率目标 15%(月频)', port(vol_target=0.15, rebalance_months=tuple(range(1, 13)))[0]),
        summarize('MA200 + 成本 10bps', port(trend_ma=200, trend_floor=0.0, cost_bps=0.001)[0]),
        summarize('MA200 + 成本 50bps', port(trend_ma=200, trend_floor=0.0, cost_bps=0.005)[0]),
    ]
    return rows


def run_extended_pool(prices, args, bond_factors=None):
    """扩资产池：黄金 + 纳指 + 红利低波 + 债（2013 年后才有黄金/纳指 ETF）。"""
    weights = {'518880.SH': 0.2, '513100.SH': 0.2, '512890.SH': 0.2, 'bond': 0.4}
    eq, _ = run_portfolio_v2(prices, weights, BOND_ANNUAL, dd_control=True,
                             min_stock=args.min_stock, dd_threshold=args.dd_threshold,
                             restore_dd=args.restore_dd, bond_factors=bond_factors)
    rows = [
        summarize('扩资产池(黄金+纳指+红利低波+债40%)', eq),
    ]
    return rows


def main():
    ap = argparse.ArgumentParser(description='资产配置变体研究（双均线/波动率目标/成本/扩资产池）')
    ap.add_argument('--start', default=DEFAULT_START)
    ap.add_argument('--end', default=DEFAULT_END)
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--dd-threshold', type=float, default=0.15)
    ap.add_argument('--min-stock', type=float, default=0.30)
    ap.add_argument('--restore-dd', type=float, default=None)
    ap.add_argument('--real-bond', action='store_true', help='用 SHIBOR 1w 真实利率')
    ap.add_argument('--oos-split', default=None, help='YYYYMMDD 研发/冻结切分')
    ap.add_argument('--extended', action='store_true', help='运行扩资产池变体（需拉取黄金/纳指 ETF）')
    args = ap.parse_args()

    # 主线只需要 000300.SH；扩资产池额外需要黄金/纳指/红利低波
    codes = ['000300.SH']
    if args.extended:
        codes += ['512890.SH', '518880.SH', '513100.SH']

    pro = get_tushare_pro()
    prices = load_prices(pro, codes, args.start, args.end, use_cache=not args.no_cache)
    bond_factors = build_bond_factors(pro, args.start, args.end) if args.real_bond else None

    if args.oos_split:
        split = str(args.oos_split)
        frozen = (datetime.strptime(split, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
        print(f'\n===== 研发期 {args.start} ~ {split} =====')
        print_table(run_main_variants(slice_prices(prices, codes, args.start, split), args, bond_factors))
        print(f'\n===== 冻结样本外 {frozen} ~ {args.end}（只验一次）=====')
        print_table(run_main_variants(slice_prices(prices, codes, frozen, args.end), args, bond_factors))
        return

    print_table(run_main_variants(prices, args, bond_factors))
    if args.extended:
        print('\n（扩资产池变体，窗口受黄金/纳指 ETF 上市日限制）')
        print_table(run_extended_pool(prices, args, bond_factors))


if __name__ == '__main__':
    main()
