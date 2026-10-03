# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
预注册检验：静态 60/40 中加入 20% 红利低波卫星
============================================================================
预注册文档：docs/knowledge/10-预注册-红利低波卫星.md（假设、区间、判定标准均以该文为准，本脚本只负责执行）。

S = 沪深300 40% + 红利低波 20% + 现金 40%
B = 沪深300 60% + 现金 40%（现行主线）
两者均 1/7 月首个交易日再平衡、单边 10bp、现金 SHIBOR 1w。

主检验区间 2014-01-01 ~ 2018-12-31（指数口径，优先全收益，拿不到则两腿都用价格指数）；
次要区间 2019-01-18 ~ 2026-09-30（510310 + 512890 ETF 复权价格，已污染，仅报告）。

用法：python dividend_lowvol_satellite.py
结果：stdout + output/research/dividend_lowvol_satellite.json
"""
import os
import sys
import json
import math

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import (get_tushare_pro, run_portfolio, summarize,
                                       build_bond_factors, BOND_ANNUAL)
from etf_selection_research import fetch_adj_close

PRIMARY = ('20140101', '20181231')
SECONDARY = ('20190118', '20260930')   # 512890 上市日起
COST = 0.001
OUT_FILE = os.path.join('output', 'research', 'dividend_lowvol_satellite.json')

# 主检验：(沪深300, 红利低波, 口径说明)；全收益优先，拿不到则两腿同时降级为价格指数
PRIMARY_SOURCES = [('H00300.CSI', 'H20269.CSI', '全收益'),
                   ('000300.SH', 'H30269.CSI', '价格（保守，不利于 S）')]

W_S = {'HS300': 0.4, 'DIVLV': 0.2, 'bond': 0.4}
W_B = {'HS300': 0.6, 'bond': 0.4}


def fetch_index(pro, code, start, end):
    try:
        df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
    except Exception as e:
        print(f'  ! {code} 拉取失败: {str(e)[:80]}')
        return {}
    if df is None or df.empty:
        print(f'  ! {code} 无数据')
        return {}
    return {str(r['trade_date']): float(r['close']) for _, r in df.sort_values('trade_date').iterrows()}


def run_pair(prices, factors, report_start=None):
    """返回 (S 净值, B 净值, 日期)；两者在同一组共同交易日上计算。"""
    common = sorted(set(prices['HS300']) & set(prices['DIVLV']))
    px = {k: {d: prices[k][d] for d in common} for k in ('HS300', 'DIVLV')}
    eq_s, dates = run_portfolio(px, W_S, BOND_ANNUAL, dd_control=False,
                                bond_factors=factors, cost_rate=COST)
    eq_b, dates_b = run_portfolio({'HS300': px['HS300']}, W_B, BOND_ANNUAL, dd_control=False,
                                  bond_factors=factors, cost_rate=COST)
    assert dates == dates_b
    return eq_s, eq_b, [d.strftime('%Y%m%d') for d in dates]


def monthly_returns(eq, dates):
    """每月最后一个交易日的净值 → 月收益列表。"""
    last = {}
    for e, d in zip(eq, dates, strict=True):
        last[d[:6]] = e
    vals = [last[m] for m in sorted(last)]
    return [b / a - 1 for a, b in zip(vals[:-1], vals[1:], strict=True)]


def t_stat(xs):
    n = len(xs)
    if n < 3:
        return float('nan')
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    return mu / sd * math.sqrt(n) if sd > 0 else float('nan')


def yearly(eq, dates):
    out = {}
    for y in sorted({d[:4] for d in dates}):
        seg = [e for e, d in zip(eq, dates, strict=True) if d[:4] == y]
        # 年收益以上年末净值为起点
        prev = [e for e, d in zip(eq, dates, strict=True) if d[:4] < y]
        start = prev[-1] if prev else seg[0]
        peak, mdd = start, 0.0
        for v in seg:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak)
        out[y] = (seg[-1] / start - 1, mdd)
    return out


def judge(s, b):
    c1 = s['sharpe'] > b['sharpe']
    c2 = s['max_drawdown'] <= b['max_drawdown'] + 0.02
    c3 = s['annual_return'] >= b['annual_return'] - 0.005
    return {'sharpe_higher': c1, 'drawdown_ok': c2, 'return_ok': c3, 'pass': c1 and c2 and c3}


def report(title, eq_s, eq_b, dates):
    s = summarize('S 40/20/40', eq_s)
    b = summarize('B 60/40', eq_b)
    print(f'\n========== {title}  {dates[0]} ~ {dates[-1]}（{len(dates)} 个交易日） ==========')
    print(f"{'方案':<14}{'累计收益':>10}{'年化':>8}{'最大回撤':>10}{'夏普':>8}")
    for r in (s, b):
        print(f"{r['variant']:<14}{r['total_return'] * 100:>9.1f}%{r['annual_return'] * 100:>7.2f}%"
              f"{r['max_drawdown'] * 100:>9.1f}%{r['sharpe']:>8.2f}")
    j = judge(s, b)
    print(f"判定：夏普更高 {'✓' if j['sharpe_higher'] else '✗'}  "
          f"回撤不差于 B+2pp {'✓' if j['drawdown_ok'] else '✗'}  "
          f"年化不低于 B−0.5pp {'✓' if j['return_ok'] else '✗'}  →  {'通过' if j['pass'] else '不通过'}")
    ms, mb = monthly_returns(eq_s, dates), monthly_returns(eq_b, dates)
    t = t_stat([a - c for a, c in zip(ms, mb, strict=True)])
    print(f'月度收益差 S−B 的 t 值：{t:.2f}（{len(ms)} 个月；仅报告，不作判定）')
    ys, yb = yearly(eq_s, dates), yearly(eq_b, dates)
    print(f"{'年份':<6}{'S 收益':>9}{'S 回撤':>9}{'B 收益':>9}{'B 回撤':>9}")
    for y in ys:
        print(f"{y:<6}{ys[y][0] * 100:>8.1f}%{ys[y][1] * 100:>8.1f}%{yb[y][0] * 100:>8.1f}%{yb[y][1] * 100:>8.1f}%")
    print(f"S 收益更高的年份 {sum(ys[y][0] > yb[y][0] for y in ys)}/{len(ys)}，"
          f"S 回撤更小的年份 {sum(ys[y][1] < yb[y][1] for y in ys)}/{len(ys)}")
    return {'S': s, 'B': b, 'judge': j, 'monthly_diff_t': t,
            'yearly': {y: {'S': ys[y], 'B': yb[y]} for y in ys}}


def main():
    pro = get_tushare_pro()
    result = {'prereg': 'docs/knowledge/10-预注册-红利低波卫星.md'}

    # 主检验
    start, end = PRIMARY
    factors = build_bond_factors(pro, start, end)
    if not factors:
        print('! SHIBOR 拉取失败，无法按预注册口径运行，终止')
        sys.exit(1)
    prices, basis = None, None
    for hs, dv, label in PRIMARY_SOURCES:
        a, b = fetch_index(pro, hs, start, end), fetch_index(pro, dv, start, end)
        if a and b and min(b) <= '20140110':
            prices, basis = {'HS300': a, 'DIVLV': b}, f'{label}（{hs} + {dv}）'
            break
        print(f'  - {label}口径数据不全，尝试下一种')
    if prices is None:
        print('! 主检验数据缺失，终止')
        sys.exit(1)
    print(f'主检验口径：{basis}')
    result['primary_basis'] = basis
    result['primary'] = report('主检验区间', *run_pair(prices, factors))

    # 次要区间（已污染，仅报告）
    start, end = SECONDARY
    factors2 = build_bond_factors(pro, start, end)
    hs, _ = fetch_adj_close(pro, '510310.SH', start, end)
    dv, _ = fetch_adj_close(pro, '512890.SH', start, end)
    if hs and dv and factors2:
        result['secondary'] = report('次要区间（已污染，仅报告）',
                                     *run_pair({'HS300': hs, 'DIVLV': dv}, factors2))
    else:
        print('\n! 次要区间数据缺失，跳过')

    p = result['primary']['judge']['pass']
    print('\n========== 结论（按预注册第 5 节） ==========')
    if p:
        print('主检验通过 → 新增 S 模拟盘，前向运行 ≥ 6 个月后才可考虑修改 IPS')
    elif basis.startswith('全收益'):
        print('主检验不通过（全收益口径）→ 记入证伪档案，主线保持静态 60/40')
    else:
        print('主检验不通过（价格口径）→ 结论不确定，仅在拿到全收益数据时按同一标准重跑')
    if 'secondary' in result and not any(v for k, v in result['secondary']['judge'].items() if k != 'pass'):
        print('注意：次要区间三条全部不满足，与已污染样本矛盾')

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    json.dump(result, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n结果已保存 -> {OUT_FILE}')


if __name__ == '__main__':
    main()
