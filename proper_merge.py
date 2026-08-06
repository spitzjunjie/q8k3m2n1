# -*- coding: utf-8 -*-
"""正确合并策略数据 - 保留现有数据，如果存在新数据则合并"""
import json
import os
import subprocess
from datetime import datetime

def main():
    # 本次回测刚生成的新数据（由 backtest.py 写入，update_time 为当前时间）
    # 注意：不要用 output/new_strategy_results.json —— 它可能长期没更新，
    # 之前就是因为它被 git 追踪、内容停留在 7/28，导致每天合并的都是旧数据。
    new_file = 'output/strategy_data.json'
    
    if not os.path.exists(new_file):
        print("没有新策略数据文件，跳过合并")
        # 仍然检查并保存当前数据
        if os.path.exists('output/strategy_data.json'):
            print("当前数据文件已存在，无需更新")
        return
    
    # 从git获取原始数据（如果存在）
    old_data = None
    try:
        result = subprocess.run(
            ['git', 'show', 'HEAD:output/strategy_data.json'],
            capture_output=True, text=True, encoding='utf-8-sig',
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            old_data = json.loads(result.stdout)
            print(f"Git原始策略: {len(old_data.get('strategies', []))}个")
    except Exception as e:
        print(f"获取Git原始数据失败: {e}")
    
    # 如果没有原始数据，尝试使用当前文件
    if old_data is None:
        if os.path.exists('output/strategy_data.json'):
            try:
                with open('output/strategy_data.json', 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                print(f"使用当前数据: {len(old_data.get('strategies', []))}个策略")
            except Exception as e:
                print(f"读取当前数据失败: {e}")
                old_data = {'strategies': [], 'update_time': ''}
        else:
            old_data = {'strategies': [], 'update_time': ''}
            print("没有找到任何历史数据，创建新数据文件")
    
    # 读取新数据
    try:
        with open(new_file, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        print(f"新策略: {len(new_data.get('strategies', []))}个")
    except Exception as e:
        print(f"读取新数据失败: {e}")
        new_data = {'strategies': []}

    # 陈旧数据守卫：new_file 就是 output/strategy_data.json，它可能是 checkout 下来的
    # 旧文件（7/25 起每日回测全部超时，旧文件长期被当成"新数据"自我合并，产生假提交）。
    # 只有 update_time 在最近 7 天内的才允许合并；否则警告并跳过，保持仓库数据不变。
    ut = (new_data.get('update_time') or '').strip()
    try:
        ut_dt = datetime.strptime(ut[:19], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - ut_dt).total_seconds() > 7 * 24 * 3600:
            print(f"⚠️ 新数据 update_time 过旧（{ut}），判定为陈旧数据，跳过合并")
            print("   回测未真正产出新数据（可能超时/失败），保持仓库当前数据不变")
            return
    except Exception:
        print(f"⚠️ 新数据 update_time 格式异常（{ut!r}），跳过合并")
        return
    
    # 处理策略
    old_names = {s['name'] for s in old_data.get('strategies', [])}
    added = []
    replaced = []
    
    for s in new_data.get('strategies', []):
        trades = len(s.get('trades', []))
        
        if s['name'] in old_names:
            # 替换旧策略（如果有交易记录）
            for i, old_s in enumerate(old_data['strategies']):
                if old_s['name'] == s['name']:
                    if trades > 0:
                        old_data['strategies'][i] = s
                        replaced.append(f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}% (替换旧数据)")
                    break
        else:
            # 添加新策略
            if trades > 0:
                old_data['strategies'].append(s)
                added.append(f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}%")
    
    print(f"\n替换策略: {len(replaced)}个")
    for r in replaced:
        print(f"  🔄 {r}")
    
    print(f"新增策略: {len(added)}个")
    for a in added:
        print(f"  ✅ {a}")
    
    old_data['strategy_count'] = len(old_data['strategies'])
    # 用本次回测的真实时间，不再硬编码
    old_data['update_time'] = new_data.get('update_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 如果新数据带回了测区间元数据，以新数据为准
    for k in ('backtest_type', 'backtest_start', 'backtest_end', 'backtest_days'):
        if new_data.get(k):
            old_data[k] = new_data[k]
    
    # 保存
    with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n最终策略数: {len(old_data['strategies'])}")

if __name__ == '__main__':
    main()
