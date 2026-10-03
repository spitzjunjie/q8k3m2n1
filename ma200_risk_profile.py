# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MA200 风险画像：把"这套规则最难熬的时刻"量化出来，回填知识库的预期痛苦表与案例库。
============================================================================
只描述历史、不选参数：规则固定为沪深300 收盘 vs 200 日均线（与主线一致）。
输出：
  - 每年翻转次数、短命信号（< SHORT_LIVED 个交易日即反转）次数及其累计损耗
  - 最长连续空仓、空仓期间错过的最大涨幅
  - 最长"跑输买入持有"持续期（相对净值回撤）
  - 关键事件日期附近的信号状态（2015 股灾 / 2016 熔断 / 2020-03 / 2024-02 / 2024-09-24）
结果写 output/ma200_risk_profile.json，并打印 Markdown 表格（可直接贴进 Obsidian）。

用法：
    python ma200_risk_profile.py                       # 默认 2006-2024
    python ma200_risk_profile.py --start 20060101 --end 20260930
"""
import os
import sys
import json
import argparse

sys.stdout.reconfigure(encoding='utf-8')

MA = 200
SHORT_LIVED = 20
EVENTS = {
    '2015 股灾起点': '20150615',
    '2016 熔断首日': '20160104',
    '2020 新冠急跌': '20200323',
    '2024 微盘股危机': '20240205',
    '2024 9·24 行情': '20240924',
    '2024 9·24 后高点': '20241008',
}
RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'ma200_risk_profile.json')


def signals(dates, closes, ma=MA):
    """逐日信号：True=持有（收盘 ≥ MA），False=空仓；前 ma-1 日为 None。"""
    out = []
    for i in range(len(closes)):
        if i < ma - 1:
            out.append(None)
        else:
            out.append(closes[i] >= sum(closes[i - ma + 1: i + 1]) / ma)
    return out


def segments(dates, sigs):
    """把信号序列切成连续段：[(state, 起始下标, 结束下标)]，忽略 None。"""
    segs = []
    for i, s in enumerate(sigs):
        if s is None:
            continue
        if segs and segs[-1][0] == s and segs[-1][2] == i - 1:
            segs[-1] = (s, segs[-1][1], i)
        else:
            segs.append((s, i, i))
    return segs


def profile(dates, closes, ma=MA, short_lived=SHORT_LIVED):
    sigs = signals(dates, closes, ma)
    segs = segments(dates, sigs)

    flips_by_year = {}
    for k in range(1, len(segs)):
        y = dates[segs[k][1]][:4]
        flips_by_year[y] = flips_by_year.get(y, 0) + 1

    # 短命信号：一段持续 < short_lived 日就反转（首尾段不算，因为不知完整长度）
    short = []
    for s, a, b in segs[1:-1]:
        n = b - a + 1
        if n < short_lived:
            # 打脸损耗（正数=亏）：段首日收盘按新信号成交，次段首日（b+1）收盘反向成交。
            # 持有段 = 买入后又低价卖出的亏损；空仓段 = 卖出后又高价买回的差价。
            move = closes[b + 1] / closes[a] - 1
            loss = -move if s else move
            short.append({'state': 'hold' if s else 'cash', 'start': dates[a],
                          'end': dates[b], 'days': n, 'whipsaw_loss': round(loss, 4)})

    cash_segs = [(a, b) for s, a, b in segs if not s]
    longest_cash = max(cash_segs, key=lambda x: x[1] - x[0], default=None)
    # 错过的涨幅：空仓段内最低收盘 → 重新入场日收盘（含入场日，那一天的涨幅也没吃到）
    missed = []
    for a, b in cash_segs:
        end = min(b + 1, len(closes) - 1)
        lo = min(closes[a:b + 1])
        lo_i = closes.index(lo, a, b + 1)
        missed.append((max(closes[lo_i:end + 1]) / lo - 1, dates[a], dates[b]))
    worst_missed = max(missed, default=None)

    # 相对净值：纯择时（持有日 100% 吃指数收益、空仓日 0，不计现金利息）÷ 买入持有
    rel, peak, peak_i, worst = 1.0, 1.0, 0, (0, None, None)
    first = next((i for i, s in enumerate(sigs) if s is not None), None)
    for i in range(first + 1 if first is not None else len(closes), len(closes)):
        bh = closes[i] / closes[i - 1]
        strat = bh if sigs[i - 1] else 1.0
        rel *= strat / bh
        if rel >= peak:
            peak, peak_i = rel, i
        elif i - peak_i > worst[0]:
            worst = (i - peak_i, dates[peak_i], dates[i])

    event_state = {}
    for name, d in EVENTS.items():
        idx = next((i for i, x in enumerate(dates) if x >= d), None)
        if idx is None or sigs[idx] is None:
            continue
        seg = next(sg for sg in segs if sg[1] <= idx <= sg[2])
        event_state[name] = {'date': dates[idx], 'state': 'hold' if sigs[idx] else 'cash',
                             'state_since': dates[seg[1]], 'state_until': dates[seg[2]]}

    years = sorted({d[:4] for d, s in zip(dates, sigs, strict=True) if s is not None})
    return {
        'n_flips': len(segs) - 1,
        'flips_by_year': {y: flips_by_year.get(y, 0) for y in years},
        'max_flips_in_year': max((flips_by_year.get(y, 0) for y in years), default=0),
        'short_lived': short,
        'short_lived_per_year': round(len(short) / max(len(years), 1), 2),
        'short_lived_total_loss': round(sum(x['whipsaw_loss'] for x in short), 4),
        'short_lived_loss_rate': round(sum(x['whipsaw_loss'] > 0 for x in short) / max(len(short), 1), 3),
        'longest_cash': None if longest_cash is None else {
            'days': longest_cash[1] - longest_cash[0] + 1,
            'start': dates[longest_cash[0]], 'end': dates[longest_cash[1]]},
        'worst_missed_rally_in_cash': None if worst_missed is None else {
            'gain': round(worst_missed[0], 4), 'start': worst_missed[1], 'end': worst_missed[2]},
        'longest_underperformance_vs_bh': {'days': worst[0], 'from': worst[1], 'to': worst[2]},
        'events': event_state,
    }


def print_markdown(p):
    print('\n| 指标 | 历史值 |\n|---|---|')
    lc, wm, lu = p['longest_cash'], p['worst_missed_rally_in_cash'], p['longest_underperformance_vs_bh']
    if lc:
        print(f"| 最长连续空仓 | {lc['days']} 个交易日（{lc['start']} ~ {lc['end']}） |")
    if wm:
        print(f"| 空仓期间错过的最大涨幅 | {wm['gain'] * 100:.1f}%（空仓段 {wm['start']} ~ {wm['end']}） |")
    print(f"| 最长跑输买入持有（纯择时相对净值未创新高） | {lu['days']} 个交易日（{lu['from']} ~ {lu['to']}） |")
    print(f"| 总翻转次数 / 单年最多 | {p['n_flips']} / {p['max_flips_in_year']} |")
    print(f"| 短命信号（<{SHORT_LIVED} 日反转）年均 | {p['short_lived_per_year']} 次 |")
    print(f"| 短命信号累计打脸损耗 | {p['short_lived_total_loss'] * 100:+.1f}%（正=亏，简单加总，"
          f"其中 {p['short_lived_loss_rate'] * 100:.0f}% 的短命信号是亏的） |")
    print('\n| 年份 | 翻转次数 |\n|---|---|')
    for y, n in p['flips_by_year'].items():
        print(f'| {y} | {n} |')
    print('\n| 事件 | 当日信号 | 该状态起止 |\n|---|---|---|')
    for name, e in p['events'].items():
        print(f"| {name}（{e['date']}） | {e['state']} | {e['state_since']} ~ {e['state_until']} |")


def main():
    from asset_allocation_backtest import load_prices, get_tushare_pro
    ap = argparse.ArgumentParser(description='MA200 风险画像（只描述历史，不选参）')
    ap.add_argument('--start', default='20050101', help='含 MA200 预热期')
    ap.add_argument('--end', default='20241231')
    ap.add_argument('--no-cache', action='store_true')
    args = ap.parse_args()
    pro = get_tushare_pro()
    px = load_prices(pro, ['000300.SH'], args.start, args.end, use_cache=not args.no_cache)['000300.SH']
    dates = sorted(px)
    p = profile(dates, [px[d] for d in dates])
    print_markdown(p)
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    json.dump(p, open(RESULT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n结果已保存 -> output/{os.path.basename(RESULT_FILE)}')


if __name__ == '__main__':
    main()
