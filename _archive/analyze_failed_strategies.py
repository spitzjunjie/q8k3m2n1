# -*- coding: utf-8 -*-
"""分析14个失败策略的回测表现 - 从git获取数据"""

import json
import subprocess

# 从成功的commit获取数据
result = subprocess.run(
    ['git', 'show', '9fc599c:output/new_strategy_results.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)
data = json.loads(result.stdout)

# 14个失败策略
failed = ['ROE选股', '高ROIC', '红利低波', '动量反转', 'KDJ超卖金叉', '动量突破', 
          '南向资金', '北向资金', '龙虎榜', '业绩暴增', '资金流事件', '反过度自信', 
          '超跌反弹', '短线动量', '研报推荐']

print('='*60)
print('14个失败策略回测表现（从git获取）')
print('='*60)

results = []
for s in data['strategies']:
    if s['name'] in failed:
        trades = len(s.get('trades', []))
        pnl = s.get('total_pnl_pct', 0)
        status = '有交易' if trades > 0 else '无交易'
        print(f"{s['name']:12s}: {status}, 交易{len(s.get('trades',[]))}笔, 收益{pnl:.2f}%")
        results.append({
            'name': s['name'],
            'has_trades': trades > 0,
            'trades_count': trades,
            'pnl_pct': pnl
        })

print('\n汇总:')
success = [r for r in results if r['has_trades']]
fail = [r for r in results if not r['has_trades']]
print(f"有交易: {len(success)}个")
print(f"无交易: {len(fail)}个")

if success:
    print("\n有交易的策略:")
    for r in success:
        print(f"  - {r['name']}: {r['trades_count']}笔, 收益{r['pnl_pct']:.2f}%")

if fail:
    print("\n无交易的策略（需要优化）:")
    for r in fail:
        print(f"  - {r['name']}")
