import json

new = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))
print(f"new_strategy_results.json中共有{len(new['strategies'])}个策略:\n")

for s in new['strategies']:
    trades = len(s.get('trades', []))
    pct = s.get('total_pnl_pct', 0)
    print(f"  {s['name']}: {pct:.2f}%, 交易{trades}次")
