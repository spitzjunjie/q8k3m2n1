# -*- coding: utf-8 -*-
"""批量回测未上线策略 - 分批执行"""

import sys
import json
import os
import time
from datetime import datetime

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from backtest import get_all_strategies, run_strategy
from timing.timing import TimingEngine
from evaluation import StrategyEvaluator
from data.akshare_helper import AKShareHelper

# 已上线的33个策略
ONLINE_STRATEGIES = [
    "多周期共振", "高管增持", "均线多头排列", "国产替代",
    "趋势动量", "AI供应链紫苏叶", "ST摘帽潜伏", "业绩超预期",
    "量价突破", "北向资金跟投", "多因子综合", "现金流质量",
    "首板回调", "ROE选股", "高ROIC", "红利低波",
    "高股息", "动量反转", "分析师上调", "MACD金叉",
    "KDJ超卖金叉", "动量突破", "营收增长", "净利润增速",
    "北向重仓", "机构持仓", "PSR低估值", "低负债率",
    "RSI超卖反转", "低PB", "低估值修复", "低PE", "质量因子选股"
]

# 需要回测的策略（可以指定批次）
BATCH_STRATEGIES = [
    # 第1批 - 重点策略
    "新闻情感", "热点新闻", "情绪冰点抄底", "筹码分布", "筹码突破",
    "行业轮动", "龙头战法", "质量因子选股Pro", "尾盘抢筹",
    "集合竞价选股"
]

def run_batch_backtest(strategy_names, batch_num):
    """回测一批策略"""
    print("=" * 60)
    print(f"批次 {batch_num}: 回测 {len(strategy_names)} 个策略")
    print("=" * 60)
    
    helper = AKShareHelper()
    timing = TimingEngine()
    evaluator = StrategyEvaluator()
    all_strategies = get_all_strategies()
    
    # 创建策略名到实例的映射
    strategy_map = {s.name: s for s in all_strategies}
    
    results = []
    start_time = time.time()
    
    for i, name in enumerate(strategy_names, 1):
        if name not in strategy_map:
            print(f"[{i}/{len(strategy_names)}] {name}: 策略不存在，跳过")
            continue
        
        strategy = strategy_map[name]
        print(f"\n[{i}/{len(strategy_names)}] 回测: {name}...", end='', flush=True)
        
        try:
            # 运行回测
            backtest_result = run_strategy(strategy, helper, timing, date=None)
            
            # 评估
            evaluation = evaluator.evaluate(backtest_result)
            
            # 保存结果
            result = {
                'name': name,
                'category': strategy.category,
                **evaluation
            }
            results.append(result)
            
            # 显示结果
            grade = evaluation.get('grade', 'N/A')
            score = evaluation.get('composite_score', 0)
            ret = evaluation.get('total_return', 0) * 100
            icon = '✅' if score >= 35 else '⚠️' if score >= 20 else '❌'
            print(f" {icon} {grade}级({score:.0f}分) 收益:{ret:.1f}%")
            
        except Exception as e:
            print(f" ❌ 失败: {str(e)[:30]}")
            results.append({
                'name': name,
                'category': strategy.category,
                'status': 'error',
                'error': str(e)
            })
        
        # 延迟，避免频率限制
        time.sleep(1)
    
    # 保存结果
    output_file = f"output/batch_{batch_num}_results.json"
    os.makedirs("output", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'batch': batch_num,
            'timestamp': datetime.now().isoformat(),
            'strategies_count': len(strategy_names),
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    elapsed = time.time() - start_time
    
    # 统计
    success = [r for r in results if r.get('status') != 'error']
    c级以上 = [r for r in success if r.get('composite_score', 0) >= 35]
    
    print("\n" + "=" * 60)
    print(f"批次 {batch_num} 完成!")
    print(f"成功: {len(success)}/{len(strategy_names)}")
    print(f"C级以上: {len(c级以上)} 个")
    print(f"耗时: {elapsed:.1f} 秒")
    print(f"结果已保存: {output_file}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    import sys
    
    # 从命令行参数获取批次号
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    # 定义各批次策略
    batches = {
        1: ["新闻情感", "热点新闻", "情绪冰点抄底", "筹码分布", "筹码突破",
            "行业轮动", "龙头战法", "质量因子选股Pro", "尾盘抢筹", "集合竞价选股"],
        2: ["ETF二八轮动", "财务基本面过滤小市值", "资金流事件", "研报推荐", 
            "超跌反弹", "短线动量", "低波动", "龙虎榜", "北向资金", "价值成长"],
        3: ["业绩暴增", "涨停回调", "低PB价值", "机构调研", "业绩预告超预期",
            "北向持仓变化", "月线共振", "主力资金", "北向择时", "财报季"],
        4: ["护城河选股", "GARP成长", "高成长股", "周期股择时", "回购信号",
            "股权激励", "解禁逆向", "龙虎榜跟风", "打板接力", "次新股"],
        5: ["AI供应链瓶颈", "SEPA成长股", "协整配对交易", "Hurst择时动量",
            "游资席位跟踪", "涨停封单", "跌停撬板", "可转债双低", "可转债下修博弈", "ETF折溢价套利"],
        6: ["网格交易", "限售解禁博弈", "戴维斯双击", "困境反转", "股东户数变化",
            "行业动量", "南向资金", "量价齐升", "反过度自信", "行业动量"]
    }
    
    if batch in batches:
        run_batch_backtest(batches[batch], batch)
    else:
        print(f"可用批次: {list(batches.keys())}")
