import json

d = json.load(open('output/strategy_data.json', encoding='utf-8'))
print(f"update_time: {d.get('update_time')}  策略数: {len(d.get('strategies', []))}")
print()

rows = []
for s in d['strategies']:
    hist = s.get('all_trades') or s.get('trades') or []
    rows.append({
        'name': s['name'],
        'ret': s.get('total_return', 0) * 100,
        'sharpe': s.get('sharpe_ratio', 0),
        'dd': s.get('max_drawdown', 0) * 100,
        'win': s.get('win_rate', 0) * 100,
        'trades': len(hist),
        'grade': s.get('grade', '?'),
        'score': s.get('composite_score', 0),
        'holdings': len(s.get('holdings', [])),
    })

rows.sort(key=lambda x: x['ret'], reverse=True)

print("== 按收益排序 ==")
for r in rows:
    print(f"{r['name']:<14} 收益{r['ret']:+6.1f}% 夏普{r['sharpe']:5.2f} "
          f"回撤{r['dd']:5.1f}% 胜率{r['win']:4.0f}% 交易{r['trades']:3} "
          f"grade={r['grade']} 分{r['score']:.0f} 持仓{r['holdings']}")

profitable = sum(1 for r in rows if r['ret'] > 0)
print(f"\n盈利策略: {profitable}/{len(rows)}")
print(f"grade 分布: " + ", ".join(f"{g}:{sum(1 for r in rows if r['grade']==g)}"
      for g in ['S', 'A', 'B', 'C', 'D']))

print("\n== 需关注（亏损>10% 或 交易>=5 且亏损）==")
for r in rows:
    if r['ret'] < -10 or (r['trades'] >= 5 and r['ret'] < -5):
        print(f"  {r['name']}: 收益{r['ret']:+.1f}% 夏普{r['sharpe']:.2f} "
              f"交易{r['trades']} 胜率{r['win']:.0f}%")

print("\n== 交易过少（<5 笔，统计不足）==")
few = [r for r in rows if r['trades'] < 5]
print(f"  {len(few)} 个策略: " + ", ".join(r['name'] for r in few))
