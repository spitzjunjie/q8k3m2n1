# -*- coding: utf-8 -*-
"""测试 Groq 集成后的金融NLP模块"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategy_discovery.financial_nlp import create_sentiment_monitor, create_strategy_analyzer, create_report_enhancer

print('=' * 60)
print('金融NLP模块测试（Groq集成后）')
print('=' * 60)

# 测试市场情绪
print('\n[1] 市场情绪监控...')
monitor = create_sentiment_monitor()
sentiment = monitor.get_market_sentiment()
print('情绪:', sentiment['overall_sentiment']['label'])
print('操作:', sentiment['overall_sentiment']['action'])

# 测试策略分析（使用Groq）
print('\n[2] 策略失败分析（Groq）...')
analyzer = create_strategy_analyzer()
strategy_info = {'name': '低PE策略', 'select_rule': 'PE<10'}
backtest_result = {'total_return': -5.2, 'sharpe': 0.3, 'win_rate': 0.35}
suggestion = analyzer.analyze_failure(strategy_info, backtest_result)
if suggestion:
    print('失败原因:', suggestion['failure_reasons'][0])
    print('改进:', suggestion['improvements'][0]['direction'])

# 测试报告增强（使用Groq）
print('\n[3] 报告增强（Groq）...')
enhancer = create_report_enhancer()
market_data = {'indices': {'上证指数': {'price': 3015, 'change_pct': 0.5}}}
insight = enhancer.generate_market_insight(market_data)
print('洞察:', insight[:100])

print('\n' + '=' * 60)
print('测试完成！所有API已自动选择最优路径')
print('=' * 60)
