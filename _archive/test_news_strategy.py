# -*- coding: utf-8 -*-
"""测试新闻情感选股策略"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategies.news_sentiment_strategy import NewsSentimentStrategy
from data.akshare_helper import AKShareHelper

print('=' * 60)
print('测试新闻情感选股策略')
print('=' * 60)

helper = AKShareHelper()
strategy = NewsSentimentStrategy()

print('\n正在获取并分析财经新闻...')
results = strategy.detect_events(helper)

print(f'\n选出 {len(results)} 只股票:')
for i, r in enumerate(results[:10], 1):
    name = r.get('name', r['symbol'])
    reason = r.get('reason', '')
    print(f'{i}. {name}({r["symbol"]}): {reason}')

if not results:
    print('(今日暂无符合条件的股票)')

print('\n' + '=' * 60)
print('测试完成')
print('=' * 60)
