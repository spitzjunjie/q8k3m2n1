# -*- coding: utf-8 -*-
"""测试 FinBERT 金融情感分析"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategy_discovery.hf_client import HuggingFaceClient

token = '***REMOVED***'

print('=' * 60)
print('测试 FinBERT 金融情感分析')
print('=' * 60)

client = HuggingFaceClient(api_token=token)

# 测试新闻
test_news = [
    "The company reported strong quarterly earnings, beating analyst expectations by 15%.",
    "Stock prices fell sharply today as the company missed revenue targets.",
    "The Federal Reserve announced no changes to interest rates, markets remain stable.",
    "Apple announces record iPhone sales, stock rises 3% in after-hours trading.",
    "Bank of China reports 20% decline in profit due to bad loans.",
]

print('\n[FinBERT 情感分析测试]')
print('-' * 60)

for news in test_news:
    print(f'\n新闻: {news[:60]}...')
    result = client.analyze_financial_news(news)
    
    if result:
        print(f'情感: {result["sentiment"]}')
        print(f'分数: {result["sentiment_score"]} (范围 -1 到 1)')
        print(f'置信度: {result["confidence"]}')
        print(f'详细: {result["all_scores"]}')
    else:
        print('分析失败')

print('\n' + '=' * 60)
print('FinBERT 测试完成！')
print('=' * 60)
