# -*- coding: utf-8 -*-
#!/usr/bin/env python3
'''三指数动量轮动（沪深300/中证500/红利低波 + 双动量现金保护）· 回测
============================================================================
设计文档: docs/superpowers/specs/2026-08-26-momentum-rotation-design.md（预注册协议）

用法:
    python momentum_rotation_backtest.py --dev                     # 研发期 2006-2016，三参数对比选 N
    python momentum_rotation_backtest.py --frozen --lookback 6     # 冻结期 2017-2024（只跑一次）
    python momentum_rotation_backtest.py --frozen --lookback 6 --permutation   # 冻结期 + 置换检验
'''
import os
import sys
import json
import argparse
import random

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import (
    BOND_ANNUAL, BOND_DAILY_FACTOR,
    build_bond_factors, slice_prices, summarize, print_table, fmt_pct,
    run_buyhold, run_portfolio,
)

RISK_ASSETS = ['000300.SH', '000905.SH', 'H30269.CSI']
ASSET_NAMES = {'000300.SH': '沪深300', '000905.SH': '中证500', 'H30269.CSI': '红利低波'}
LOOKBACKS = [3, 6, 12]           # 候选动量回看期（月），研发期三选一
COST_RATE = 0.001                # 单边成本 0.1%
INITIAL = 100.0
FETCH_START = '20050101'         # 12 个月 lookback 的预热 + MA200 参照的 200 日预热
DEV_END, FROZEN_END = '20161231', '20241231'
DEV_REPORT, FROZEN_REPORT = '20060101', '20170101'
PERM_N = 1000
PERM_SEED = 20260826
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(_MODULE_DIR, 'output', 'momentum_rotation_results.json')


def month_end_indices(dates):
    '''每个月最后一个交易日在 dates（升序 YYYYMMDD 字符串）里的下标。'''
    out = []
    for i, d in enumerate(dates):
        if i == len(dates) - 1 or d[:6] != dates[i + 1][:6]:
            out.append(i)
    return out


def cash_index_series(dates, cash_factors):
    '''现金净值序列（首日=1.0），逐日乘 SHIBOR 因子；缺失日回退固定 3.5% 年化。'''
    out = [1.0]
    for i in range(1, len(dates)):
        f = cash_factors.get(dates[i], BOND_DAILY_FACTOR) if cash_factors else BOND_DAILY_FACTOR
        out.append(out[-1] * f)
    return out


def select_assets(close, dates, lookback_months, cash_idx):
    '''每个月末收盘算 N 个月动量，选出下月持仓（'code'|'cash'），与月末列表对齐。

    相对动量：三资产当月月末收盘 / N 个自然月前月末收盘 - 1，最高者胜。
    绝对动量：胜者收益 <= 现金同期收益 → 现金。
    '''
    me = month_end_indices(dates)
    holdings = []
    for k, idx in enumerate(me):
        d_cur = dates[idx]
        y, m = int(d_cur[:4]), int(d_cur[4:6])
        tm, ty = m - lookback_months, y
        while tm <= 0:
            tm += 12
            ty -= 1
        prefix = f'{ty:04d}{tm:02d}'
        past = [i for i in me[:k] if dates[i][:6] == prefix]
        if not past:
            holdings.append('cash')          # 历史不足 N 个月
            continue
        i0 = past[-1]
        best = 'cash'
        best_ret = cash_idx[idx] / cash_idx[i0] - 1   # 现金同期收益 = 绝对动量门槛
        for code in RISK_ASSETS:
            r = close[code][d_cur] / close[code][dates[i0]] - 1
            if r > best_ret:
                best, best_ret = code, r
        holdings.append(best)
    return holdings
