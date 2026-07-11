# -*- coding: utf-8 -*-
"""快速测试新闻情感策略"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategies.news_sentiment_strategy import NewsSentimentStrategy, HotNewsTrackingStrategy
from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator
from datetime import datetime

print('=' * 60)
print('新闻情感策略回测测试')
print('=' * 60)

helper = AKShareHelper()
timing = TimingEngine()
today = datetime.now().strftime('%Y-%m-%d')

# 测试新闻情感策略
print('\n[1] 新闻情感策略选股...')
strategy1 = NewsSentimentStrategy()
results1 = strategy1.detect_events(helper)
print(f'选出 {len(results1)} 只股票:')
for r in results1[:5]:
    print(f'  {r.get("name", r["symbol"])}({r["symbol"]}): {r.get("reason", "")[:50]}')

# 测试热点新闻策略
print('\n[2] 热点新闻策略选股...')
strategy2 = HotNewsTrackingStrategy()
results2 = strategy2.detect_events(helper)
print(f'选出 {len(results2)} 只股票:')
for r in results2[:5]:
    print(f'  {r.get("name", r["symbol"])}({r["symbol"]}): {r.get("reason", "")[:50]}')

# 模拟回测
print('\n[3] 模拟回测...')
simulator = TradingSimulator(strategy1, timing)

# 获取价格并买入
for stock in results1[:3]:
    try:
        symbol = stock['symbol']
        df = helper.get_history_kline(symbol, days=5)
        if not df.empty:
            price = df['close'].iloc[-1]
            simulator.buy(symbol, price, 100)
            print(f'  买入 {symbol} @ {price:.2f}')
    except Exception as e:
        print(f'  买入 {symbol} 失败: {e}')

# 获取最终结果
print('\n[4] 回测结果...')
final_prices = {}
for h in strategy1.holdings:
    try:
        df = helper.get_history_kline(h['symbol'], days=5)
        if not df.empty:
            final_prices[h['symbol']] = df['close'].iloc[-1]
    except:
        pass

result = strategy1.to_dict(final_prices)
print(f'  总收益: {result.get("total_return", 0):.2f}%')
print(f'  交易次数: {len(strategy1.trades)}')
print(f'  持仓: {len(strategy1.holdings)}')

print('\n' + '=' * 60)
print('测试完成!')
print('=' * 60)
