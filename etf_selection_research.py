# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
静态 60/40 实盘工具选择研究（一次性）
============================================================================
回答 IPS（docs/knowledge/09-IPS草案.md）第 2 节的两个空：
  1. 股票腿用哪只沪深300 ETF：对比复权净值 vs 沪深300 全收益指数（H00300.CSI）的
     年化跟踪差（含管理费、托管费、分红处理）、跟踪误差、日均成交额。
  2. 现金腿用什么：场内货基 / 短融 ETF 的复权价格收益与最大回撤，国债逆回购 GC001 平均利率，
     与回测用的 SHIBOR 1w 对照。
  3. 用真实 ETF 价格重跑静态 60/40，与"指数 + SHIBOR"回测口径对比，量化回测高估了多少。

说明：
  - 511990（华宝添益）按份额结转收益、二级市场价格基本不涨，价格口径会严重低估，故不纳入；
    511880（银华日利）收益计入价格、年度分红由复权因子还原。
  - GC001 只给平均年化利率：逐日滚动的实际收益受计息天数规则影响，仅作参考，不进回测。
  - 任一数据拉取失败只跳过该项并打印原因，不中断。

用法：python etf_selection_research.py [--start 20231001 --end 20260930]
结果：stdout 表格 + output/research/etf_selection.json
"""
import os
import sys
import json
import math
import argparse

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import (get_tushare_pro, run_portfolio, summarize,
                                       build_bond_factors, BOND_ANNUAL)

STOCK_ETFS = {'510300.SH': '华泰柏瑞沪深300ETF', '510310.SH': '易方达沪深300ETF',
              '159919.SZ': '嘉实沪深300ETF'}
CASH_ETFS = {'511880.SH': '银华日利（货基）', '511360.SH': '海富通短融ETF'}
REPO = '204001.SH'
TR_INDEX = 'H00300.CSI'
OUT_FILE = os.path.join('output', 'research', 'etf_selection.json')


def fetch_adj_close(pro, code, start, end):
    """复权收盘价 {YYYYMMDD: close*adj_factor} 与日均成交额（亿元）；失败返回 (None, None)。"""
    try:
        df = pro.fund_daily(ts_code=code, start_date=start, end_date=end)
        adj = pro.fund_adj(ts_code=code, start_date=start, end_date=end)
    except Exception as e:
        print(f'  ! {code} 拉取失败: {str(e)[:80]}')
        return None, None
    if df is None or df.empty:
        print(f'  ! {code} 无行情数据')
        return None, None
    af = {}
    if adj is not None and not adj.empty:
        af = {str(r['trade_date']): float(r['adj_factor']) for _, r in adj.iterrows()}
    else:
        print(f'  ! {code} 无复权因子，按不复权价格计算（分红会被低估）')
    px = {}
    for _, r in df.iterrows():
        d = str(r['trade_date'])
        px[d] = float(r['close']) * af.get(d, 1.0)
    amt = df['amount'].astype(float).mean() / 1e5   # 千元 → 亿元
    return dict(sorted(px.items())), amt


def fetch_index(pro, code, start, end):
    df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
    return {str(r['trade_date']): float(r['close']) for _, r in df.sort_values('trade_date').iterrows()}


def daily_returns(px, dates):
    out = []
    for a, b in zip(dates[:-1], dates[1:], strict=True):
        out.append(px[b] / px[a] - 1)
    return out


def annualize(total, n_days):
    return (1 + total) ** (252 / n_days) - 1 if n_days > 0 else 0.0


def max_drawdown(values):
    peak, mdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


def tracking_stats(etf, idx):
    """在共同交易日上计算年化收益、年化跟踪差、跟踪误差。"""
    dates = sorted(set(etf) & set(idx))
    re = daily_returns(etf, dates)
    ri = daily_returns(idx, dates)
    n = len(re)
    ann_e = annualize(etf[dates[-1]] / etf[dates[0]] - 1, n)
    ann_i = annualize(idx[dates[-1]] / idx[dates[0]] - 1, n)
    diff = [a - b for a, b in zip(re, ri, strict=True)]
    mu = sum(diff) / n
    te = math.sqrt(sum((x - mu) ** 2 for x in diff) / (n - 1)) * math.sqrt(252)
    return {'start': dates[0], 'end': dates[-1], 'n_days': n, 'ann_return': ann_e,
            'index_ann_return': ann_i, 'tracking_diff': ann_e - ann_i, 'tracking_error': te}


def cash_factors(px, dates):
    """把现金工具价格转成 run_portfolio 的逐日因子；缺数据的日子记 1.0（不计息，保守）。"""
    out, prev = {}, None
    for d in dates:
        if prev is not None and d in px and prev in px:
            out[d] = px[d] / px[prev]
        else:
            out[d] = 1.0
        if d in px:
            prev = d
    return out


def static_6040(stock_px, factors):
    eq, _ = run_portfolio({'000300.SH': stock_px}, {'000300.SH': 0.6, 'bond': 0.4}, BOND_ANNUAL,
                          dd_control=False, bond_factors=factors, cost_rate=0.001)
    return eq


def main():
    ap = argparse.ArgumentParser(description='静态 60/40 实盘工具选择研究')
    ap.add_argument('--start', default='20231001')
    ap.add_argument('--end', default='20260930')
    args = ap.parse_args()
    pro = get_tushare_pro()
    print(f'研究窗口: {args.start} ~ {args.end}\n')
    result = {'window': [args.start, args.end], 'stock': {}, 'cash': {}, 'repo': None, 'backtest': []}

    idx = fetch_index(pro, TR_INDEX, args.start, args.end)
    print(f'  {TR_INDEX}: {len(idx)} 行')

    # 1. 股票腿
    print('\n========== 股票腿：沪深300 ETF（复权） vs 沪深300 全收益指数 ==========')
    print(f"{'代码':<11}{'名称':<16}{'年化收益':>9}{'指数年化':>9}{'年化跟踪差':>10}{'跟踪误差':>9}{'日均成交(亿)':>12}")
    stock_px = {}
    for code, name in STOCK_ETFS.items():
        px, amt = fetch_adj_close(pro, code, args.start, args.end)
        if not px:
            continue
        stock_px[code] = px
        st = tracking_stats(px, idx)
        st['avg_amount_yi'] = amt
        st['name'] = name
        result['stock'][code] = st
        print(f"{code:<11}{name:<16}{st['ann_return'] * 100:>8.2f}%{st['index_ann_return'] * 100:>8.2f}%"
              f"{st['tracking_diff'] * 100:>9.2f}%{st['tracking_error'] * 100:>8.2f}%{amt:>12.1f}")
    print('读法：跟踪差越接近 0（负得越少）越好；跟踪误差越小越稳；成交额越大，买卖价差和冲击越小。')

    # 2. 现金腿
    print('\n========== 现金腿 ==========')
    print(f"{'代码':<11}{'名称':<16}{'年化收益':>9}{'最大回撤':>9}{'日均成交(亿)':>12}")
    cash_px = {}
    for code, name in CASH_ETFS.items():
        px, amt = fetch_adj_close(pro, code, args.start, args.end)
        if not px:
            continue
        cash_px[code] = px
        ds = sorted(px)
        n = len(ds) - 1
        ann = annualize(px[ds[-1]] / px[ds[0]] - 1, n)
        mdd = max_drawdown([px[d] for d in ds])
        result['cash'][code] = {'name': name, 'ann_return': ann, 'max_drawdown': mdd,
                                'avg_amount_yi': amt, 'start': ds[0], 'end': ds[-1]}
        print(f"{code:<11}{name:<16}{ann * 100:>8.2f}%{mdd * 100:>8.2f}%{amt:>12.1f}")
    try:
        rp = pro.repo_daily(ts_code=REPO, start_date=args.start, end_date=args.end)
        col = 'weight' if 'weight' in rp.columns else 'close'
        avg = rp[col].astype(float).mean() / 100
        result['repo'] = {'code': REPO, 'avg_rate': avg, 'field': col}
        print(f"{REPO:<11}{'GC001 逆回购':<16}{avg * 100:>8.2f}%（{col} 均值，仅参考，不进回测）")
    except Exception as e:
        print(f'  ! {REPO} 拉取失败: {str(e)[:80]}')
    shibor = build_bond_factors(pro, args.start, args.end)
    if shibor:
        sh_ann = math.prod(shibor.values()) ** (252 / len(shibor)) - 1
        result['shibor_1w_ann'] = sh_ann
        print(f"{'SHIBOR 1w':<11}{'回测口径':<16}{sh_ann * 100:>8.2f}%")

    # 3. 真实工具重跑静态 60/40
    print('\n========== 静态 60/40（单边 10bp）：真实工具 vs 回测口径 ==========')
    dates = sorted(idx)
    rows = []
    base = static_6040(idx, {d: shibor.get(d, 1.0) for d in dates} if shibor else None)
    rows.append(('指数全收益 + SHIBOR 1w（回测口径）', base))
    for sc, spx in stock_px.items():
        sd = sorted(spx)
        for cc, cpx in cash_px.items():
            if min(cpx) > sd[0]:
                print(f'  - {cc} 上市晚于窗口起点，跳过与 {sc} 的组合')
                continue
            rows.append((f'{sc} + {cc}', static_6040(spx, cash_factors(cpx, sd))))
    print(f"{'组合':<36}{'累计收益':>10}{'年化':>8}{'最大回撤':>10}{'夏普':>8}")
    for name, eq in rows:
        s = summarize(name, eq)
        result['backtest'].append(s)
        print(f"{name:<36}{s['total_return'] * 100:>9.1f}%{s['annual_return'] * 100:>7.2f}%"
              f"{s['max_drawdown'] * 100:>9.1f}%{s['sharpe']:>8.2f}")

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    json.dump(result, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n结果已保存 -> {OUT_FILE}')


if __name__ == '__main__':
    main()
