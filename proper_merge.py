# -*- coding: utf-8 -*-
"""正确合并策略数据 - 替换重复策略"""
import json
import subprocess

# 从git获取原始数据
result = subprocess.run(
    ['git', 'show', '57d1a97:output/strategy_data.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)
old_data = json.loads(result.stdout)

# 读取新数据
new_data = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))

print(f"原始策略: {len(old_data['strategies'])}个")
print(f"新策略: {len(new_data['strategies'])}个")

# 处理策略
old_names = {s['name'] for s in old_data['strategies']}
added = []
replaced = []

for s in new_data['strategies']:
    trades = len(s.get('trades', []))
    
    if s['name'] in old_names:
        # 替换旧策略（如果有更好的结果）
        for i, old_s in enumerate(old_data['strategies']):
            if old_s['name'] == s['name'] and trades > 0:
                old_data['strategies'][i] = s
                replaced.append(f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}% (替换旧数据)")
                break
    else:
        # 添加新策略
        if trades > 0:
            old_data['strategies'].append(s)
            added.append(f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}%")

print(f"\n替换策略: {len(replaced)}个")
for r in replaced:
    print(f"  🔄 {r}")

print(f"新增策略: {len(added)}个")
for a in added:
    print(f"  ✅ {a}")

old_data['strategy_count'] = len(old_data['strategies'])
old_data['update_time'] = '2026-07-08 23:30:00'

# 保存
with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
    json.dump(old_data, f, ensure_ascii=False, indent=2)

print(f"\n最终策略数: {len(old_data['strategies'])}")
