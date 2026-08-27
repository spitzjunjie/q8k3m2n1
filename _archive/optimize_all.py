"""
策略参数优化脚本
网格搜索最优参数
"""

import json
import itertools
from datetime import datetime

def optimize_strategy_params():
    """优化策略参数"""
    print("=" * 60)
    print("策略参数优化引擎")
    print("=" * 60)
    
    # 定义可优化的策略参数
    optimizations = {
        '均线多头排列': {
            'ma_short': [5, 10, 20],
            'ma_long': [30, 60, 120],
            'holding_days': [5, 10, 15],
        },
        'MACD金叉': {
            'fast': [8, 12, 16],
            'slow': [20, 26, 32],
            'signal': [6, 9, 12],
        },
        'KDJ超卖金叉': {
            'k_period': [9, 14, 21],
            'oversold': [20, 30, 40],
            'holding_days': [3, 5, 7],
        },
        'RSI超卖反转': {
            'rsi_period': [7, 14, 21],
            'oversold': [20, 30, 40],
            'overbought': [50, 60, 70],
        },
        '资金流事件': {
            'consecutive_days': [3, 5, 7],
            'holding_days': [5, 10, 15],
        },
        '超跌反弹': {
            'lookback_days': [5, 10, 20],
            'max_drop': [10, 15, 20],
            'holding_days': [5, 10, 15],
        },
        '行业动量': {
            'lookback_days': [10, 20, 30],
            'top_n': [1, 3, 5],
            'holding_days': [5, 10, 20],
        },
        '高股息': {
            'min_dividend': [2, 3, 5],
            'min_roe': [5, 10, 15],
            'holding_days': [20, 30, 60],
        },
    }
    
    results = []
    
    for strategy_name, params in optimizations.items():
        print(f"\n优化: {strategy_name}")
        
        # 生成所有参数组合
        keys = list(params.keys())
        values = list(params.values())
        combinations = list(itertools.product(*values))
        
        best_score = -999
        best_params = None
        
        for combo in combinations:
            current_params = dict(zip(keys, combo))
            
            # 模拟评分（实际应该回测）
            import random
            score = random.uniform(0, 1)
            
            if score > best_score:
                best_score = score
                best_params = current_params
            
            print(f"  {current_params} -> 评分: {score:.3f}")
        
        results.append({
            'strategy': strategy_name,
            'best_params': best_params,
            'best_score': best_score,
        })
    
    # 保存结果
    output_path = 'output/optimization_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'optimizations': results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n优化完成! 结果保存到: {output_path}")
    
    return results


if __name__ == '__main__':
    optimize_strategy_params()
