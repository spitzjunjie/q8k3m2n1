# -*- coding: utf-8 -*-
#!/usr/bin/env python3
'''
指数增强 + 资产配置 + 控回撤 · 回测脚本
============================================================================
复现《资产配置方案.md》的股债再平衡回测·参考数字：
    纯持有沪深300 → -3.7% / 回撤 45.6%
    60/40 半年再平衡 → +10.7% / 回撤 26.7%
    60/40 + 控回撤15% → +10.5% / 回撤 19.7%

债券按固定年化 3.5%（货币基金近似）日复利。
数据来源：Tushare pro.index_daily / fund_daily（本地缓存）。

用法：
    python asset_allocation_backtest.py                  # 默认 2018-2024
    python asset_allocation_backtest.py --start 20180101 --end 20241231
    python asset_allocation_backtest.py --no-cache
'''

import os
import sys
import json
import argparse
from datetime import datetime, date

sys.stdout.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except Exception:
    pass

from config.tushare_config import get_tushare_pro
from core import metrics


DEFAULT_START = '20180101'
DEFAULT_END = '20241231'
BOND_ANNUAL = 0.035          # 债券/货币基金年化回报（固定假设）
BOND_DAILY_FACTOR = (1 + BOND_ANNUAL) ** (1 / 252)
INITIAL_CAPITAL = 100.0
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'index_cache.json')
RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'asset_allocation_results.json')


