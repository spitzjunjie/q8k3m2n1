import json

path = r'c:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\strategy_data.json'
data = json.load(open(path, 'r', encoding='utf-8'))

strategies = data.get('strategies', [])
print(f"Total strategies: {len(strategies)}")
print()

# Show first 3 strategies in detail to understand format
for s in strategies[:3]:
    name = s.get('name', '?')
    print(f"=== {name} ===")
    for k, v in s.items():
        if k == 'trades':
            print(f"  trades: [{len(v)} trades]")
        else:
            print(f"  {k}: {v}")
    print()
