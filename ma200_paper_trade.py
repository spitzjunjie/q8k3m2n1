# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MA200 模拟盘（paper trading）：每日记账，前向验证。
===========================================================
用沪深300 收盘 vs 200 日均线判断信号；按 60/40 股债规则在信号切换日重建仓位。
每天跑一次：python ma200_paper_trade.py
状态持久化到 output/ma200_paper_state.json，可重复运行（同一天不重复记账）；
漏跑或当天数据未出导致缺失的交易日，下次运行会自动补记。
"""
import os, sys, json
from ma200_common import MA, get_pro, fetch_hs300, signal_state
sys.stdout.reconfigure(encoding='utf-8')

STATE_FILE = os.path.join('output', 'ma200_paper_state.json')
STOCK_PCT = 0.6
INITIAL = 100000.0


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding='utf-8'))
        except Exception:
            pass
    return {'position': None, 'shares': 0.0, 'cash': INITIAL, 'start': None, 'history': []}


def rebuild_state(history):
    """按历史记录重放出 shares/cash：仓位只在切换日按当日收盘重建，其余日子持仓不变。"""
    state = {'position': None, 'shares': 0.0, 'cash': INITIAL, 'start': None, 'history': []}
    for h in history:
        if state['position'] is None or state['position'] != h['position']:
            state['shares'] = h['equity'] * h['position'] / h['close']
            state['cash'] = h['equity'] * (1 - h['position'])
            state['position'] = h['position']
            state['start'] = state['start'] or h['date']
    state['history'] = list(history)
    return state


def record_day(state, st):
    """按某个交易日的信号记一条账（必要时在当日收盘重建仓位）。"""
    d, close, sig = st['date'], st['close'], st['signal']
    target = STOCK_PCT if sig == 'hold' else 0.0
    # 首次建仓或信号切换：在当日收盘按目标仓位重建
    if state['position'] is None or state['position'] != target:
        equity = state['shares'] * close + state['cash']
        state['shares'] = equity * target / close
        state['cash'] = equity * (1 - target)
        state['position'] = target
        state['start'] = state.get('start') or d
    equity = state['shares'] * close + state['cash']
    state['history'].append({'date': d, 'close': close, 'ma': round(st['ma'], 2),
                             'signal': sig, 'position': state['position'], 'equity': round(equity, 2)})


def main():
    pro = get_pro()
    df = fetch_hs300(pro)
    st = signal_state(df)
    if st is None:
        print('数据不足 200 日，无法判断信号')
        return
    # 每个可算 MA200 的交易日 -> 当日信号
    days = [signal_state(df.iloc[:i + 1]) for i in range(MA - 1, len(df))]
    state = load_state()
    history = state.get('history', [])
    if not history:
        record_day(state, st)
    else:
        # 定时任务可能延迟/跳过，或运行时当天数据尚未发布：找出起始日之后、
        # 历史里缺的交易日，从最早缺口处截断并按日重放，保证每个交易日都有一条记录
        recorded = {h['date'] for h in history}
        first = history[0]['date']
        missing = [x['date'] for x in days if x['date'] > first and x['date'] not in recorded]
        if not missing:
            last = history[-1]
            print(f"今日({st['date']})已记账：净值 {last['equity']:,.2f}，仓位 {last.get('position', 0) * 100:.0f}%"
                  f"（重复运行同一交易日会自动跳过）")
            return
        gap = missing[0]
        state = rebuild_state([h for h in history if h['date'] < gap])
        replayed = [x for x in days if x['date'] >= gap]
        for x in replayed:
            record_day(state, x)
        print(f"补记缺失交易日: {', '.join(missing)}（自 {gap} 起按日重放 {len(replayed)} 天）")
    history = state['history']
    os.makedirs('output', exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    last = history[-1]
    equity, sig = last['equity'], last['signal']
    ret = equity / INITIAL - 1
    peak = max(h['equity'] for h in history)
    dd = (peak - equity) / peak if peak > 0 else 0.0
    label = '持有（60%股票）' if sig == 'hold' else '空仓（全现金）'
    print(f"日期: {last['date']}  信号: {label}")
    print(f"沪深300收盘: {last['close']:.2f}  MA200: {last['ma']:.2f}")
    print(f"组合净值: {equity:,.2f}  累计收益: {ret * 100:+.2f}%  当前回撤: {dd * 100:.2f}%")
    print(f"当前仓位: {state['position'] * 100:.0f}%  起始: {state['start']}  记录天数: {len(history)}")


if __name__ == '__main__':
    main()
