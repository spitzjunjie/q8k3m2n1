# -*- coding: utf-8 -*-
"""完整回测脚本 - 带进度显示"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from backtest import get_all_strategies, run_strategy, PRIMARY_HELPER, FALLBACK_HELPER, DATA_SOURCE
from timing.timing import TimingEngine
from evaluation import StrategyEvaluator

print('=' * 70)
print('多策略量化回测系统')
print('=' * 70)
print(f'数据源: {DATA_SOURCE}')
print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 70)

# 初始化
helper = PRIMARY_HELPER(cache_dir="data/cache")
timing = TimingEngine()
strategies = get_all_strategies()

print(f'\n总策略数: {len(strategies)}')
print(f'回测天数: 5天')
print('=' * 70)

# 回测结果存储
results = []
start_time = time.time()

# 逐个策略回测
for i, strategy in enumerate(strategies):
    strategy_start = time.time()
    print(f'\n[{i+1}/{len(strategies)}] 运行策略: {strategy.name}...', end='', flush=True)
    
    try:
        # 运行策略
        result = run_strategy(strategy, helper, timing, date=None)
        
        # 评估结果
        evaluator = StrategyEvaluator()
        evaluation = evaluator.evaluate(result)
        
        # 存储结果
        strategy_result = {
            'name': strategy.name,
            'category': strategy.category,
            'status': 'success',
            'evaluation': evaluation,
            'backtest': result,
            'time': time.time() - strategy_start
        }
        results.append(strategy_result)
        
        # 显示结果
        grade = evaluation.get('grade', 'N/A')
        score = evaluation.get('composite_score', 0)
        status_icon = '✅' if score >= 50 else '⚠️' if score >= 30 else '❌'
        print(f' {status_icon} 等级:{grade} 分数:{score:.1f} 耗时:{strategy_result["time"]:.1f}s')
        
    except Exception as e:
        print(f' ❌ 失败: {str(e)[:50]}')
        results.append({
            'name': strategy.name,
            'category': strategy.category,
            'status': 'error',
            'error': str(e),
            'time': time.time() - strategy_start
        })

# 统计结果
print('\n' + '=' * 70)
print('回测完成!')
print('=' * 70)

total_time = time.time() - start_time
success_count = sum(1 for r in results if r['status'] == 'success')
failed_count = len(results) - success_count

print(f'\n总计: {len(results)} 个策略')
print(f'成功: {success_count} 个 ✅')
print(f'失败: {failed_count} 个 ❌')
print(f'总耗时: {total_time:.1f} 秒')

# 找出表现最好和最差的策略
success_results = [r for r in results if r['status'] == 'success']
if success_results:
    sorted_results = sorted(success_results, key=lambda x: x['evaluation'].get('composite_score', 0), reverse=True)
    
    print('\n📈 表现最好的5个策略:')
    for r in sorted_results[:5]:
        score = r['evaluation'].get('composite_score', 0)
        print(f'  {r["name"]}: {score:.1f}分 ({r["evaluation"].get("grade", "N/A")})')
    
    print('\n📉 表现最差的5个策略:')
    for r in sorted_results[-5:]:
        score = r['evaluation'].get('composite_score', 0)
        print(f'  {r["name"]}: {score:.1f}分 ({r["evaluation"].get("grade", "N/A")})')
    
    # 找出需要优化的失败策略（评分D级）
    d_grade_strategies = [r for r in success_results if r['evaluation'].get('grade') == 'D']
    if d_grade_strategies:
        print(f'\n⚠️ 需要优化的D级策略 ({len(d_grade_strategies)}个):')
        for r in d_grade_strategies[:5]:
            print(f'  - {r["name"]}: {r["evaluation"].get("composite_score", 0):.1f}分')

# 保存结果
output_file = f'output/backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
os.makedirs('output', exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f'\n结果已保存到: {output_file}')

print('\n' + '=' * 70)
