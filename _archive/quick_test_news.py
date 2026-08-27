# -*- coding: utf-8 -*-
"""快速测试新闻策略选股"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategies.news_sentiment_strategy import NewsSentimentStrategy, HotNewsTrackingStrategy
from data.akshare_helper import AKShareHelper

print('=' * 60)
print('新闻情感策略测试')
print('=' * 60)

helper = AKShareHelper()

print('\n[1] 新闻情感策略选股...')
strategy1 = NewsSentimentStrategy()
results1 = strategy1.detect_events(helper)
print('选出股票数量:', len(results1))
for r in results1[:5]:
    name = r.get('name', r['symbol'])
    reason = r.get('reason', '')[:60]
    print(f'  {name}: {reason}')

print('\n[2] 热点新闻策略选股...')
strategy2 = HotNewsTrackingStrategy()
results2 = strategy2.detect_events(helper)
print('选出股票数量:', len(results2))
for r in results2[:5]:
    name = r.get('name', r['symbol'])
    reason = r.get('reason', '')[:60]
    print(f'  {name}: {reason}')

print('\n' + '=' * 60)
print('测试完成!')
print('=' * 60)
