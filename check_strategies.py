# -*- coding: utf-8 -*-
import json

data = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
print(f"总策略数: {len(data['strategies'])}")
print("\n有交易的策略:")
for s in data['strategies']:
    trades = len(s.get('trades', []))
    if trades > 0:
        print(f"  {s['name']}: 收益={s.get('total_pnl_pct', 0):.2f}%, 交易={trades}")
