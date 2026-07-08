import json

new = json.load(open('output/new_strategy_results.json', 'r', encoding='utf-8'))
for s in new['strategies']:
    if 'MACD' in s['name'] or '高股息' in s['name']:
        print(f"{s['name']}: realized_pnl={s.get('realized_pnl')}, total_pnl={s.get('total_pnl')}, trades={len(s.get('trades', []))}")
