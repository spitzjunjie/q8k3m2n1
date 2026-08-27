#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex 分析脚本：分析0收益策略

这个脚本分析哪些策略有0收益，并输出需要修复的策略列表。
Codex AI 应该根据这个列表来修复策略代码。

Usage:
    python codex_zero_return_task.py
"""

import json
import os
from datetime import datetime

# ============ Config ============
STRATEGY_DATA = "output/strategy_data.json"


def log(msg):
    """Log output"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")


def analyze_zero_return_strategies():
    """分析0收益策略"""
    log("="*60)
    log("分析0收益策略")
    log("="*60)
    
    # 读取策略数据
    if not os.path.exists(STRATEGY_DATA):
        log(f"错误: {STRATEGY_DATA} 不存在")
        return []
    
    with open(STRATEGY_DATA, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    strategies = data.get('strategies', [])
    log(f"总策略数: {len(strategies)}")
    log("")
    
    # 分析0收益策略
    zero_strategies = []
    normal_strategies = []
    
    for s in strategies:
        total_return = s.get('total_return', 0)
        total_trades = s.get('total_trades', 0)
        
        if total_return == 0 and total_trades == 0:
            zero_strategies.append(s)
        else:
            normal_strategies.append(s)
    
    # 输出结果
    log(f"正常策略: {len(normal_strategies)} 个")
    log(f"0收益策略: {len(zero_strategies)} 个")
    log("")
    
    # 按类别分组
    categories = {}
    for s in zero_strategies:
        cat = s.get('category', '未分类')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(s['name'])
    
    log("="*60)
    log("0收益策略分类")
    log("="*60)
    
    for cat, names in categories.items():
        log(f"\n【{cat}】({len(names)} 个)")
        for name in names:
            log(f"  - {name}")
    
    # 输出修复建议
    log("")
    log("="*60)
    log("修复建议")
    log("="*60)
    log("Codex AI 应该：")
    log("1. 查看这些策略的代码")
    log("2. 检查为什么没有产生交易（可能是：")
    log("   - 选股条件太严格，没有股票符合")
    log("   - 数据源无法获取所需数据")
    log("   - 参数设置不当")
    log("   - 代码逻辑错误）")
    log("3. 修复后运行回测验证")
    log("")
    log("修复后运行以下命令回测：")
    log("  python backtest_history.py --source tushare --strategies \"策略1,策略2,...\"")
    log("  python proper_merge.py")
    
    # 保存分析结果
    result = {
        'timestamp': datetime.now().isoformat(),
        'total_strategies': len(strategies),
        'zero_count': len(zero_strategies),
        'normal_count': len(normal_strategies),
        'zero_strategies': [s['name'] for s in zero_strategies],
        'categories': categories
    }
    
    os.makedirs('output', exist_ok=True)
    with open('output/zero_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    log("")
    log(f"分析结果已保存到: output/zero_analysis.json")
    
    return zero_strategies


def main():
    """主流程"""
    log("="*60)
    log("Codex 分析任务：0收益策略分析")
    log("="*60)
    
    zero_strategies = analyze_zero_return_strategies()
    
    log("")
    log("="*60)
    log("任务完成")
    log("="*60)
    log(f"发现 {len(zero_strategies)} 个0收益策略")
    log("请 Codex AI 根据上述分析修复策略代码")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
