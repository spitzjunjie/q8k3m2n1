import json

path = r'c:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\new_strategy_results.json'
data = json.load(open(path, 'r', encoding='utf-8'))

strategies = data.get('strategies', [])
print(f"Total strategies in new_strategy_results.json: {len(strategies)}")
print()

for s in strategies:
    name = s.get('name', '?')
    ret = s.get('total_return', s.get('return', 0))
    trades_val = s.get('trades', [])
    n_trades = len(trades_val) if isinstance(trades_val, list) else trades_val
    print(f"  {name:20s} return={ret:+.4f} trades={n_trades}")
