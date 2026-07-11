import json

path = r'c:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\strategy_data.json'
data = json.load(open(path, 'r', encoding='utf-8'))

strategies = data.get('strategies', [])
print(f"Total strategies: {len(strategies)}")
print()

# Check specific strategies we're interested in
target_names = ['KDJ超卖金叉', 'MACD金叉', '短线动量', '超跌反弹', '反过度自信', '资金流事件',
                '动量反转', '分析师上调', '研报推荐', '业绩暴增', '动量突破']

for s in strategies:
    name = s.get('name', '?')
    if name in target_names:
        ret = s.get('total_return', 0)
        trades_val = s.get('trades', [])
        n_trades = len(trades_val) if isinstance(trades_val, list) else trades_val
        pnl_pct = s.get('total_pnl_pct', s.get('realized_pnl_pct', 0))
        print(f"  {name:20s} return={ret*100:+.2f}%  pnl_pct={pnl_pct:+.2f}%  trades={n_trades}")

print()
print("=== All strategies sorted by return ===")
results = []
for s in strategies:
    name = s.get('name', '?')
    ret = s.get('total_return', 0)
    trades_val = s.get('trades', [])
    n_trades = len(trades_val) if isinstance(trades_val, list) else trades_val
    results.append((name, ret, n_trades))

for name, ret, n_trades in sorted(results, key=lambda x: x[1], reverse=True):
    print(f"  {name:20s} return={ret*100:+.2f}%  trades={n_trades}")

zero = [r for r in results if abs(r[1]) < 0.0001]
print(f"\nZero return: {len(zero)}")
