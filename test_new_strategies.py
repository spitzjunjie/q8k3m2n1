# -*- coding: utf-8 -*-
"""快速测试新策略"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategies.market_sentiment_strategy import SentimentIcePointStrategy
from strategies.chips_distribution_strategy import ChipsDistributionStrategy
from strategies.news_sentiment_strategy import NewsSentimentStrategy
from strategies.sector_rotation_strategy import SectorRotationStrategy
from strategies.leading_stock_strategy import LeadingStockStrategy
from strategies.quality_factor_strategy import QualityFactorStrategy
from data.akshare_helper import AKShareHelper

print('=' * 60)
print('新策略快速测试')
print('=' * 60)

helper = AKShareHelper()

# 测试情绪冰点
print('\n[1] 情绪冰点抄底策略...')
try:
    strategy1 = SentimentIcePointStrategy()
    results1 = strategy1.detect_events(helper)
    print(f'选出 {len(results1)} 只股票')
    for r in results1[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

# 测试筹码分布
print('\n[2] 筹码分布策略...')
try:
    strategy2 = ChipsDistributionStrategy()
    results2 = strategy2.detect_events(helper)
    print(f'选出 {len(results2)} 只股票')
    for r in results2[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

# 测试新闻情感
print('\n[3] 新闻情感策略...')
try:
    strategy3 = NewsSentimentStrategy()
    results3 = strategy3.detect_events(helper)
    print(f'选出 {len(results3)} 只股票')
    for r in results3[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

# 测试行业轮动
print('\n[4] 行业轮动策略...')
try:
    strategy4 = SectorRotationStrategy()
    results4 = strategy4.detect_events(helper)
    print(f'选出 {len(results4)} 只股票')
    for r in results4[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

# 测试龙头战法
print('\n[5] 龙头战法策略...')
try:
    strategy5 = LeadingStockStrategy()
    results5 = strategy5.detect_events(helper)
    print(f'选出 {len(results5)} 只股票')
    for r in results5[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

# 测试质量因子
print('\n[6] 质量因子策略...')
try:
    strategy6 = QualityFactorStrategy()
    results6 = strategy6.detect_events(helper)
    print(f'选出 {len(results6)} 只股票')
    for r in results6[:3]:
        print(f'  {r.get("name", r["symbol"])}: {r.get("reason", "")[:50]}')
except Exception as e:
    print(f'失败: {e}')

print('\n' + '=' * 60)
print('测试完成!')
print('=' * 60)
