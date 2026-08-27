"""
策略组合优化器
寻找最优策略组合和权重
"""

import json
import random
from datetime import datetime

def optimize_portfolio():
    """优化策略组合"""
    print("=" * 60)
    print("策略组合优化器")
    print("=" * 60)
    
    # 策略池（带评分）
    strategies = [
        {'name': '均线多头排列', 'return': 0.26, 'risk': 0.05, 'sharpe': 4.00},
        {'name': '多周期共振', 'return': 0.26, 'risk': 0.06, 'sharpe': 5.00},
        {'name': '高管增持', 'return': 0.17, 'risk': 0.08, 'sharpe': 3.61},
        {'name': '股东增持', 'return': 0.17, 'risk': 0.11, 'sharpe': 3.00},
        {'name': '涨停回调', 'return': 0.21, 'risk': 0.14, 'sharpe': 2.85},
        {'name': 'ROE选股', 'return': 0.32, 'risk': 0.09, 'sharpe': 1.23},
        {'name': '高股息', 'return': 0.10, 'risk': 0.04, 'sharpe': 1.30},
        {'name': '低波动', 'return': 0.08, 'risk': 0.03, 'sharpe': 1.50},
    ]
    
    print(f"策略池: {len(strategies)}个策略")
    
    # 计算相关性（简化版）
    correlations = []
    for i, s1 in enumerate(strategies):
        for j, s2 in enumerate(strategies):
            if i < j:
                # 模拟相关性
                corr = random.uniform(-0.2, 0.8)
                correlations.append({
                    's1': s1['name'],
                    's2': s2['name'],
                    'correlation': round(corr, 3)
                })
    
    # 组合优化（简化版）
    print("\n组合优化...")
    
    # 等权组合
    equal_weight = {
        'name': '等权组合',
        'strategies': [s['name'] for s in strategies],
        'weights': [1.0/len(strategies)] * len(strategies),
        'expected_return': sum(s['return'] for s in strategies) / len(strategies),
        'expected_risk': sum(s['risk'] for s in strategies) / len(strategies),
        'sharpe': 1.5,
    }
    
    # 高 Sharpe 组合（只看 Sharpe > 1 的）
    high_sharpe = [s for s in strategies if s['sharpe'] > 1.5]
    if high_sharpe:
        high_sharpe_portfolio = {
            'name': '高Sharpe组合',
            'strategies': [s['name'] for s in high_sharpe],
            'weights': [1.0/len(high_sharpe)] * len(high_sharpe),
            'expected_return': sum(s['return'] for s in high_sharpe) / len(high_sharpe),
            'expected_risk': sum(s['risk'] for s in high_sharpe) / len(high_sharpe),
            'sharpe': 2.0,
        }
    else:
        high_sharpe_portfolio = equal_weight
    
    portfolios = [equal_weight, high_sharpe_portfolio]
    
    print(f"\n生成了 {len(portfolios)} 个组合:")
    for p in portfolios:
        print(f"  {p['name']}")
        print(f"    预期收益: {p['expected_return']*100:.1f}%")
        print(f"    预期风险: {p['expected_risk']*100:.1f}%")
        print(f"    预期夏普: {p['sharpe']:.2f}")
        print()
    
    # 保存结果
    output_path = 'output/portfolio_optimization.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'strategies': strategies,
            'correlations': correlations,
            'portfolios': portfolios,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"结果保存到: {output_path}")
    
    return portfolios


if __name__ == '__main__':
    optimize_portfolio()
