import json
import sys

path = r'c:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\strategy_data.json'
data = json.load(open(path, 'r', encoding='utf-8'))

strategies = data.get('strategies', [])
print(f"Total strategies: {len(strategies)}")
print()

results = []
zero_return = []
for s in strategies:
    name = s.get('name', '?')
    ret = s.get('total_return', s.get('return', 0))
    trades_val = s.get('total_trades', s.get('trades', 0))
    if isinstance(trades_val, list):
        n_trades = len(trades_val)
    else:
        n_trades = trades_val
    results.append((name, ret, n_trades))
    if abs(ret) < 0.001:
        zero_return.append((name, n_trades))

print("=== All strategies (sorted by return) ===")
for name, ret, n_trades in sorted(results, key=lambda x: x[1], reverse=True):
    print(f"  {name:20s} return={ret:+.2f}%  trades={n_trades}")

print()
print(f"=== Zero return strategies ({len(zero_return)}) ===")
for name, n_trades in zero_return:
    print(f"  - {name} (trades={n_trades})")

positive = sum(1 for _, r, _ in results if r > 0.001)
negative = sum(1 for _, r, _ in results if r < -0.001)
zero = len(zero_return)
print()
print(f"Summary: {positive} positive, {negative} negative, {zero} zero")
