# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MA200 模拟盘（paper trading）v2：每日记账，前向验证。
===========================================================
规则与回测同构：沪深300 收盘 vs 200 日均线判断信号，60/40 股债。
v2 口径（见 docs/knowledge/01-回测与实盘口径对照.md）：
  - 收盘判断、**次日开盘**执行（v1 在同一收盘价成交，实盘做不到）
  - 非股票部分按 SHIBOR 1w 逐日计息（v1 为零收益现金）；拉取失败沿用上次利率，再退回 1.4%
  - 每次调仓单边成本 0.1%（与动量轮动 spec 一致的保守值）
  - 持有期间 1/7 月首个交易日开盘再平衡回 60%（与回测一致）
  - 每次运行回放所有未记账的交易日（v1 漏跑的日子不会再丢）
状态持久化到 output/ma200_paper_state.json；v1 状态首次运行时归档为 ma200_paper_state_v1.json。
用法：python ma200_paper_trade.py
"""
import os, sys, json, shutil
from datetime import datetime, timedelta
from ma200_common import MA, get_pro, fetch_hs300, fetch_shibor_1w
sys.stdout.reconfigure(encoding='utf-8')

STATE_FILE = os.path.join('output', 'ma200_paper_state.json')
STATE_FILE_V1 = os.path.join('output', 'ma200_paper_state_v1.json')
VERSION = 2
STOCK_PCT = 0.6
INITIAL = 100000.0
COST_RATE = 0.001             # 单边成本（佣金+价差+开盘竞价偏差，保守值）
CASH_FALLBACK_ANNUAL = 0.014  # SHIBOR 1w 2026-09 约 1.37%~1.41%；不再用旧的 3.5%
REBALANCE_MONTHS = (1, 7)


def new_state(start=None):
    return {'version': VERSION, 'start': start, 'units': 0.0, 'cash': INITIAL,
            'target': None, 'pending': None, 'cash_rate': None, 'total_cost': 0.0,
            'history': []}


def build_bars(df, ma=MA):
    """DataFrame(trade_date, open, close) → [{date, open, close, ma}]；前 ma-1 天 ma 为 None。"""
    dates = df['trade_date'].astype(str).tolist()
    opens = df['open'].astype(float).tolist()
    closes = df['close'].astype(float).tolist()
    bars = []
    for i, d in enumerate(dates):
        m = sum(closes[i - ma + 1: i + 1]) / ma if i >= ma - 1 else None
        bars.append({'date': d, 'open': opens[i], 'close': closes[i], 'ma': m})
    return bars


def rate_on(rates, d, fallback):
    """取 d 当日或之前最近一个已发布的利率；都没有则用 fallback。"""
    known = [k for k in rates if k <= d]
    return rates[max(known)] if known else fallback


def process_day(state, bar, cash_rate):
    """处理一个交易日：计息 → 开盘执行挂单/再平衡 → 收盘估值 → 收盘出信号挂单。原地修改 state。"""
    d, op, cl, ma = bar['date'], bar['open'], bar['close'], bar['ma']
    if ma is None:
        raise ValueError(f'{d} 均线窗口不足 {MA} 日，无法记账')
    history = state['history']
    prev_date = history[-1]['date'] if history else None
    if history:
        state['cash'] *= (1 + cash_rate) ** (1 / 252)
    state['cash_rate'] = cash_rate

    order, reason = state['pending'], 'signal'
    if order is None and state['target'] and prev_date and prev_date[4:6] != d[4:6] \
            and int(d[4:6]) in REBALANCE_MONTHS:
        order, reason = state['target'], 'rebalance'
    trade = None
    if order is not None:
        stock_val = state['units'] * op
        equity_open = stock_val + state['cash']
        desired = order * equity_open
        cost = abs(desired - stock_val) * COST_RATE
        state['units'] = desired / op
        state['cash'] = equity_open - desired - cost
        state['total_cost'] += cost
        state['target'] = order
        state['pending'] = None
        trade = {'reason': reason, 'price': op, 'to': order, 'cost': round(cost, 2)}

    equity = state['units'] * cl + state['cash']
    signal = 'hold' if cl >= ma else 'cash'
    want = STOCK_PCT if signal == 'hold' else 0.0
    if want != state['target']:
        state['pending'] = want

    rec = {'date': d, 'open': op, 'close': cl, 'ma': round(ma, 2), 'signal': signal,
           'position': state['target'] or 0.0, 'cash_rate': cash_rate,
           'equity': round(equity, 2)}
    if trade:
        rec['trade'] = trade
    history.append(rec)
    return rec


def replay(state, bars, rates, fallback=CASH_FALLBACK_ANNUAL):
    """回放 start 之后、尚未记账的全部交易日，返回新记账条数。"""
    last = state['history'][-1]['date'] if state['history'] else None
    todo = [b for b in bars
            if (state['start'] is None or b['date'] >= state['start'])
            and (last is None or b['date'] > last)]
    for b in todo:
        prev = state['cash_rate'] if state['cash_rate'] is not None else fallback
        process_day(state, b, rate_on(rates, b['date'], prev))
    return len(todo)


def load_state():
    """读取 v2 状态；遇到 v1 状态则归档并以原起始日开一个 v2 新账本（按新口径回放）。"""
    if not os.path.exists(STATE_FILE):
        return new_state()
    try:
        old = json.load(open(STATE_FILE, encoding='utf-8'))
    except Exception:
        return new_state()
    if old.get('version') == VERSION:
        return old
    if not os.path.exists(STATE_FILE_V1):
        shutil.copyfile(STATE_FILE, STATE_FILE_V1)
        print(f'检测到 v1 状态，已归档到 {STATE_FILE_V1}，按 v2 口径从 {old.get("start")} 起回放')
    return new_state(old.get('start'))


def main():
    pro = get_pro()
    df = fetch_hs300(pro)
    bars = build_bars(df)
    if not bars or bars[-1]['ma'] is None:
        print(f'数据不足 {MA} 日，无法判断信号')
        return
    state = load_state()
    if state['start'] is None:
        state['start'] = bars[-1]['date']
    first = state['history'][-1]['date'] if state['history'] else state['start']
    rate_start = (datetime.strptime(first, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
    rates = fetch_shibor_1w(pro, rate_start, bars[-1]['date'])
    n = replay(state, bars, rates)
    if n == 0:
        last = state['history'][-1]
        print(f"今日({last['date']})已记账：净值 {last['equity']:,.2f}，仓位 {last['position'] * 100:.0f}%"
              f"（重复运行同一交易日会自动跳过）")
        return
    os.makedirs('output', exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    history = state['history']
    last = history[-1]
    equity = last['equity']
    peak = max(h['equity'] for h in history)
    dd = (peak - equity) / peak if peak > 0 else 0.0
    label = '持有（60%股票）' if last['signal'] == 'hold' else '空仓（全现金）'
    pend = state['pending']
    print(f"本次补记 {n} 个交易日")
    print(f"日期: {last['date']}  信号: {label}")
    print(f"沪深300收盘: {last['close']:.2f}  MA200: {last['ma']:.2f}")
    print(f"组合净值: {equity:,.2f}  累计收益: {(equity / INITIAL - 1) * 100:+.2f}%  当前回撤: {dd * 100:.2f}%")
    print(f"当前仓位: {last['position'] * 100:.0f}%  现金年化: {last['cash_rate'] * 100:.2f}%  "
          f"累计成本: {state['total_cost']:,.2f}")
    if pend is not None:
        print(f"挂单: 下一交易日开盘调到 {pend * 100:.0f}% 股票")
    print(f"起始: {state['start']}  记录天数: {len(history)}")


if __name__ == '__main__':
    main()
