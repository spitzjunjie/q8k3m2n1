# -*- coding: utf-8 -*-
"""
快速测试策略选股能力（不使用完整回测）
"""

import sys
import time
sys.path.insert(0, r'C:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading')

from data.akshare_helper import AKShareHelper
from strategies.factor_strategies import ROEStrategy, HighROICStrategy, DividendLowVolStrategy, MomentumReversalStrategy
from strategies.technical_strategies import KDJOversoldStrategy, MomentumBreakoutStrategy
from strategies.southbound_money_strategy import SouthboundMoneyStrategy
from strategies.northbound_money_strategy import NorthboundMoneyStrategy
from strategies.dragon_tiger_list_strategy import DragonTigerListStrategy
from strategies.profit_explosion_strategy import ProfitExplosionStrategy
from strategies.money_flow_event_strategy import MoneyFlowEventStrategy
from strategies.anti_overconfidence_strategy import AntiOverconfidenceStrategy
from strategies.super_short_rebound_strategy import SuperShortReboundStrategy
from strategies.short_term_momentum_strategy import ShortTermMomentumStrategy
from strategies.research_report_strategy import ResearchReportStrategy


def test_select(strategy_class, name):
    """测试策略选股能力"""
    try:
        helper = AKShareHelper()
        strategy = strategy_class()
        
        # 选股
        selected = strategy.select_stocks(helper, date=None)
        
        if selected:
            print(f"✓ {name}: 选出 {len(selected)} 只股票")
            for s in selected[:3]:
                print(f"    - {s['symbol']} {s.get('name','')}: {s.get('reason','')[:40]}")
            return True, len(selected)
        else:
            print(f"✗ {name}: 无股票选出")
            return False, 0
            
    except Exception as e:
        print(f"✗ {name}: 异常 - {e}")
        return False, 0


# 14个失败策略测试
strategies = [
    # 因子策略
    (ROEStrategy, "ROE选股"),
    (HighROICStrategy, "高ROIC"),
    (DividendLowVolStrategy, "红利低波"),
    (MomentumReversalStrategy, "动量反转"),
    # 技术策略
    (KDJOversoldStrategy, "KDJ超卖金叉"),
    (MomentumBreakoutStrategy, "动量突破"),
    # 事件策略
    (SouthboundMoneyStrategy, "南向资金"),
    (NorthboundMoneyStrategy, "北向资金"),
    (DragonTigerListStrategy, "龙虎榜"),
    (ProfitExplosionStrategy, "业绩暴增"),
    (MoneyFlowEventStrategy, "资金流事件"),
    (AntiOverconfidenceStrategy, "反过度自信"),
    (SuperShortReboundStrategy, "超跌反弹"),
    (ShortTermMomentumStrategy, "短线动量"),
    (ResearchReportStrategy, "研报推荐"),
]

print("="*60)
print("测试14个优化后的失败策略选股能力")
print("="*60)

results = []
for strategy_class, name in strategies:
    time.sleep(1.6)  # API延迟
    has_stocks, count = test_select(strategy_class, name)
    results.append({
        'name': name,
        'has_stocks': has_stocks,
        'count': count
    })

# 汇总
print("\n" + "="*60)
print("汇总")
print("="*60)

success = [r for r in results if r['has_stocks']]
fail = [r for r in results if not r['has_stocks']]

print(f"成功选出股票: {len(success)}/{len(results)}")
print(f"无股票选出: {len(fail)}/{len(results)}")

if success:
    print("\n成功策略:")
    for r in success:
        print(f"  ✓ {r['name']}: {r['count']}只")

if fail:
    print("\n失败策略:")
    for r in fail:
        print(f"  ✗ {r['name']}")
