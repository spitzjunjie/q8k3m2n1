# -*- coding: utf-8 -*-
"""测试金融NLP模块"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategy_discovery.financial_nlp import (
    create_sentiment_monitor, 
    create_event_detector, 
    create_strategy_analyzer,
    create_report_enhancer
)

print('=' * 60)
print('金融NLP模块功能测试')
print('=' * 60)

# 1. 测试市场情绪监控
print('\n[1] 市场情绪监控')
try:
    monitor = create_sentiment_monitor()
    sentiment = monitor.get_market_sentiment()
    print(f'整体情绪: {sentiment["overall_sentiment"]["label"]}')
    print(f'操作建议: {sentiment["overall_sentiment"]["action"]}')
    print(f'新闻情绪: {sentiment["news_sentiment"]}')
except Exception as e:
    print(f'情绪监控失败: {e}')

# 2. 测试公告事件检测
print('\n[2] 公告事件检测')
try:
    detector = create_event_detector()
    events = detector.detect_events(days=3)
    print(f'检测到 {len(events)} 个重大事件:')
    for e in events[:3]:
        print(f'  - {e["symbol"]}: {e["title"][:40]}...')
except Exception as e:
    print(f'事件检测失败: {e}')

# 3. 测试策略失败分析
print('\n[3] 策略失败分析')
try:
    analyzer = create_strategy_analyzer()
    strategy_info = {
        'name': '低PE策略',
        'hypothesis': '低PE股票有超额收益',
        'select_rule': 'PE<10',
        'timing_rule': '金叉买入'
    }
    backtest_result = {
        'total_return': -5.2,
        'sharpe': 0.3,
        'win_rate': 0.35,
        'max_drawdown': 15
    }
    suggestion = analyzer.analyze_failure(strategy_info, backtest_result)
    if suggestion:
        print(f'失败原因: {suggestion.get("failure_reasons", [])[:2]}')
        print(f'改进方向: {[i["direction"] for i in suggestion.get("improvements", [])[:2]]}')
except Exception as e:
    print(f'策略分析失败: {e}')

# 4. 测试报告增强
print('\n[4] 报告增强')
try:
    enhancer = create_report_enhancer()
    market_data = {
        'indices': {
            '上证指数': {'price': 3015, 'change_pct': 0.5},
            '创业板': {'price': 1665, 'change_pct': 1.2}
        },
        'north_flow': '净流入30亿'
    }
    insight = enhancer.generate_market_insight(market_data)
    print(f'市场洞察: {insight[:100]}...')
except Exception as e:
    print(f'报告增强失败: {e}')

print('\n' + '=' * 60)
print('所有功能测试完成!')
print('=' * 60)
