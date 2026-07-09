import json
import os

# 读取12个新策略的回测结果
with open('output/12_new_strategy_results.json', 'r', encoding='utf-8') as f:
    new_data = json.load(f)

# 读取主数据
main_file = 'output/strategy_data.json'
with open(main_file, 'r', encoding='utf-8') as f:
    main_data = json.load(f)

# 获取主数据中的策略名（用于去重）
main_strategies = {s['name']: s for s in main_data['strategies']}

# 合并策略 - 回测过的策略更新到主数据
backtest_strategies = new_data.get('strategies_with_trades', [])
updated = []
added = []

for strategy in backtest_strategies:
    name = strategy['name']
    if name in main_strategies:
        # 更新已有策略
        main_strategies[name] = strategy
        updated.append(name)
        print(f"更新: {name} (收益:{strategy.get('total_return', 0)*100:.2f}%)")
    else:
        # 添加新策略
        main_strategies[name] = strategy
        added.append(name)
        print(f"添加: {name} (收益:{strategy.get('total_return', 0)*100:.2f}%)")

# 保存
main_data['strategies'] = list(main_strategies.values())
main_data['update_time'] = '2026-07-09 14:47:02'
main_data['strategy_count'] = len(main_data['strategies'])
with open(main_file, 'w', encoding='utf-8') as f:
    json.dump(main_data, f, ensure_ascii=False, indent=2)

print(f"\n已更新 {len(updated)} 个策略，已添加 {len(added)} 个策略")
