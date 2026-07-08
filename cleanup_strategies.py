# -*- coding: utf-8 -*-
"""清理策略数据 - 只保留有交易的策略"""
import json

data = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
print(f"清理前策略数: {len(data['strategies'])}")

# 过滤有交易的策略
successful = []
skipped = []

for s in data['strategies']:
    trades = len(s.get('trades', []))
    has_return = s.get('realized_pnl', 0) > 0 or s.get('total_pnl', 0) > 0
    
    if trades > 0 or has_return:
        successful.append(s)
    else:
        skipped.append(s['name'])

print(f"清理后策略数: {len(successful)}")
print(f"\n删除的策略 ({len(skipped)}个):")
for name in skipped:
    print(f"  - {name}")

# 保存清理后的数据
data['strategies'] = successful
data['strategy_count'] = len(successful)
data['update_time'] = '2026-07-08 22:50:00'

with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n完成！保留 {len(successful)} 个有交易的策略")
