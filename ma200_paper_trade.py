# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MA200 模拟盘（paper trading）：每日记账，前向验证。
===========================================================
用沪深300 收盘 vs 200 日均线判断信号；按 60/40 股债规则在信号切换日重建仓位。
每天跑一次：python ma200_paper_trade.py
状态持久化到 output/ma200_paper_state.json，可重复运行（同一天不重复记账）。
"""
import os, sys, json
from ma200_common import get_pro, fetch_hs300, signal_state
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


def main():
    pro = get_pro()
    df = fetch_hs300(pro)
    st = signal_state(df)
    if st is None:
        print('数据不足 200 日，无法判断信号')
        return
    d, close, sig = st['date'], st['close'], st['signal']
    state = load_state()
    history = state.get('history', [])
    if history and history[-1].get('date') == d:
        last = history[-1]
        print(f"今日({d})已记账：净值 {last['equity']:,.2f}，仓位 {last.get('position', 0) * 100:.0f}%"
              f"（重复运行同一交易日会自动跳过）")
        return
    target = STOCK_PCT if sig == 'hold' else 0.0
    # 首次建仓或信号切换：在当日收盘按目标仓位重建
    if state['position'] is None or state['position'] != target:
        equity = state['shares'] * close + state['cash']
        state['shares'] = equity * target / close
        state['cash'] = equity * (1 - target)
        state['position'] = target
        state['start'] = state.get('start') or d
    equity = state['shares'] * close + state['cash']
    history.append({'date': d, 'close': close, 'ma': round(st['ma'], 2),
                    'signal': sig, 'position': state['position'], 'equity': round(equity, 2)})
    state['history'] = history
    os.makedirs('output', exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    ret = equity / INITIAL - 1
    peak = max(h['equity'] for h in history)
    dd = (peak - equity) / peak if peak > 0 else 0.0
    label = '持有（60%股票）' if sig == 'hold' else '空仓（全现金）'
    print(f"日期: {d}  信号: {label}")
    print(f"沪深300收盘: {close:.2f}  MA200: {st['ma']:.2f}")
    print(f"组合净值: {equity:,.2f}  累计收益: {ret * 100:+.2f}%  当前回撤: {dd * 100:.2f}%")
    print(f"当前仓位: {state['position'] * 100:.0f}%  起始: {state['start']}  记录天数: {len(history)}")


if __name__ == '__main__':
    main()
