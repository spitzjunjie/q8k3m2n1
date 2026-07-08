# -*- coding: utf-8 -*-
import json
import subprocess

# 从成功的commit获取数据
result = subprocess.run(
    ['git', 'show', '9fc599c:output/new_strategy_results.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)
data = json.loads(result.stdout)

# 0%收益的策略
targets = ['超跌反弹', '短线动量', '量价齐升', '南向资金', '龙虎榜', '北向资金', '资金流事件', '反过度自信', '研报推荐', '业绩暴增', 'ETF二八轮动', '财务基本面过滤小市值']

print("0%收益策略检查:")
for s in data['strategies']:
    if s['name'] in targets:
        trades = len(s.get('trades', []))
        pct = s.get('total_pnl_pct', 0)
        realized = s.get('realized_pnl', 0)
        print(f"{s['name']}:")
        print(f"  收益: {pct:.2f}%")
        print(f"  已实现盈亏: {realized}")
        print(f"  交易次数: {trades}")
        if trades == 0:
            print(f"  原因: 选股失败，无交易记录")
        print()
