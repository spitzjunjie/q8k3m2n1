import json
d=json.load(open('output/strategy_data.json'))
for s in d['strategies']:
    if s['name'] == '南向资金':
        print(f"策略: {s['name']}")
        print(f"initial_capital: {s['initial_capital']}")
        print(f"current_capital: {s['current_capital']}")
        print(f"total_value: {s['total_value']}")
        print(f"total_return: {s['total_return']*100:.2f}%")
        print(f"realized_pnl: {s['realized_pnl']}")
        print(f"floating_pnl: {s['floating_pnl']}")
        print(f"holdings:")
        for h in s['holdings']:
            print(f"  {h['symbol']}: buy_price={h.get('buy_price')}, quantity={h.get('quantity')}, cost={h.get('cost')}")
        break
