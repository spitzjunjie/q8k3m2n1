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
import pandas as pd

from data.akshare_helper import AKShareHelper
from data.tushare_helper import TushareHelper

# 使用AKShare作为主数据源，Tushare作为备用
PRIMARY_HELPER = AKShareHelper
FALLBACK_HELPER = TushareHelper


def get_kline_with_fallback(primary_helper, symbol, days=5, end_date=None, source='akshare'):
    """获取K线数据，失败时自动切换数据源
    
    Args:
        primary_helper: 主数据源
        symbol: 股票代码
        days: 天数
        end_date: 结束日期
        source: 当前数据源标识
    
    Returns:
        DataFrame 或 None
    """
    try:
        df = primary_helper.get_history_kline(symbol, days=days, end_date=end_date)
        if isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
            return df, source
    except Exception as e:
        pass
    
    # 切换到备用数据源
    fallback_source = 'tushare' if source == 'akshare' else 'akshare'
    try:
        df = fallback_helper.get_history_kline(symbol, days=days, end_date=end_date)
        if isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
            print(f"    [切换数据源] {symbol}: {source} -> {fallback_source}")
            return df, fallback_source
    except:
        pass
    
    return None, source


# 全局备用helper实例
fallback_helper = FALLBACK_HELPER(cache_dir="data/cache")
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
from strategies.new_strategies import (
    ETFRotationStrategy, FundamentalSmallCapStrategy, MoneyFlowEventStrategy,
    AntiOverconfidenceStrategy, ResearchReportStrategy, SuperShortReboundStrategy,
    ShortTermMomentumStrategy, LowVolatilityStrategy, DragonTigerListStrategy,
    NorthboundMoneyStrategy, ValueGrowthStrategy, ProfitExplosionStrategy,
    ContinuousVolumeStrategy, LimitCallbackStrategy, GoldenCrossStrategy,
    RSIReboundStrategy, LowPBValueStrategy, KDJStrategy, HighDividendStrategy,
    ProfitExceedsExpectationStrategy
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
        # 新策略 (22个) - 完整导入
        ETFRotationStrategy(),              # ETF二八轮动
        FundamentalSmallCapStrategy(),      # 财务基本面过滤小市值
        MoneyFlowEventStrategy(),           # 资金流事件
        AntiOverconfidenceStrategy(),       # 反过度自信
        ResearchReportStrategy(),           # 研报推荐
        SuperShortReboundStrategy(),        # 超跌反弹
        ShortTermMomentumStrategy(),        # 短线动量
        LowVolatilityStrategy(),            # 低波动
        DragonTigerListStrategy(),          # 龙虎榜
        NorthboundMoneyStrategy(),          # 北向资金
        ValueGrowthStrategy(),              # 价值成长
        ProfitExplosionStrategy(),          # 业绩暴增
        ContinuousVolumeStrategy(),         # 量价齐升
        LimitCallbackStrategy(),            # 涨停回调
        GoldenCrossStrategy(),              # MACD金叉
        RSIReboundStrategy(),               # RSI超卖反转
        LowPBValueStrategy(),               # 低PB价值
        KDJStrategy(),                      # KDJ超卖金叉
        HighDividendStrategy(),             # 高股息
        ProfitExceedsExpectationStrategy(), # 业绩超预期
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

        # 2. 获取股票价格（带自动切换数据源）
        prices = {}
        current_source = 'akshare'
        for stock in selected[:30]:  # 扩大到前30只（原10只太少）
            try:
                df, current_source = get_kline_with_fallback(helper, stock['symbol'], days=5, end_date=date, source=current_source)
                # 严格验证：确保是DataFrame、有数据、有close列、是数字
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price) and isinstance(close_price, (int, float)):
                        prices[stock['symbol']] = float(close_price)
            except:
                continue

        # 3. 检查现有持仓（带自动切换数据源）
        for holding in strategy.holdings:
            symbol = holding['symbol']
            try:
                df, current_source = get_kline_with_fallback(helper, symbol, days=5, end_date=date, source=current_source)
                # 严格验证
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price) and isinstance(close_price, (int, float)):
                        prices[symbol] = float(close_price)
                        # 检查是否需要卖出
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

    # 新开发的策略列表（22个）- 只回测这些
    NEW_STRATEGIES = {
        'ETF二八轮动', '财务基本面过滤小市值', '资金流事件', '反过度自信',
        '行业动量', '研报推荐', '超跌反弹', '短线动量', '低波动',
        '南向资金', '龙虎榜', '北向资金', '价值成长', '业绩暴增',
        '量价齐升', '涨停回调', 'MACD金叉', 'RSI超卖反转',
        '低PB价值', 'KDJ超卖金叉', '高股息', '业绩超预期'
    }

    # 初始化
    helper = PRIMARY_HELPER(cache_dir="data/cache")
    timing = TimingEngine()
    all_strategies = get_all_strategies()

    # 回测所有策略（Dashboard上线的所有策略）
    strategies = all_strategies

    print(f"\n共 {len(strategies)} 个策略（所有上线策略）\n")

    # 并行运行策略
    results = []
    
    # 使用线程池并行执行（减少并发避免频率限制）
    with ThreadPoolExecutor(max_workers=2) as executor:
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

    # 保存结果 - 增量合并模式
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # 增量合并到主数据文件（只更新本次回测的策略，保留其他策略的数据）
    main_file = os.path.join(output_dir, 'strategy_data.json')
    
    # 读取现有数据
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
        existing_strategies = {s['name']: s for s in main_data.get('strategies', [])}
        existing_update_time = main_data.get('update_time', '')
    else:
        main_data = {'strategies': []}
        existing_strategies = {}
        existing_update_time = ''
    
    # 只更新本次回测中有交易的策略，保留其他策略的数据
    merged_count = 0
    for result in results:
        name = result['name']
        # 只更新有实际交易的策略
        if result.get('trades') or result.get('total_return', 0) != 0:
            existing_strategies[name] = result
            merged_count += 1
    
    # 构建新的主数据（按综合分排序）
    main_data['strategies'] = list(existing_strategies.values())
    main_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    main_data['strategy_count'] = len(main_data['strategies'])
    
    # 保存
    with open(main_file, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 已增量合并 {merged_count} 个策略到 strategy_data.json")
    print(f"   保留 {len(existing_strategies) - merged_count} 个未回测策略的数据")
    print(f"   主数据文件: {main_file}")

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
