# -*- coding: utf-8 -*-
"""
多策略回测引擎
主程序入口
"""

import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

from data.tushare_helper import TushareHelper

# 使用Tushare作为主数据源（更稳定）
Helper = TushareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator

# 导入所有策略
from strategies.factor_strategies import (
    ROEStrategy, ProfitGrowthStrategy, RevenueGrowthStrategy,
    LowPEStrategy, LowPBStrategy, PSRStrategy, LowValuationStrategy,
    CashFlowQualityStrategy, HighROICStrategy, LowDebtStrategy,
    HighDividendStrategy, DividendLowVolStrategy,
    NorthHeavyStrategy, InstitutionHoldingStrategy,
    MomentumReversalStrategy as FactorMomentumReversal,
    TrendMomentumStrategy as FactorTrendMomentum
)
from strategies.event_strategies import (
    MomentumReversalStrategy, TrendMomentumStrategy, NorthFlowStrategy,
    LimitUpCallbackStrategy, STRemoveStrategy,
    ExecutiveBuyStrategy, EarningsSurpriseStrategy, AnalystUpgradeStrategy,
    MultiFactorStrategy as EventMultiFactor
)
from strategies.special_strategies import (
    AISupplyChainStrategy, LocalizationStrategy,
    MaBreakStrategy, MultiPeriodStrategy, MultiFactorStrategy
)
from strategies.technical_strategies import (
    VolumeBreakoutStrategy, MACDCrossStrategy, KDJOversoldStrategy,
    RSIReversalStrategy, MomentumBreakoutStrategy
)
from strategies.advanced_strategies import (
    IndustryMomentumStrategy, SouthboundFlowStrategy, OversoldReboundStrategy,
    ValueLowPBStrategy, EarningsSurpriseStrategy as AdvEarningsSurprise,
    VolumeBreakoutStrategy as AdvVolumeBreakout
)


def get_all_strategies():
    """获取所有策略实例"""
    strategies = [
        # 紫苏叶策略 (2)
        AISupplyChainStrategy(),
        LocalizationStrategy(),
        # 盈利因子 (3)
        ROEStrategy(),
        ProfitGrowthStrategy(),
        RevenueGrowthStrategy(),
        # 价值因子 (4)
        LowPEStrategy(),
        LowPBStrategy(),
        PSRStrategy(),
        LowValuationStrategy(),
        # 质量因子 (3)
        CashFlowQualityStrategy(),
        HighROICStrategy(),
        LowDebtStrategy(),
        # 红利因子 (2)
        HighDividendStrategy(),
        DividendLowVolStrategy(),
        # 动量因子 (2)
        MomentumReversalStrategy(),
        TrendMomentumStrategy(),
        # 趋势策略 (2)
        MaBreakStrategy(),
        MultiPeriodStrategy(),
        # 资金因子 (3)
        NorthHeavyStrategy(),
        InstitutionHoldingStrategy(),
        NorthFlowStrategy(),
        # 事件驱动 (4)
        LimitUpCallbackStrategy(),
        STRemoveStrategy(),
        ExecutiveBuyStrategy(),
        EarningsSurpriseStrategy(),
        AnalystUpgradeStrategy(),
        # 技术突破 (5) - 捕捉放量突破、动能突破
        VolumeBreakoutStrategy(),
        MACDCrossStrategy(),
        KDJOversoldStrategy(),
        RSIReversalStrategy(),
        MomentumBreakoutStrategy(),
        # 综合 (1)
        MultiFactorStrategy(),
        # 高级策略 (6) - 新增
        IndustryMomentumStrategy(),
        SouthboundFlowStrategy(),
        OversoldReboundStrategy(),
        ValueLowPBStrategy(),
        AdvEarningsSurprise(),
        AdvVolumeBreakout(),
    ]
    return strategies


