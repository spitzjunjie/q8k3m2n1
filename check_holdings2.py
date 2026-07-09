import json
d=json.load(open('output/strategy_data.json'))
for s in d['strategies']:
    if s['name'] == '南向资金':
        print(f"策略: {s['name']}")
        print(f"回测结束日期: {s.get('backtest_end', '?')}")
        for h in s['holdings']:
            print(f"  {h['symbol']} {h['name']}: 买入日期={h.get('buy_date')}, 买入价={h.get('buy_price')}")
        break
