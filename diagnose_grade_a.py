# -*- coding: utf-8 -*-
"""A级策略数据诊断"""

import sys
sys.path.insert(0, '.')
from data.akshare_helper import AKShareHelper
from backtest import get_all_strategies
import pandas as pd

helper = AKShareHelper()

print('=' * 60)
print('A级策略数据诊断')
print('=' * 60)

# A级策略
test_strategies = ['多周期共振', '高管增持', '均线多头排列', 'RSI超卖反转', '趋势动量', '量价突破', '低PE', '低PB']

strategies = get_all_strategies()

for name in test_strategies:
    strategy = next((s for s in strategies if s.name == name), None)
    if strategy is None:
        print(f'\n{name}: 策略不存在')
        continue

    print(f'\n{name}:')

    # 因子策略
    if hasattr(strategy, 'calculate_factor'):
        result = strategy.calculate_factor(helper)
        if result is None or result.empty:
            print(f'  选股为空')
        else:
            print(f'  选出 {len(result)} 只')
            # 检查前3只的详细数据
            for _, row in result.head(3).iterrows():
                sym = row['symbol']
                kline = helper.get_history_kline(sym, days=30)
                val = helper.get_valuation_data(sym)
                fin = helper.get_financial_indicator(sym)
                close = kline['close'].iloc[-1] if kline is not None and not kline.empty else 0
                pe = val.get('pe', 0)
                roe = fin.get('roe', 0)
                print(f'    {sym}: 价格={close:.2f}, PE={pe:.1f}, ROE={roe}')

    # 事件策略
    elif hasattr(strategy, 'detect_events'):
        result = strategy.detect_events(helper)
        if not result:
            print(f'  选股为空')
        else:
            print(f'  选出 {len(result)} 只')
            for r in result[:3]:
                sym = r['symbol']
                kline = helper.get_history_kline(sym, days=30)
                close = kline['close'].iloc[-1] if kline is not None and not kline.empty else 0
                reason = r.get('reason', '')[:40]
                print(f'    {sym}: 价格={close:.2f}, 原因={reason}')

print('\n' + '=' * 60)
print('诊断结论')
print('=' * 60)
