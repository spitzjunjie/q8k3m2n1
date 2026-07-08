# -*- coding: utf-8 -*-
import json
import subprocess
import os

# 从git获取之前的回测结果
result = subprocess.run(
    ['git', 'show', '9fc599c:output/new_strategy_results.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)

if result.returncode != 0:
    print("获取失败")
    print(result.stderr)
    exit(1)

backup_data = json.loads(result.stdout)
print(f"找到 {len(backup_data['strategies'])} 个策略")

# 8个目标策略
targets = ['行业动量', '涨停回调', '价值成长', '低波动', 'RSI超卖反转', '低PB价值', '超跌反弹', '短线动量']

print("\n检查8个策略:")
found = []
for s in backup_data['strategies']:
    if s['name'] in targets:
        trades = len(s.get('trades', []))
        pct = s.get('total_pnl_pct', 0)
        print(f"  ✅ {s['name']}: {pct:.2f}%, 交易{trades}次")
        found.append(s)

print(f"\n找到 {len(found)}/8 个策略")
