# -*- coding: utf-8 -*-
"""
回测14个优化后的失败策略

验证优化是否有效，策略是否有交易
"""

import json
import sys
import time
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, r'C:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading')

from data.akshare_helper import AKShareHelper
from strategies.factor_strategies import (
    ROEStrategy, HighROICStrategy, DividendLowVolStrategy, MomentumReversalStrategy
)
from strategies.technical_strategies import (
    KDJOversoldStrategy, MomentumBreakoutStrategy
)
from strategies.southbound_money_strategy import SouthboundMoneyStrategy
from strategies.northbound_money_strategy import NorthboundMoneyStrategy
from strategies.dragon_tiger_list_strategy import DragonTigerListStrategy
from strategies.profit_explosion_strategy import ProfitExplosionStrategy
from strategies.money_flow_event_strategy import MoneyFlowEventStrategy
from strategies.anti_overconfidence_strategy import AntiOverconfidenceStrategy
from strategies.super_short_rebound_strategy import SuperShortReboundStrategy
from strategies.short_term_momentum_strategy import ShortTermMomentumStrategy
from strategies.research_report_strategy import ResearchReportStrategy


# 14个失败策略列表
FAILED_STRATEGIES = {
    # 因子策略
    'ROE选股': ROEStrategy,
    '高ROIC': HighROICStrategy,
    '红利低波': DividendLowVolStrategy,
    '动量反转': MomentumReversalStrategy,
    
    # 技术策略
    'KDJ超卖金叉': KDJOversoldStrategy,
    '动量突破': MomentumBreakoutStrategy,
    
    # 事件策略
    '南向资金': SouthboundMoneyStrategy,
    '北向资金': NorthboundMoneyStrategy,
    '龙虎榜': DragonTigerListStrategy,
    '业绩暴增': ProfitExplosionStrategy,
    '资金流事件': MoneyFlowEventStrategy,
    '反过度自信': AntiOverconfidenceStrategy,
    '超跌反弹': SuperShortReboundStrategy,
    '短线动量': ShortTermMomentumStrategy,
    '研报推荐': ResearchReportStrategy,
}


def backtest_single_strategy(strategy_name, strategy_class, helper, days=5):
    """回测单个策略"""
    try:
        # 创建策略实例
        strategy = strategy_class()
        
        # 回测日期范围（最近5个交易日）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 模拟每日调仓
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y%m%d")
            
            # 选股
            try:
                selected = strategy.select_stocks(helper, date=date_str)
                if selected:
                    print(f"  [{date_str}] 选股成功: {len(selected)}只")
            except Exception as e:
                print(f"  [{date_str}] 选股异常: {e}")
                continue
            
            # API延迟
            time.sleep(1.6)
        
        # 返回结果
        result = {
            'name': strategy.name,
            'category': strategy.category,
            'trades_count': len(strategy.trades),
            'holdings_count': len(strategy.holdings),
            'has_trades': len(strategy.trades) > 0 or len(strategy.holdings) > 0,
            'realized_pnl': strategy.realized_pnl,
            'total_pnl_pct': strategy.get_total_pnl_pct(),
        }
        
        return result
        
    except Exception as e:
        print(f"  回测异常: {e}")
        return {
            'name': strategy_name,
            'error': str(e),
            'has_trades': False,
        }


def main():
    """主函数"""
    print("=" * 60)
    print("回测14个优化后的失败策略")
    print("=" * 60)
    
    # 初始化数据助手
    helper = AKShareHelper()
    
    results = []
    
    for name, strategy_class in FAILED_STRATEGIES.items():
        print(f"\n回测策略: {name}")
        try:
            result = backtest_single_strategy(name, strategy_class, helper, days=3)
            results.append(result)
            
            if result.get('has_trades'):
                print(f"  ✓ 有交易: {result.get('trades_count', 0)}笔交易, {result.get('holdings_count', 0)}持仓")
                print(f"  收益: {result.get('total_pnl_pct', 0):.2f}%")
            else:
                print(f"  ✗ 无交易")
                
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            results.append({
                'name': name,
                'error': str(e),
                'has_trades': False,
            })
    
    # 汇总
    print("\n" + "=" * 60)
    print("回测结果汇总")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r.get('has_trades'))
    fail_count = len(results) - success_count
    
    print(f"\n总计: {len(results)}个策略")
    print(f"有交易: {success_count}个 ✓")
    print(f"无交易: {fail_count}个 ✗")
    
    # 列出有交易的策略
    print("\n有交易的策略:")
    for r in results:
        if r.get('has_trades'):
            print(f"  - {r['name']}: {r.get('trades_count', 0)}笔交易, 收益{r.get('total_pnl_pct', 0):.2f}%")
    
    # 列出无交易的策略
    print("\n无交易的策略:")
    for r in results:
        if not r.get('has_trades'):
            print(f"  - {r['name']}: {r.get('error', '未知原因')}")
    
    # 保存结果
    output_file = r'C:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\optimized_strategies_backtest.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_strategies': len(results),
            'success_count': success_count,
            'fail_count': fail_count,
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")
    
    return results


if __name__ == "__main__":
    main()
