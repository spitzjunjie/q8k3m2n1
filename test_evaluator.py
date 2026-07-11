# -*- coding: utf-8 -*-
"""测试评估器"""

from evaluation import StrategyEvaluator

# 测试评估器
evaluator = StrategyEvaluator()

# 模拟一个正常表现不错的回测结果
test_result = {
    'name': '测试策略',
    'category': '测试',
    'total_return': 0.15,       # 15%收益
    'sharpe_ratio': 1.5,        # 夏普1.5
    'max_drawdown': 0.08,       # 8%回撤
    'win_rate': 0.60,           # 60%胜率
    'equity_curve': [100000, 102000, 104000, 106000, 108000, 110000, 112000, 114000, 116000, 118000],
    'trades': [
        {'profit': 1000}, {'profit': -500}, {'profit': 800}, {'profit': -300}, {'profit': 1200}
    ]
}

result = evaluator.evaluate(test_result)
print('评估结果:')
print(f'  综合分数: {result["composite_score"]}')
print(f'  等级: {result["grade"]}')
print(f'  总收益: {result["total_return"]*100:.1f}%')
print(f'  夏普比率: {result["sharpe_ratio"]:.2f}')
print(f'  最大回撤: {result["max_drawdown"]*100:.1f}%')
print(f'  胜率: {result["win_rate"]*100:.0f}%')

# 测试实际回测结果
print('\n' + '='*50)
print('现在测试实际回测结果')
print('='*50)

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategies.roe_strategy import ROEStrategy
from backtest import run_strategy
from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine

helper = AKShareHelper()
timing = TimingEngine()
strategy = ROEStrategy()

print(f'\n运行策略: {strategy.name}')
try:
    backtest_result = run_strategy(strategy, helper, timing, date=None)
    print(f'回测结果:')
    print(f'  总收益: {backtest_result.get("total_return", 0)*100:.2f}%')
    print(f'  夏普比率: {backtest_result.get("sharpe_ratio", 0):.2f}')
    print(f'  最大回撤: {backtest_result.get("max_drawdown", 0)*100:.2f}%')
    print(f'  胜率: {backtest_result.get("win_rate", 0)*100:.1f}%')

    # 评估
    evaluation = evaluator.evaluate(backtest_result)
    print(f'\n评估结果:')
    print(f'  综合分数: {evaluation["composite_score"]}')
    print(f'  等级: {evaluation["grade"]}')
except Exception as e:
    print(f'回测失败: {e}')
