# -*- coding: utf-8 -*-
import json
import subprocess

# 从git获取之前的回测结果
result = subprocess.run(
    ['git', 'show', '9fc599c:output/new_strategy_results.json'],
    capture_output=True, text=True, encoding='utf-8-sig'
)
backup_data = json.loads(result.stdout)

# 读取当前主数据
main_data = json.load(open('output/strategy_data.json', 'r', encoding='utf-8'))
main_names = {s['name'] for s in main_data['strategies']}

# 8个目标策略
targets = ['行业动量', '涨停回调', '价值成长', '低波动', 'RSI超卖反转', '低PB价值', '超跌反弹', '短线动量']

print("从备份恢复8个策略:")
added = 0
for s in backup_data['strategies']:
    if s['name'] in targets:
        trades = len(s.get('trades', []))
        if trades > 0:  # 只恢复有交易的
            if s['name'] in main_names:
                # 替换
                for i, old in enumerate(main_data['strategies']):
                    if old['name'] == s['name']:
                        main_data['strategies'][i] = s
                        print(f"  🔄 更新: {s['name']} ({s.get('total_pnl_pct', 0):.2f}%)")
                        added += 1
                        break
            else:
                main_data['strategies'].append(s)
                print(f"  ✅ 新增: {s['name']} ({s.get('total_pnl_pct', 0):.2f}%)")
                added += 1

print(f"\n恢复 {added} 个策略")

# 保存
main_data['strategy_count'] = len(main_data['strategies'])
main_data['update_time'] = '2026-07-08 23:50:00'
with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
    json.dump(main_data, f, ensure_ascii=False, indent=2)

print(f"最终策略数: {len(main_data['strategies'])}")
