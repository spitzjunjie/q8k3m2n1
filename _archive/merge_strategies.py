# -*- coding: utf-8 -*-
"""合并新旧策略数据 - 只合并有交易的策略"""
import json

# 读取旧数据
with open('output/strategy_data.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)

# 读取新数据
with open('output/new_strategy_results.json', 'r', encoding='utf-8') as f:
    new_data = json.load(f)

print(f"旧策略数: {len(old_data['strategies'])}")
print(f"新策略数: {len(new_data['strategies'])}")

# 找出不重复的、且有交易的策略（有交易记录或收益率不为0）
old_names = {s['name'] for s in old_data['strategies']}
successful_strategies = []

for s in new_data['strategies']:
    if s['name'] in old_names:
        continue
    # 判断是否有交易：realized_pnl > 0 或有 trades 记录
    has_trades = len(s.get('trades', [])) > 0
    has_return = s.get('realized_pnl', 0) > 0 or s.get('total_pnl', 0) > 0
    
    if has_trades or has_return:
        successful_strategies.append(s)
        pct = s.get('total_pnl_pct', 0)
        print(f"  ✅ {s['name']}: {pct:.2f}% (交易次数: {len(s.get('trades', []))})")
    else:
        print(f"  ❌ {s['name']}: 0% (无交易，跳过)")

print(f"\n只有{len(successful_strategies)}个策略有交易记录，将被合并")

# 合并
old_data['strategies'].extend(successful_strategies)
old_data['strategy_count'] = len(old_data['strategies'])
old_data['update_time'] = '2026-07-08 22:45:00'

# 保存
with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
    json.dump(old_data, f, ensure_ascii=False, indent=2)

print(f"\n合并完成！策略总数: {len(old_data['strategies'])}")
