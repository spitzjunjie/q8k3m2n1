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

# 根据环境变量选择主数据源
# GitHub Actions服务器在美国，AKShare爬取中国网站不稳定，使用Tushare API
# 本地默认使用AKShare（免费，功能丰富）
DATA_SOURCE = os.environ.get('DATA_SOURCE', 'akshare').lower()

if DATA_SOURCE == 'tushare':
    PRIMARY_HELPER = TushareHelper
    FALLBACK_HELPER = AKShareHelper
    print(f"[数据源] 主数据源: Tushare (环境变量DATA_SOURCE={DATA_SOURCE})")
else:
    PRIMARY_HELPER = AKShareHelper
    FALLBACK_HELPER = TushareHelper
    print(f"[数据源] 主数据源: AKShare (环境变量DATA_SOURCE={DATA_SOURCE})")


def get_kline_with_fallback(primary_helper, symbol, days=5, end_date=None, source=None):
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
    if source is None:
        source = DATA_SOURCE
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
    ProfitExceedsExpectationStrategy,
    # 新增3个S级策略
    InstitutionResearchStrategy, EarningsPreviewStrategy, NorthboundChangeStrategy
)
from strategies.new_s_strategies import (
    MonthlyResonanceStrategy, MainForceMoneyStrategy,
    NorthMoneyTimingStrategy, EarningsSeasonStrategy
)
# 新增11个GitHub开源研究策略v3
from strategies.moat_strategy import MoatStrategy
from strategies.piotroski_strategy import PiotroskiStrategy
from strategies.garp_strategy import GARPStrategy
from strategies.high_growth_strategy import HighGrowthStrategy
from strategies.cycle_timing_strategy import CycleTimingStrategy
from strategies.repurchase_strategy import RepurchaseStrategy
from strategies.equity_incentive_strategy import EquityIncentiveStrategy
from strategies.lockup_expiry_strategy import LockupExpiryStrategy
from strategies.dragon_tiger_follow_strategy import DragonTigerFollowStrategy
from strategies.limit_up_relay_strategy import LimitUpRelayStrategy
from strategies.new_stock_strategy import NewStockStrategy
# 新增4个研究驱动策略v4（基于海外交易者方法论+量化经典书系）
from strategies.perilla_chokepoint_strategy import PerillaChokepointStrategy
from strategies.sepa_growth_strategy import SEPAGrowthStrategy
from strategies.cointegration_pairs_strategy import CointegrationPairsStrategy
from strategies.hurst_timing_strategy import HurstTimingStrategy
# 新增13个GitHub开源研究策略v5（短线交易类+套利另类类+基本面深度类）
from strategies.auction_selection_strategy import AuctionSelectionStrategy
from strategies.after_hours_momentum_strategy import AfterHoursMomentumStrategy
from strategies.hot_money_tracking_strategy import HotMoneyTrackingStrategy
from strategies.limit_up_seal_strategy import LimitUpSealStrategy
from strategies.limit_down_rebound_strategy import LimitDownReboundStrategy
from strategies.convertible_bond_double_low_strategy import ConvertibleBondDoubleLowStrategy
from strategies.convertible_bond_downward_strategy import ConvertibleBondDownwardStrategy
from strategies.etf_premium_arbitrage_strategy import ETFPremiumArbitrageStrategy
from strategies.grid_trading_strategy import GridTradingStrategy
from strategies.lockup_expiry_arbitrage_strategy import LockupExpiryArbitrageStrategy
from strategies.davis_double_hit_strategy import DavisDoubleHitStrategy
from strategies.turnaround_strategy import TurnaroundStrategy
from strategies.shareholder_change_strategy import ShareholderChangeStrategy
# 新增新闻情感策略（基于FinBERT金融情感分析）
from strategies.news_sentiment_strategy import NewsSentimentStrategy, HotNewsTrackingStrategy
# 新增市场情绪策略
from strategies.market_sentiment_strategy import SentimentIcePointStrategy
# 新增筹码分布策略
from strategies.chips_distribution_strategy import ChipsDistributionStrategy, ChipBreakoutStrategy
# 新增行业轮动策略
from strategies.sector_rotation_strategy import SectorRotationStrategy
# 新增龙头战法策略
from strategies.leading_stock_strategy import LeadingStockStrategy
# 新增质量因子策略
from strategies.quality_factor_strategy import QualityFactorStrategy
# 新增集合竞价策略
from strategies.closing_auction_strategy import ClosingAuctionStrategy


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
        RSIReversalStrategy(),
        MomentumBreakoutStrategy(),
        # 综合 (1)
        MultiFactorStrategy(),
        # 高级策略 (4) - 新增（移除重复注册：OversoldRebound/ValueLowPB/AdvEarningsSurprise）
        IndustryMomentumStrategy(),
        SouthboundFlowStrategy(),
        AdvVolumeBreakout(),
        # 新策略 (17个) - 完整导入（移除重复注册：GoldenCross/RSIRebound/HighDividend/ProfitExceeds）
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
        LowPBValueStrategy(),               # 低PB价值
        KDJStrategy(),                      # KDJ超卖金叉
        # 新增3个S级策略
        InstitutionResearchStrategy(),      # 机构调研
        EarningsPreviewStrategy(),          # 业绩预告超预期
        NorthboundChangeStrategy(),         # 北向持仓变化
        # 新增5个S级策略v2
        MonthlyResonanceStrategy(),         # 月线共振
        MainForceMoneyStrategy(),           # 主力资金
        NorthMoneyTimingStrategy(),         # 北向择时
        EarningsSeasonStrategy(),           # 财报季
        # 新增11个GitHub开源研究策略v3
        MoatStrategy(),                    # 护城河选股
        PiotroskiStrategy(),               # 质量因子选股
        GARPStrategy(),                    # GARP成长
        HighGrowthStrategy(),              # 高成长股
        CycleTimingStrategy(),             # 周期股择时
        RepurchaseStrategy(),              # 回购信号
        EquityIncentiveStrategy(),         # 股权激励
        LockupExpiryStrategy(),            # 解禁逆向
        DragonTigerFollowStrategy(),       # 龙虎榜跟风
        LimitUpRelayStrategy(),            # 打板接力
        NewStockStrategy(),                # 次新股
        # 新增4个研究驱动策略v4（基于海外交易者方法论+量化经典书系）
        PerillaChokepointStrategy(),       # AI供应链瓶颈（Serenity瓶颈理论）
        SEPAGrowthStrategy(),              # SEPA成长股（Minervini SEPA）
        CointegrationPairsStrategy(),      # 协整配对交易（Chan统计套利）
        HurstTimingStrategy(),             # Hurst择时动量（Hurst指数择时）
        # 新增13个GitHub开源研究策略v5（短线交易类+套利另类类+基本面深度类）
        AuctionSelectionStrategy(),        # 集合竞价选股
        AfterHoursMomentumStrategy(),      # 尾盘抢筹
        HotMoneyTrackingStrategy(),        # 游资席位跟踪
        LimitUpSealStrategy(),             # 涨停封单
        LimitDownReboundStrategy(),        # 跌停撬板
        ConvertibleBondDoubleLowStrategy(), # 可转债双低
        ConvertibleBondDownwardStrategy(), # 可转债下修博弈
        ETFPremiumArbitrageStrategy(),     # ETF折溢价套利
        GridTradingStrategy(),             # 网格交易
        LockupExpiryArbitrageStrategy(),  # 限售解禁博弈
        DavisDoubleHitStrategy(),          # 戴维斯双击
        TurnaroundStrategy(),              # 困境反转
        ShareholderChangeStrategy(),       # 股东户数变化
        # 新增新闻情感策略（基于FinBERT金融情感分析）
        NewsSentimentStrategy(),           # 新闻情感选股
        HotNewsTrackingStrategy(),         # 热点新闻追踪
        # 新增市场情绪策略（情绪冰点抄底）
        SentimentIcePointStrategy(),       # 情绪冰点抄底
        # 新增筹码分布策略
        ChipsDistributionStrategy(),        # 筹码分布
        ChipBreakoutStrategy(),            # 筹码突破
        # 新增行业轮动策略
        SectorRotationStrategy(),          # 行业轮动
        # 新增龙头战法策略
        LeadingStockStrategy(),            # 龙头战法
        # 新增质量因子策略
        QualityFactorStrategy(),            # 质量因子选股
        # 新增集合竞价策略
        ClosingAuctionStrategy(),          # 集合竞价选股
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
        current_source = DATA_SOURCE
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

    print(f"\n结果已保存到: {main_file}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    main()