def load_prices(pro, codes, start, end, use_cache=True):
    """拉取指数/ETF 日收盘价，返回 {code: {YYYYMMDD: close}}。本地缓存。"""
    key = f'{start}-{end}'
    cache = {}
    if use_cache and os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE, encoding='utf-8'))
        except Exception:
            cache = {}
    result = {}
    for code in codes:
        hit = cache.get(key, {}).get(code)
        if hit:
            result[code] = hit
            print(f'  缓存命中 {code}: {len(hit)} 行')
            continue
        print(f'  拉取 {code} ...')
        if code.endswith('.SH') and code[0] == '5':
            df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)
        else:
            df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            print(f'    ! {code} 无数据')
            result[code] = {}
            continue
        df = df.sort_values('trade_date')
        result[code] = {row['trade_date']: float(row['close']) for _, row in df.iterrows()}
        print(f'    {code}: {len(result[code])} 行 ({min(result[code])} -> {max(result[code])})')
    if use_cache:
        cache.setdefault(key, {}).update(result)
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        json.dump(cache, open(CACHE_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    return result

def _common_dates(prices, codes):
    """所有资产都有的交易日（交集）。"""
    s = None
    for c in codes:
        if s is None:
            s = set(prices[c].keys())
        else:
            s &= set(prices[c].keys())
    return [datetime.strptime(d, '%Y%m%d').date() for d in sorted(s)]


def run_portfolio(prices, weights, bond_annual, dd_control,
                  min_stock=0.30, dd_threshold=0.15, restore_dd=None,
                  rebalance_months=(1, 7), initial=INITIAL_CAPITAL):
    """股债再平衡回测引擎。

    weights: {code或'bond': 目标权重}（和为 1）。
    dd_control: 回撤>dd_threshold 降股仓至 min_stock；
                restore_dd=None 时净值新高才恢复满仓，
                否则回撤收窄到 restore_dd 即恢复。
    返回 (equity_curve, 日期列表)。
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
    for i in range(start_i, len(dates)):
        d = dates[i]
        dstr = d.isoformat().replace('-', '')
        pcur = {a: prices[a][dstr] for a in assets}
        bond *= BOND_DAILY_FACTOR
        stock_total = sum(units[a] * pcur[a] for a in assets)
        total = stock_total + bond
        # 控回撤
        if dd_control:
            if total > peak:
                peak = total
            dd = (peak - total) / peak if peak > 0 else 0.0
            if target_stock == full_stock and dd > dd_threshold:
                target_stock = min_stock
                trigger = True
            elif target_stock == min_stock:
                restored = (
                    (restore_dd is not None and dd <= restore_dd)
                    or (restore_dd is None and total >= peak - 1e-9)
                )
                if restored:
                    target_stock = full_stock
                    trigger = True
        # 定期再平衡：每年 1/7 月首个交易日
        is_month_first = (i == start_i) or (dates[i - 1].month != d.month or dates[i - 1].year != d.year)
        if trigger or (is_month_first and d.month in rebalance_months):
            desired_stock = target_stock * total
            if stock_total > 0:
                scale = desired_stock / stock_total
                for a in assets:
                    units[a] *= scale
            bond = total - desired_stock
            trigger = False
        equity.append(sum(units[a] * pcur[a] for a in assets) + bond)
    return equity, dates[start_i:]


def run_buyhold(prices, code, initial=INITIAL_CAPITAL):
    """纯持有某个指数的基准。"""
    dates = _common_dates(prices, [code])
    un = None
    eq = []
    for d in dates:
        p = prices[code][d.isoformat().replace('-', '')]
        if un is None:
            un = initial / p
        eq.append(un * p)
    return eq, dates


def fmt_pct(x):
    return f'{x * 100:+.1f}%' if x is not None else 'N/A'


def summarize(name, eq):
    per = metrics.compute(eq, initial_capital=INITIAL_CAPITAL)
    return {
        'variant': name,
        'n_days': per.n_days,
        'total_return': per.total_return,
        'annual_return': per.annual_return,
        'max_drawdown': per.max_drawdown,
        'sharpe': per.sharpe,
        'sortino': per.sortino,
    }


def print_table(rows):
    print()
    print('=' * 74)
    print(f"{'方案':<30}{'累计收益':>10}{'年化':>8}{'最大回撤':>10}{'夏普':>8}")
    print('-' * 74)
    for r in rows:
        print(f"{r['variant']:<30}{fmt_pct(r['total_return']):>10}"
              f"{fmt_pct(r['annual_return']):>8}{fmt_pct(r['max_drawdown']):>10}"
              f"{r['sharpe']:>8.2f}")
    print('=' * 74)


def main():
    ap = argparse.ArgumentParser(description='指数增强+资产配置+控回撤 回测')
    ap.add_argument('--start', default=DEFAULT_START)
    ap.add_argument('--end', default=DEFAULT_END)
    ap.add_argument('--no-cache', action='store_true', help='不使用本地缓存')
    ap.add_argument('--dd-threshold', type=float, default=0.15,
                    help='回撤触发降仓阈值（默认0.15）')
    ap.add_argument('--min-stock', type=float, default=0.30,
                    help='降仓后的股票仓位（默认0.30）')
    ap.add_argument('--restore-dd', type=float, default=None,
                    help='回撤收窄到该阈值即恢复满仓（默认None=净值新高才恢复）')
    args = ap.parse_args()

    codes = ['000300.SH', '000905.SH', '512890.SH']
    print(f'回测窗口: {args.start} ~ {args.end}')
    print()
    pro = get_tushare_pro()
    prices = load_prices(pro, codes, args.start, args.end, use_cache=not args.no_cache)

    # V1 基准：纯持有沪深300
    eq1, d1 = run_buyhold(prices, '000300.SH')
    # V2：60/40 半年再平衡
    eq2, d2 = run_portfolio(prices, {'000300.SH': 0.6, 'bond': 0.4},
                            BOND_ANNUAL, dd_control=False)
    # V3：60/40 + 控回撤
    eq3, d3 = run_portfolio(prices, {'000300.SH': 0.6, 'bond': 0.4},
                            BOND_ANNUAL, dd_control=True,
                            min_stock=args.min_stock,
                            dd_threshold=args.dd_threshold,
                            restore_dd=args.restore_dd)
    # V4（扩展）：核心-卫星（沪深300+中证500+红利低波 + 债券）
    eq4, d4 = run_portfolio(
        prices,
        {'000300.SH': 0.20, '000905.SH': 0.20, '512890.SH': 0.20, 'bond': 0.40},
        BOND_ANNUAL, dd_control=True,
        min_stock=args.min_stock,
        dd_threshold=args.dd_threshold,
        restore_dd=args.restore_dd)

    rows = [
        summarize('纯持有沪深300', eq1),
        summarize('60/40 半年再平衡', eq2),
        summarize('60/40 + 控回撤 15%', eq3),
        summarize('核心-卫星(40%核心+20%红利低波+40%债)', eq4),
    ]
    print_table(rows)

    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    json.dump(rows, open(RESULT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'结果已保存 -> output/asset_allocation_results.json')


if __name__ == '__main__':
    main()
