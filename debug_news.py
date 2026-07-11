# -*- coding: utf-8 -*-
"""调试新闻数据"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

import akshare as ak
from strategy_discovery.hf_client import HuggingFaceClient

print('=' * 60)
print('调试新闻数据')
print('=' * 60)

# 1. 获取新闻
print('\n[1] 获取财经新闻...')
try:
    news_df = ak.stock_news_em()
    print(f'获取到 {len(news_df)} 条新闻')
    print(f'列名: {list(news_df.columns)}')
    print(f'\n前5条新闻:')
    print(news_df.head())
except Exception as e:
    print(f'获取新闻失败: {e}')
    news_df = None

# 2. 测试 FinBERT 对中文新闻的效果
print('\n[2] 测试 FinBERT 对中文新闻的效果...')
client = HuggingFaceClient(api_token='***REMOVED***')

# 中文测试
chinese_news = [
    "The company reported strong quarterly earnings, beating analyst expectations.",
    "公司业绩大幅增长，净利润同比增长50%，超出市场预期。",
    "Stock prices fell sharply due to poor financial results.",
]

for news in chinese_news:
    result = client.analyze_financial_news(news)
    if result:
        print(f'\n新闻: {news[:50]}...')
        print(f'情感: {result["sentiment"]}, 分数: {result["sentiment_score"]}')

# 3. 尝试用 akshare 其他新闻接口
print('\n[3] 尝试其他新闻接口...')
try:
    # 尝试获取个股新闻
    print('尝试 akshare.stock_news_individual_em...')
    # 这个接口需要股票代码，我们用茅台试试
    individual_news = ak.stock_news_individual_em(symbol="600519")
    print(f'获取到 {len(individual_news)} 条个股新闻')
    print(individual_news.head(3))
except Exception as e:
    print(f'个股新闻接口失败: {e}')

print('\n' + '=' * 60)
print('调试完成')
print('=' * 60)
