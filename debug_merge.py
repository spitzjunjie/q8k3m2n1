import json

old = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
new = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))

old_names = {s['name'] for s in old['strategies']}
print(f"旧策略名称 ({len(old_names)}个):")
for n in sorted(old_names):
    print(f"  - {n}")

print(f"\n新策略中不在旧策略中的:")
for s in new['strategies']:
    if s['name'] not in old_names:
        trades = len(s.get('trades', []))
        print(f"  - {s['name']}: 交易{trades}次")