def run_strategy(strategy, helper, timing, date=None):
    """运行单个策略
    date: 指定运行日期(YYYY-MM-DD)，None=今天（用于历史回测）
    """
    try:
        print(f"运行策略: {strategy.name}" + (f" 日期:{date}" if date else ""))
        simulator = TradingSimulator(strategy, timing)

        # 1. 选股（传入date用于历史回测）
        selected = strategy.select_stocks(helper, date)

        # 2. 获取股票价格
        prices = {}
        for stock in selected[:30]:  # 扩大到前30只（原10只太少）
            try:
                df = helper.get_history_kline(stock['symbol'], days=5, end_date=date)
                if not df.empty:
                    prices[stock['symbol']] = df['close'].iloc[-1]
            except:
                continue

        # 3. 检查现有持仓
        for holding in strategy.holdings:
            symbol = holding['symbol']
            try:
                df = helper.get_history_kline(symbol, days=5, end_date=date)
                if not df.empty:
                    prices[symbol] = df['close'].iloc[-1]
                    # 检查是否需要卖出（传helper+date，消除未来函数Bug）
                    should_sell, reason = simulator.check_and_sell(
                        symbol, prices[symbol], helper=helper, date=date)
                    if should_sell:
                        simulator.execute_sell(symbol, prices[symbol], reason, sell_date=date)
            except:
                continue

        # 4. 尝试买入新股票
        for stock in selected:
            if len(strategy.holdings) >= simulator.max_holdings:
                break

            symbol = stock['symbol']
            if symbol in prices:
                result, msg = simulator.execute_buy(
                    symbol,
                    stock.get('name', symbol),
                    prices[symbol],
                    stock.get('reason', ''),
                    helper=helper,
                    date=date
                )
                if result:
                    print(f"  买入 {stock['name']}: {msg}")
        
        # 5. 更新持仓状态
        simulator.update_positions(prices)
        
        # 6. 记录权益曲线
        total_value = strategy.get_total_value(prices)
        strategy.equity_curve.append(total_value)
        
        # 7. 返回策略结果
        return strategy.to_dict(prices)
    
    except Exception as e:
        print(f"策略 {strategy.name} 运行失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'name': strategy.name,
            'category': strategy.category,
            'error': str(e),
            'total_value': strategy.initial_capital,
            'total_return': 0,
            'holdings': [],
            'trades': [],
            'equity_curve': []
        }


def main():
    """主函数"""
    print("=" * 60)
    print("多策略模拟交易系统")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 初始化
    helper = Helper(cache_dir="data/cache")
    timing = TimingEngine()
    strategies = get_all_strategies()
    
    print(f"\n共 {len(strategies)} 个策略\n")
    
    # 并行运行策略
    results = []
    
    # 使用线程池并行执行
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(run_strategy, strategy, helper, timing): strategy
            for strategy in strategies
        }
        
        for future in as_completed(futures):
            strategy = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"完成: {result['name']}")
            except Exception as e:
                print(f"策略 {strategy.name} 执行异常: {e}")
    
    # 用综合评分排序（夏普30%+收益25%+回撤20%+胜率15%+稳定性10%）
    from evaluation import StrategyEvaluator
    evaluator = StrategyEvaluator()
    evaluations = evaluator.evaluate_batch(results)
    # 把评估结果合并到每个strategy result中（供Dashboard展示等级徽章）
    for r, e in zip(results, evaluations):
        r['composite_score'] = e['composite_score']
        r['grade'] = e['grade']
        r['profit_loss_ratio'] = e['profit_loss_ratio']
        r['return_stability'] = e['return_stability']
        r['calmar_ratio'] = e['calmar_ratio']
    # 按综合分排序（不再是单一total_return）
    results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    # 生成输出数据
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'strategy_count': len(results),
        'grade_stats': evaluator.grade_stats(evaluations),
        'strategies': results
    }

    # 保存结果
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'strategy_data.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 60)
    print("策略排名（按综合分）")
    print("=" * 60)

    grade_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉', 'D': '⚠️'}
    for i, r in enumerate(results, 1):
        name = r.get('name', 'Unknown')
        ret = r.get('total_return', 0) * 100
        value = r.get('total_value', 0)
        score = r.get('composite_score', 0)
        grade = r.get('grade', 'D')
        sharpe = r.get('sharpe_ratio', 0)
        print(f"{i:2}. {grade_emoji.get(grade,'')} {name:<18} 分数:{score:>5.1f} 收益:{ret:>+7.2f}% 夏普:{sharpe:>5.2f} 权益:¥{value:,.0f}")

    print(f"\n结果已保存到: {output_file}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    main()
