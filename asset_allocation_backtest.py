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
from datetime import datetime, date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except Exception:
    pass

import tushare as ts

try:
    from config.tushare_config import get_tushare_pro
except Exception:
    def get_tushare_pro():
        """无本地 config 模块时的降级实现（CI 环境）。"""
        ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
        return ts.pro_api()

from core import metrics


DEFAULT_START = '20060101'
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
                  rebalance_months=(1, 7), initial=INITIAL_CAPITAL,
                  trend_ma=0, trend_floor=0.0, bond_factors=None,
                  report_start=None):
    """股债再平衡回测引擎。

    weights: {code或'bond': 目标权重}（和为 1）。
    dd_control: 回撤>dd_threshold 降股仓至 min_stock；
                restore_dd=None 时净值新高才恢复满仓，
                否则回撤收窄到 restore_dd 即恢复。
    trend_ma: >0 时启用均线趋势过滤（跌破 N 日均线降到 trend_floor）。
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
    trend_state = []
    if trend_ma > 0:
        closes = [prices[assets[0]][d.isoformat().replace('-', '')] for d in dates]
        for i in range(len(dates)):
            if i < trend_ma - 1:
                trend_state.append(True)
            else:
                ma = sum(closes[i - trend_ma + 1: i + 1]) / trend_ma
                trend_state.append(closes[i] >= ma)
    for i in range(start_i, len(dates)):
        d = dates[i]
        dstr = d.isoformat().replace('-', '')
        pcur = {a: prices[a][dstr] for a in assets}
        bond *= (bond_factors.get(dstr, BOND_DAILY_FACTOR) if bond_factors else BOND_DAILY_FACTOR)
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
        # 均线趋势过滤
        if trend_ma > 0 and i < len(trend_state):
            if not trend_state[i] and target_stock > trend_floor:
                target_stock = trend_floor
                trigger = True
            elif trend_state[i] and target_stock < full_stock:
                target_stock = full_stock
                trigger = True
        # 定期再平衡：每年 1/7 月首个交易日
        is_month_first = (i == start_i) or (dates[i - 1].month != d.month or dates[i - 1].year != d.year)
        if trigger or (is_month_first and d.month in rebalance_months):
            desired_stock = target_stock * total
            # 按目标权重重建持仓（从 0 恢复到满仓也必须能重建）
            sw = {a: weights[a] for a in assets}
            ssw = sum(sw.values())
            for a in assets:
                units[a] = desired_stock * (sw[a] / ssw) / pcur[a]
            bond = total - desired_stock
            trigger = False
        equity.append(sum(units[a] * pcur[a] for a in assets) + bond)
    if report_start:
        keep = [(d, e) for d, e in zip(dates[start_i:], equity)
                if d.isoformat().replace('-', '') >= report_start]
        return [e for _, e in keep], [d for d, _ in keep]
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


def build_bond_factors(pro, start, end):
    """用 SHIBOR 1w 真实日利率构造债券逐日收益因子，返回 {YYYYMMDD: 日因子}；失败返回 None。"""
    try:
        df = pro.shibor(start_date=start, end_date=end)
    except Exception as e:
        print(f'  ! SHIBOR 拉取失败，退回固定 3.5%: {str(e)[:80]}')
        return None
    if df is None or len(df) == 0:
        return None
    rate = {}
    for _, r in df.iterrows():
        try:
            rate[str(r['date'])] = float(r['1w']) / 100.0
        except Exception:
            pass
    last = 0.035
    out = {}
    for d in sorted(rate):
        last = rate[d]
        out[d] = (1 + last) ** (1 / 252)
    return out


def slice_prices(prices, codes, start, end):
    """截取各标的价格到 [start, end] 区间；YYYYMMDD 字符串可直接字典序比较。"""
    out = {}
    for c in codes:
        out[c] = {d: v for d, v in prices[c].items() if start <= d <= end}
    return out


def run_variants(prices, args, bond_factors=None):
    eq1, d1 = run_buyhold(prices, '000300.SH')
    eq2, d2 = run_portfolio(prices, {'000300.SH': 0.6, 'bond': 0.4},
                            BOND_ANNUAL, dd_control=False, bond_factors=bond_factors)
    eq3, d3 = run_portfolio(prices, {'000300.SH': 0.6, 'bond': 0.4},
                            BOND_ANNUAL, dd_control=True,
                            min_stock=args.min_stock, dd_threshold=args.dd_threshold,
                            restore_dd=args.restore_dd, bond_factors=bond_factors)
    eq4, d4 = run_portfolio(
        prices,
        {'000300.SH': 0.20, '000905.SH': 0.20, '512890.SH': 0.20, 'bond': 0.40},
        BOND_ANNUAL, dd_control=True,
        min_stock=args.min_stock, dd_threshold=args.dd_threshold,
        restore_dd=args.restore_dd, bond_factors=bond_factors)
    eq5, d5 = run_portfolio(prices, {'000300.SH': 0.6, 'bond': 0.4},
                            BOND_ANNUAL, dd_control=False,
                            trend_ma=200, trend_floor=0.0, bond_factors=bond_factors)
    return [
        summarize('纯持有沪深300', eq1),
        summarize('60/40 半年再平衡', eq2),
        summarize('60/40 + 控回撤 15%', eq3),
        summarize('核心-卫星(40%核心+20%红利低波+40%债)', eq4),
        summarize('60/40 + MA200趋势过滤', eq5),
    ]


def rolling_validate(prices, codes, bond_factors, first_year=2015, last_year=2024):
    """逐年滚动样本外验证：每一年用前一年做 MA200 warmup，外推检验当年。"""
    def perf(eq):
        if len(eq) < 2:
            return 0.0, 0.0
        per = metrics.compute(eq, initial_capital=INITIAL_CAPITAL)
        return per.total_return, per.max_drawdown
    print('\n========== 滚动样本外验证（逐年外推，MA200 vs 买入持有） ==========')
    print(f"{'年份':<6}{'MA200年收益':>11}{'MA200回撤':>10}{'买入收益':>10}{'买入回撤':>10}{'谁赢':>6}")
    print('-' * 58)
    rows = []
    wins = 0
    for y in range(first_year, last_year + 1):
        warm = f'{y - 1}0101'; end = f'{y}1231'; ys = f'{y}0101'
        eq_ma, _ = run_portfolio(slice_prices(prices, codes, warm, end),
                                {'000300.SH': 0.6, 'bond': 0.4}, BOND_ANNUAL,
                                dd_control=False, trend_ma=200, trend_floor=0.0,
                                bond_factors=bond_factors, report_start=ys)
        eq_bh, _ = run_buyhold(slice_prices(prices, ['000300.SH'], ys, end), '000300.SH')
        r_ma, dd_ma = perf(eq_ma)
        r_bh, dd_bh = perf(eq_bh)
        winner = 'MA200' if r_ma >= r_bh else '买入'
        if r_ma >= r_bh:
            wins += 1
        rows.append((y, r_ma, dd_ma, r_bh, dd_bh))
        print(f"{y:<6}{r_ma * 100:>10.1f}%{dd_ma * 100:>9.1f}%{r_bh * 100:>9.1f}%{dd_bh * 100:>9.1f}%{winner:>6}")
    n = len(rows)
    avg_ma = sum(r[1] for r in rows) / n
    avg_bh = sum(r[3] for r in rows) / n
    avg_dd_ma = sum(r[2] for r in rows) / n
    avg_dd_bh = sum(r[4] for r in rows) / n
    print('-' * 58)
    print(f"{'平均':<6}{avg_ma * 100:>10.1f}%{avg_dd_ma * 100:>9.1f}%{avg_bh * 100:>9.1f}%{avg_dd_bh * 100:>9.1f}%{'':>6}")
    print(f"\nMA200 跑赢买入持有的年份: {wins}/{n}")


def main():
    ap = argparse.ArgumentParser(description='指数增强+资产配置+控回撤 回测')
    ap.add_argument('--start', default=DEFAULT_START)
    ap.add_argument('--end', default=DEFAULT_END)
    ap.add_argument('--no-cache', action='store_true', help='不使用本地缓存')
    ap.add_argument('--dd-threshold', type=float, default=0.15, help='触发降仓的回撤阈值')
    ap.add_argument('--min-stock', type=float, default=0.30, help='降仓后的最低股票仓位')
    ap.add_argument('--restore-dd', type=float, default=None, help='回撤收窄到此值即恢复满仓')
    ap.add_argument('--real-bond', action='store_true', help='用 SHIBOR 1w 真实利率替代固定 3.5%% 债券收益')
    ap.add_argument('--oos-split', default=None, help='YYYYMMDD 样本内外切分：研发期 [--start,split]，冻结期 [split+1,--end]')
    ap.add_argument('--rolling', action='store_true', help='逐年滚动样本外验证（MA200 vs 买入持有）')
    args = ap.parse_args()

    codes = ['000300.SH', '000905.SH', '512890.SH']
    print(f'回测窗口: {args.start} ~ {args.end}' + ('，现金用 SHIBOR 真实利率' if args.real_bond else ''))
    print()
    pro = get_tushare_pro()
    prices = load_prices(pro, codes, args.start, args.end, use_cache=not args.no_cache)
    bond_factors = build_bond_factors(pro, args.start, args.end) if args.real_bond else None

    if args.rolling:
        rolling_validate(prices, codes, bond_factors, first_year=2015, last_year=2024)
        return

    if args.oos_split:
        split = str(args.oos_split)
        sd = datetime.strptime(split, '%Y%m%d') + timedelta(days=1)
        frozen_start = sd.strftime('%Y%m%d')
        print(f'\n========== 研发期 {args.start} ~ {split} ==========')
        print_table(run_variants(slice_prices(prices, codes, args.start, split), args, bond_factors))
        print(f'\n========== 冻结样本外 {frozen_start} ~ {args.end}（只验一次） ==========')
        print_table(run_variants(slice_prices(prices, codes, frozen_start, args.end), args, bond_factors))
        return

    rows = run_variants(prices, args, bond_factors)
    print_table(rows)
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    json.dump(rows, open(RESULT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'结果已保存 -> output/asset_allocation_results.json')


if __name__ == '__main__':
    main()
