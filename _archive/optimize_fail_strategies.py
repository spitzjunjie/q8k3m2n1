# -*- coding: utf-8 -*-
"""
优化14个失败策略的选股逻辑

问题分析：
1. 因子策略：样本少(60)、过滤条件太严格
2. 技术策略：多重条件同时满足太难
3. 事件策略：模拟股票池标的少 + 技术条件筛选严格
"""

import os
import sys
import time

# 延迟装饰器（API限制：延迟≥1.5秒，并发≤2）
def rate_limit_delay(func):
    """添加API延迟，避免并发过高"""
    def wrapper(*args, **kwargs):
        time.sleep(1.6)  # 1.6秒延迟
        return func(*args, **kwargs)
    return wrapper

# ============== 优化1: 因子策略 ==============
# ROE选股、高ROIC、红利低波、动量反转、分析师上调

def optimize_factor_strategies():
    """优化因子策略"""
    print("=" * 50)
    print("优化因子策略")
    print("=" * 50)
    
    changes = []
    
    # 1. ROE选股优化
    # 原: sample=60, head=30
    # 优化: sample=120, head=50
    changes.append({
        'strategy': 'ROE选股',
        'file': 'factor_strategies.py',
        'class': 'ROEStrategy',
        'change': 'sample=60 -> sample=120, head(30) -> head(50)',
        'reason': '扩大样本池，增加可选标的'
    })
    
    # 2. 高ROIC优化
    changes.append({
        'strategy': '高ROIC',
        'file': 'factor_strategies.py',
        'class': 'HighROICStrategy',
        'change': 'sample=60 -> sample=120, head(30) -> head(50)',
        'reason': '扩大样本池'
    })
    
    # 3. 红利低波优化
    changes.append({
        'strategy': '红利低波',
        'file': 'factor_strategies.py',
        'class': 'DividendLowVolStrategy',
        'change': 'sample=60 -> sample=120, head(30) -> head(50), 波动率计算优化',
        'reason': '扩大样本池，优化波动率计算'
    })
    
    # 4. 动量反转优化
    changes.append({
        'strategy': '动量反转',
        'file': 'factor_strategies.py',
        'class': 'MomentumReversalStrategy',
        'change': 'sample=60 -> sample=120, ROE>5% -> ROE>3%, head(30) -> head(50)',
        'reason': '放宽ROE要求，扩大样本池'
    })
    
    return changes


# ============== 优化2: 技术策略 ==============
# KDJ超卖金叉、动量突破

def optimize_technical_strategies():
    """优化技术策略"""
    print("=" * 50)
    print("优化技术策略")
    print("=" * 50)
    
    changes = []
    
    # 1. KDJ超卖金叉优化
    changes.append({
        'strategy': 'KDJ超卖金叉',
        'file': 'technical_strategies.py',
        'class': 'KDJOversoldStrategy',
        'change': 'sample=80 -> sample=120, K<40 -> K<50, 移除J值从负转正要求',
        'reason': '放宽超卖标准，移除过于严格的条件'
    })
    
    # 2. 动量突破优化
    changes.append({
        'strategy': '动量突破',
        'file': 'technical_strategies.py',
        'class': 'MomentumBreakoutStrategy',
        'change': 'sample=80 -> sample=120, 4个条件 -> 2个核心条件即可',
        'reason': '放宽条件组合，核心是突破+放量'
    })
    
    return changes


# ============== 优化3: 事件策略 ==============
# 南向资金、北向资金、龙虎榜、业绩暴增、资金流事件、反过度自信、超跌反弹、短线动量、研报推荐

def optimize_event_strategies():
    """优化事件策略"""
    print("=" * 50)
    print("优化事件策略")
    print("=" * 50)
    
    changes = []
    
    # 1. 南向资金优化
    changes.append({
        'strategy': '南向资金',
        'file': 'southbound_money_strategy.py',
        'change': '移除趋势向上条件，只保留成交量放大条件',
        'reason': '原条件太严格导致无股票入选'
    })
    
    # 2. 北向资金优化
    changes.append({
        'strategy': '北向资金',
        'file': 'northbound_money_strategy.py',
        'change': '移除趋势向上条件，只保留成交量放大条件',
        'reason': '原条件太严格导致无股票入选'
    })
    
    # 3. 龙虎榜优化
    changes.append({
        'strategy': '龙虎榜',
        'file': 'dragon_tiger_list_strategy.py',
        'change': '移除成交额放大条件，改为趋势向上即可',
        'reason': '原条件太严格'
    })
    
    # 4. 业绩暴增优化
    changes.append({
        'strategy': '业绩暴增',
        'file': 'profit_explosion_strategy.py',
        'change': '移除趋势向上条件，只要有股票池即可入选',
        'reason': '业绩暴增本身就是选股理由'
    })
    
    # 5. 资金流事件优化
    changes.append({
        'strategy': '资金流事件',
        'file': 'money_flow_event_strategy.py',
        'change': '成交量放大20% -> 10%',
        'reason': '放宽成交量要求'
    })
    
    # 6. 反过度自信优化
    changes.append({
        'strategy': '反过度自信',
        'file': 'anti_overconfidence_strategy.py',
        'change': 'RSI<40 -> RSI<50, 跌幅10-30% -> 5-30%, 移除企稳条件',
        'reason': '放宽条件组合'
    })
    
    # 7. 超跌反弹优化
    changes.append({
        'strategy': '超跌反弹',
        'file': 'super_short_rebound_strategy.py',
        'change': 'RSI<35 -> RSI<45, 跌幅>15% -> 跌幅>10%, 移除企稳条件',
        'reason': '放宽超卖标准'
    })
    
    # 8. 短线动量优化
    changes.append({
        'strategy': '短线动量',
        'file': 'short_term_momentum_strategy.py',
        'change': '涨幅>0 -> 涨幅>-2%, 量比>1.2 -> 量比>0.8, 移除趋势向上条件',
        'reason': '放宽动量条件'
    })
    
    # 9. 研报推荐优化
    changes.append({
        'strategy': '研报推荐',
        'file': 'research_report_strategy.py',
        'change': '移除趋势向上条件，只要有股票池即可入选',
        'reason': '研报推荐本身就是选股理由'
    })
    
    return changes


def print_all_changes():
    """打印所有优化方案"""
    print("\n" + "=" * 60)
    print("14个失败策略优化方案汇总")
    print("=" * 60)
    
    all_changes = []
    all_changes.extend(optimize_factor_strategies())
    all_changes.extend(optimize_technical_strategies())
    all_changes.extend(optimize_event_strategies())
    
    for i, change in enumerate(all_changes, 1):
        print(f"\n{i}. {change['strategy']}")
        print(f"   文件: {change['file']}")
        print(f"   优化: {change['change']}")
        print(f"   原因: {change['reason']}")
    
    print(f"\n总计: {len(all_changes)} 个策略需要优化")
    return all_changes


if __name__ == "__main__":
    print_all_changes()
