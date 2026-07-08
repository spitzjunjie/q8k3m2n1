# -*- coding: utf-8 -*-
"""从git恢复原始32个策略，然后正确合并有交易的新策略"""
import json
import subprocess
import os

# 从git获取原始数据
result = subprocess.run(
    ['git', 'show', '57d1a97:output/strategy_data.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)

if result.returncode != 0:
    print("获取原始数据失败")
    print(result.stderr)
    exit(1)

old_data = json.loads(result.stdout)
print(f"原始策略数: {len(old_data['strategies'])}")

# 读取新数据
new_data = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))
print(f"新策略数: {len(new_data['strategies'])}")

# 过滤掉无交易的策略，并去除重复
old_names = {s['name'] for s in old_data['strategies']}
new_successful = []

for s in new_data['strategies']:
    if s['name'] in old_names:
        continue
    trades = len(s.get('trades', []))
    if trades > 0:
        new_successful.append(s)
        print(f"  ✅ {s['name']}: {s.get('total_pnl_pct', 0):.2f}%, 交易{trades}次")
    else:
        print(f"  ❌ {s['name']}: 0% (跳过)")

# 合并
old_data['strategies'].extend(new_successful)
old_data['strategy_count'] = len(old_data['strategies'])
old_data['update_time'] = '2026-07-08 23:00:00'

# 保存
with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
    json.dump(old_data, f, ensure_ascii=False, indent=2)

print(f"\n最终策略数: {len(old_data['strategies'])}")
print("完成！")
