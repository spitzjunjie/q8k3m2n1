import json
d = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
print(f"策略数: {len(d['strategies'])}")
print("\n策略的最后交易日期:")
for s in d['strategies']:
    trades = s.get('trades', [])
    if trades:
        last = trades[-1]
        date = last.get('sell_date') or last.get('buy_date')
        print(f"  {s['name']}: {date}")
    else:
        print(f"  {s['name']}: 无交易")
