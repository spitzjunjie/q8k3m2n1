# -*- coding: utf-8 -*-
import json

old = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
new = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))

old_names = {s['name'] for s in old['strategies']}

print("new_strategy_results.json中的策略:")
for s in new['strategies']:
    trades = len(s.get('trades', []))
    pct = s.get('total_pnl_pct', 0)
    status = "✅" if trades > 0 else "❌"
    in_old = "已存在" if s['name'] in old_names else "新策略"
    print(f"  {status} {s['name']}: {pct:.2f}%, 交易{trades}次, {in_old}")
