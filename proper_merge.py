# -*- coding: utf-8 -*-
"""正确合并策略数据 - 保留现有数据，如果存在新数据则合并"""
import json
import os
import subprocess

def main():
    # 检查是否有新数据文件
    new_file = 'output/new_strategy_results.json'
    
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
    old_data['update_time'] = '2026-07-25 08:40:00'
    
    # 保存
    with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n最终策略数: {len(old_data['strategies'])}")

if __name__ == '__main__':
    main()
