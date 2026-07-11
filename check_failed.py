# -*- coding: utf-8 -*-
"""检查0%收益的失败策略"""
import json

data = json.load(open('output/strategy_data.json', encoding='utf-8'))
strategies = data.get('strategies', [])

zero_return = []
for s in strategies:
    ret = s.get('total_return', 0)
    trades = len(s.get('trades', []))
    if ret == 0 and trades == 0:
        zero_return.append(s)

print(f"总策略数: {len(strategies)}")
print(f"0%收益且无交易策略数: {len(zero_return)}")
print()
for s in zero_return:
    name = s.get('name', '')
    cat = s.get('category', '')
    print(f"  {name} [{cat}]")
