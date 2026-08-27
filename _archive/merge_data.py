# -*- coding: utf-8 -*-
"""
合并策略数据，确保GitHub显示所有策略
"""

import json
import os
from datetime import datetime

OUTPUT_DIR = "output"
DATA_FILE = os.path.join(OUTPUT_DIR, "strategy_data.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "final_report_20260712_161347.json")

# 已上线策略列表（需要保留完整数据）
ONLINE_STRATEGIES = [
    "多周期共振", "高管增持", "均线多头排列", "国产替代",
    "趋势动量", "AI供应链紫苏叶", "ST摘帽潜伏", "业绩超预期",
    "量价突破", "北向资金跟投", "多因子综合", "现金流质量",
    "首板回调", "ROE选股", "高ROIC", "红利低波",
    "高股息", "动量反转", "分析师上调", "MACD金叉",
    "KDJ超卖金叉", "动量突破", "营收增长", "净利润增速",
    "北向重仓", "机构持仓", "PSR低估值", "低负债率",
    "RSI超卖反转", "低PB", "低估值修复", "低PE", "质量因子选股"
]

def main():
    print("=" * 50)
    print("合并策略数据")
    print("=" * 50)
    
    # 1. 读取已上线策略的详细数据
    existing_strategies = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'strategies' in data:
                for s in data['strategies']:
                    existing_strategies[s['name']] = s
        print(f"已上线策略详细数据: {len(existing_strategies)} 个")
    
    # 2. 读取新策略回测结果
    new_results = {}
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, 'r', encoding='utf-8') as f:
            report = json.load(f)
            if 'results' in report:
                new_results = report['results']
        print(f"新策略回测结果: {len(new_results)} 个")
    
    # 3. 合并策略列表
    all_strategies = []
    
    # 添加已上线策略（保留详细数据）
    for name in ONLINE_STRATEGIES:
        if name in existing_strategies:
            strategy = existing_strategies[name].copy()
            # 如果有新评分，更新评分
            if name in new_results:
                new_data = new_results[name]
                strategy['composite_score'] = new_data.get('score', 20)
                strategy['grade'] = new_data.get('grade', 'D')
                strategy['total_return'] = new_data.get('return', 0)
            all_strategies.append(strategy)
    
    # 添加新策略（使用回测结果）
    for name, result in new_results.items():
        if name not in ONLINE_STRATEGIES:
            # 检查是否已有详细数据
            if name in existing_strategies:
                strategy = existing_strategies[name].copy()
                strategy['composite_score'] = result.get('score', 20)
                strategy['grade'] = result.get('grade', 'D')
                strategy['total_return'] = result.get('return', 0)
            else:
                # 创建新策略条目
                strategy = {
                    'name': name,
                    'category': '新策略',
                    'version': '1.0.0',
                    'description': f'{name}策略',
                    'composite_score': result.get('score', 20),
                    'grade': result.get('grade', 'D'),
                    'total_return': result.get('return', 0),
                    'sharpe_ratio': result.get('sharpe', 0),
                    'max_drawdown': result.get('drawdown', 0),
                    'win_rate': result.get('win_rate', 0),
                    'trades': [],
                    'holdings': []
                }
            all_strategies.append(strategy)
    
    # 4. 保存合并后的数据
    merged_data = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_type': 'historical',
        'backtest_start': '2026-05-26',
        'backtest_end': '2026-07-07',
        'backtest_days': 30,
        'strategy_count': len(all_strategies),
        'strategies': all_strategies
    }
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 合并完成: {len(all_strategies)} 个策略")
    print(f"  - 已上线策略: {len(ONLINE_STRATEGIES)} 个")
    print(f"  - 新策略: {len(new_results)} 个")
    
    # 5. 统计等级分布
    grade_stats = {'S': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for s in all_strategies:
        grade = s.get('grade', 'D')
        grade_stats[grade] = grade_stats.get(grade, 0) + 1
    
    print(f"\n等级分布:")
    for g, c in grade_stats.items():
        if c > 0:
            print(f"  {g}级: {c}个")
    
    return len(all_strategies)

if __name__ == "__main__":
    count = main()
    print(f"\nstrategy_data.json 现有 {count} 个策略")
