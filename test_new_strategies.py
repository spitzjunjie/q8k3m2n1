# -*- coding: utf-8 -*-
"""
测试13个新策略的选股功能
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from data.akshare_helper import AKShareHelper
from strategies.new_strategies import get_new_strategy

def test_strategy(strategy_name, helper):
    """测试单个策略"""
    print(f"\n{'='*50}")
    print(f"测试策略: {strategy_name}")
    print('='*50)

    strategy = get_new_strategy(strategy_name)
    if not strategy:
        print(f"  ❌ 策略 {strategy_name} 未找到")
        return None

    print(f"  策略描述: {strategy.get_description()}")

    try:
        stocks = strategy.select_stocks(helper, date='2026-07-10')
        if stocks:
            print(f"  ✅ 选出 {len(stocks)} 只股票:")
            for i, s in enumerate(stocks[:5], 1):
                print(f"    {i}. {s.get('symbol', '')} {s.get('name', '')} - {s.get('reason', '')}")
            return stocks
        else:
            print(f"  ⚠️ 未选出任何股票")
            return []
    except Exception as e:
        print(f"  ❌ 选股失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*60)
    print("13个新策略选股功能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 初始化数据源
    helper = AKShareHelper()

    # 13个新策略列表
    strategies = [
        # 短线交易类（5个）
        '集合竞价选股',
        '尾盘抢筹',
        '游资席位跟踪',
        '涨停封单',
        '跌停撬板',
        # 套利另类类（5个）
        '可转债双低',
        '可转债下修博弈',
        'ETF折溢价套利',
        '网格交易',
        '限售解禁博弈',
        # 基本面深度类（3个）
        '戴维斯双击',
        '困境反转',
        '股东户数变化',
    ]

    results = {}
    for name in strategies:
        result = test_strategy(name, helper)
        results[name] = result
        # 避免频率限制
        import time
        time.sleep(1)

    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)

    success = sum(1 for r in results.values() if r is not None and len(r) > 0)
    fail = sum(1 for r in results.values() if r is None)
    empty = sum(1 for r in results.values() if r is not None and len(r) == 0)

    print(f"  成功: {success} 个策略")
    print(f"  失败: {fail} 个策略")
    print(f"  空选: {empty} 个策略")

    # 保存结果
    output_file = 'output/new_13_strategies_test.json'
    os.makedirs('output', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")

    return results

if __name__ == '__main__':
    main()
