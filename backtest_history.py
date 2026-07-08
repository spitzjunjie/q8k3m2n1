# -*- coding: utf-8 -*-
"""
历史回测引擎
在过去N个交易日逐日运行策略，生成历史权益曲线和交易记录
用于验证策略在历史数据上的表现
"""

import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# 数据源选择
DATA_SOURCE = 'tushare'  # 可选: 'tushare' 或 'akshare'

# 【新增】备用数据源映射
DATA_SOURCE_SWITCH = {
    'tushare': 'akshare',
    'akshare': 'tushare'
}

# 【新增】导入两个Helper
from data.tushare_helper import TushareHelper
from data.akshare_helper import AKShareHelper

from timing.timing import TimingEngine
from trading.simulator import TradingSimulator
from backtest import get_all_strategies

# 新开发的策略列表（22个）
NEW_STRATEGIES = {
    'ETF二八轮动', '财务基本面过滤小市值', '资金流事件', '反过度自信',
    '行业动量', '研报推荐', '超跌反弹', '短线动量', '低波动',
    '南向资金', '龙虎榜', '北向资金', '价值成长', '业绩暴增',
    '量价齐升', '涨停回调', 'MACD金叉', 'RSI超卖反转',
    '低PB价值', 'KDJ超卖金叉', '高股息', '业绩超预期'
}

# 基准日期：第一批策略开始回测的日期
BENCHMARK_START_DATE = datetime(2026, 5, 26)


def run_strategy_on_date(strategy, helper, timing, date):
    """在指定历史日期运行单个策略
    date: YYYY-MM-DD格式字符串
    """
    try:
        simulator = TradingSimulator(strategy, timing)

        # 1. 选股（传入历史日期）
        selected = strategy.select_stocks(helper, date)

        # 2. 获取选股当日收盘价（严格验证数据）
        prices = {}
        for stock in selected[:30]:
            try:
                df = helper.get_history_kline(stock['symbol'], days=5, end_date=date)
                # 严格验证
                if isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price) and isinstance(close_price, (int, float)):
                        prices[stock['symbol']] = float(close_price)
            except Exception:
                continue

        # 3. 检查现有持仓并卖出
        for holding in strategy.holdings:
            symbol = holding['symbol']
            try:
                df = helper.get_history_kline(symbol, days=5, end_date=date)
                if isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price) and isinstance(close_price, (int, float)):
                        prices[symbol] = float(close_price)
                        should_sell, reason = simulator.check_and_sell(
                            symbol, prices[symbol], helper=helper, date=date)
                        if should_sell:
                            simulator.execute_sell(symbol, prices[symbol], reason, sell_date=date)
            except Exception:
                continue

        # 4. 尝试买入新股票（T+1：当日选股，次日开盘价成交）
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
                    print(f"  [{date}] {strategy.name} 买入 {stock.get('name', symbol)}: {msg}")

        # 5. 更新持仓状态
        simulator.update_positions(prices)

        # 6. 记录权益曲线（带日期）
        total_value = strategy.get_total_value(prices)
        strategy.equity_curve.append({'date': date, 'value': total_value})

        return total_value
    except Exception as e:
        print(f"[{date}] 策略 {strategy.name} 运行失败: {e}")
        return None


def run_historical_backtest(strategy_names=None, days=None, max_workers=2):
    """历史回测主函数

    Args:
        strategy_names: 指定策略名列表，None=全部
        days: 回测交易日天数，None=自动计算（从基准日期到今天）
        max_workers: 并行线程数（减少避免频率限制）

    Returns:
        dict: 回测结果，包含每个策略的最终状态
    """
    # 根据数据源选择Helper类
    if DATA_SOURCE == 'tushare':
        from data.tushare_helper import TushareHelper
        HelperClass = TushareHelper
    else:
        from data.akshare_helper import AKShareHelper
        HelperClass = AKShareHelper

    # 自动计算回测天数（交易日数）
    helper = HelperClass(cache_dir="data/cache")
    
    # 计算从基准日期到今天有多少个交易日
    if hasattr(helper, 'get_trade_dates'):
        temp_dates = helper.get_trade_dates(days=1000)
    else:
        temp_dates = helper.get_trading_dates(n=1000)
    benchmark_str = BENCHMARK_START_DATE.strftime('%Y%m%d')
    actual_days = len([d for d in temp_dates if d >= benchmark_str])
    
    if days is None or days > actual_days:
        days = actual_days  # 使用实际的交易日数
        print(f"自动调整回测天数: {days}个交易日（从基准日期到今天）")

    print("=" * 60)
    print("历史回测引擎")
    print(f"基准日期: {BENCHMARK_START_DATE.strftime('%Y-%m-%d')}")
    print(f"回测天数: {days}个交易日")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    timing = TimingEngine()

    # 获取交易日列表（兼容AKShare和Tushare）
    if hasattr(helper, 'get_trade_dates'):
        trading_dates = helper.get_trade_dates(days=days)
    elif hasattr(helper, 'get_trading_dates'):
        trading_dates = helper.get_trading_dates(n=days)
    else:
        print("获取交易日失败，无法回测")
        return None
    if not trading_dates:
        print("获取交易日失败，无法回测")
        return None

    print(f"回测区间: {trading_dates[0]} ~ {trading_dates[-1]}")

    # 获取策略
    all_strategies = get_all_strategies()
    
    # 如果指定了策略名，只回测指定的策略
    if strategy_names:
        strategies = [s for s in all_strategies if s.name in strategy_names]
        print(f"回测策略数: {len(strategies)}（指定策略: {strategy_names}）\n")
    else:
        # 默认只回测新策略
        strategies = [s for s in all_strategies if s.name in NEW_STRATEGIES]
        print(f"回测策略数: {len(strategies)}（只回测新策略）\n")

    # 逐日运行（每个策略独立，但日期是共享的）
    # 对每个策略，从头开始逐日运行
    results = []

    def run_single_strategy(strategy, helper_instance=None, source_switched=False):
        """运行单个策略的完整历史回测（支持自动切换数据源）
        
        Args:
            strategy: 策略实例
            helper_instance: 数据源Helper实例
            source_switched: 是否已切换过数据源（防止无限循环）
        """
        nonlocal helper
        
        # 使用指定的helper
        if helper_instance is None:
            helper_instance = helper
        
        # 重置策略状态（设置默认值）
        if not hasattr(strategy, 'initial_capital') or strategy.initial_capital is None:
            strategy.initial_capital = 30000
        if not hasattr(strategy, 'current_capital'):
            strategy.current_capital = strategy.initial_capital
        if not hasattr(strategy, 'holdings'):
            strategy.holdings = []
        if not hasattr(strategy, 'trades'):
            strategy.trades = []
        if not hasattr(strategy, 'equity_curve'):
            strategy.equity_curve = []
        if not hasattr(strategy, 'realized_pnl'):
            strategy.realized_pnl = 0.0
        if not hasattr(strategy, 'realized_pnl_pct'):
            strategy.realized_pnl_pct = 0.0

        # 确保有select_stocks方法
        if not hasattr(strategy, 'select_stocks'):
            print(f"策略 {strategy.name} 没有select_stocks方法，跳过")
            return None

        print(f"\n开始回测: {strategy.name} [数据源: {DATA_SOURCE}]")
        
        # 记录交易次数，用于判断是否成功获取数据
        initial_trades = len(strategy.trades)
        
        try:
            for date in trading_dates:
                run_strategy_on_date(strategy, helper_instance, timing, date)
        except Exception as e:
            print(f"[错误] 策略 {strategy.name} 回测异常: {e}")
            # 自动切换数据源重试
            if not source_switched:
                print(f"[切换] 自动切换数据源重试: {DATA_SOURCE} -> {DATA_SOURCE_SWITCH.get(DATA_SOURCE, 'tushare')}")
                # 创建新的helper
                new_source = DATA_SOURCE_SWITCH.get(DATA_SOURCE, 'tushare')
                if new_source == 'tushare':
                    new_helper = TushareHelper(cache_dir="data/cache")
                else:
                    new_helper = AKShareHelper(cache_dir="data/cache")
                # 重置策略状态
                strategy.current_capital = strategy.initial_capital
                strategy.holdings = []
                strategy.trades = []
                strategy.equity_curve = []
                strategy.realized_pnl = 0.0
                strategy.realized_pnl_pct = 0.0
                # 递归调用（只切换一次）
                return run_single_strategy(strategy, new_helper, source_switched=True)
            else:
                print(f"[失败] 数据源已切换过一次，仍失败: {strategy.name}")
                return None

        # 【新增】检查是否有实际交易，如果没有则切换数据源重试
        if len(strategy.trades) == initial_trades and len(strategy.equity_curve) == 0:
            print(f"[警告] 策略 {strategy.name} 无交易记录，尝试切换数据源...")
            if not source_switched:
                new_source = DATA_SOURCE_SWITCH.get(DATA_SOURCE, 'tushare')
                print(f"[切换] 自动切换数据源重试: {DATA_SOURCE} -> {new_source}")
                if new_source == 'tushare':
                    new_helper = TushareHelper(cache_dir="data/cache")
                else:
                    new_helper = AKShareHelper(cache_dir="data/cache")
                # 重置策略状态
                strategy.current_capital = strategy.initial_capital
                strategy.holdings = []
                strategy.trades = []
                strategy.equity_curve = []
                strategy.realized_pnl = 0.0
                strategy.realized_pnl_pct = 0.0
                return run_single_strategy(strategy, new_helper, source_switched=True)

        # 返回策略最终状态
        # 获取最新价格计算浮动收益
        last_date = trading_dates[-1]
        prices = {}
        for h in strategy.holdings:
            try:
                df = helper_instance.get_history_kline(h['symbol'], days=5, end_date=last_date)
                if not df.empty:
                    prices[h['symbol']] = df['close'].iloc[-1]
            except Exception:
                continue

        # 如果策略没有to_dict方法，手动构建结果
        if hasattr(strategy, 'to_dict'):
            result = strategy.to_dict(prices)
        else:
            # 手动计算收益
            total_cost = sum(h.get('cost', 0) for h in strategy.holdings)
            total_value = sum(prices.get(h['symbol'], h.get('buy_price', 0)) * h.get('quantity', 0) for h in strategy.holdings)
            total_value += strategy.current_capital
            total_return = (total_value - strategy.initial_capital) / strategy.initial_capital if strategy.initial_capital > 0 else 0

            result = {
                'name': strategy.name,
                'category': getattr(strategy, 'category', 'unknown'),
                'initial_capital': strategy.initial_capital,
                'current_capital': strategy.current_capital,
                'total_value': total_value,
                'total_return': total_return,
                'holdings': strategy.holdings,
                'trades': strategy.trades,
                'equity_curve': strategy.equity_curve,
                'realized_pnl': strategy.realized_pnl,
                'win_rate': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }

        result['backtest_start'] = trading_dates[0]
        result['backtest_end'] = trading_dates[-1]
        result['backtest_days'] = len(trading_dates)
        print(f"完成: {strategy.name} 总收益={result.get('total_return', 0)*100:.2f}%")
        return result

    # 并行运行策略
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_strategy, s): s for s in strategies}
        for future in as_completed(futures):
            strategy = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"策略 {strategy.name} 回测异常: {e}")
                import traceback
                traceback.print_exc()

    # 按总收益排序
    results.sort(key=lambda x: x.get('total_return', 0), reverse=True)

    # 生成输出
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_type': 'historical',
        'backtest_start': trading_dates[0],
        'backtest_end': trading_dates[-1],
        'backtest_days': len(trading_dates),
        'strategy_count': len(results),
        'strategies': results
    }

    # 保存结果到单独文件（不覆盖原数据）
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    temp_file = os.path.join(output_dir, 'new_strategy_results.json')

    # 自定义JSON序列化，处理numpy类型、datetime类型和equity_curve的dict格式
    def json_serializer(obj):
        """处理无法被json.dump的类型的序列化"""
        import numpy as np
        from datetime import datetime, date

        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            if 'date' in obj and 'value' in obj:
                return {'date': str(obj['date']), 'value': float(obj['value'])}
            return obj
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=json_serializer)

    # 【新增】自动合并到主数据文件
    main_file = os.path.join(output_dir, 'strategy_data.json')
    if os.path.exists(main_file):
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
        except:
            main_data = {'strategies': []}
    else:
        main_data = {'strategies': []}

    old_names = {s['name'] for s in main_data.get('strategies', [])}
    added_count = 0
    
    for s in results:
        if s is None:
            continue
        trades = len(s.get('trades', []))
        if trades > 0:  # 只合并有交易的策略
            if s['name'] in old_names:
                # 替换旧策略
                for i, old_s in enumerate(main_data['strategies']):
                    if old_s['name'] == s['name']:
                        main_data['strategies'][i] = s
                        added_count += 1
                        print(f"🔄 更新: {s['name']}")
                        break
            else:
                # 添加新策略
                main_data['strategies'].append(s)
                added_count += 1
                print(f"✅ 新增: {s['name']}")

    if added_count > 0:
        main_data['strategy_count'] = len(main_data['strategies'])
        main_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2, default=json_serializer)
        print(f"\n📊 已自动合并 {added_count} 个策略到 strategy_data.json")
    else:
        print("\n📊 没有需要合并的新策略")

    print("\n" + "=" * 60)
    print("历史回测排名")
    print("=" * 60)
    for i, r in enumerate(results, 1):
        name = r.get('name', 'Unknown')
        ret = r.get('total_return', 0) * 100
        value = r.get('total_value', 0)
        sharpe = r.get('sharpe_ratio', 0)
        dd = r.get('max_drawdown', 0) * 100
        win_rate = r.get('win_rate', 0) * 100
        print(f"{i:2}. {name:<20} 收益:{ret:>+7.2f}%  夏普:{sharpe:>5.2f}  回撤:{dd:>5.1f}%  胜率:{win_rate:>5.1f}%  权益:¥{value:,.0f}")

    print(f"\n结果已保存到: {temp_file}")
    print(f"📊 已自动合并到: {main_file}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='历史回测引擎')
    parser.add_argument('--days', type=int, default=60, help='回测天数（默认60）')
    parser.add_argument('--strategies', type=str, default=None, help='指定策略名（逗号分隔），默认全部')
    parser.add_argument('--workers', type=int, default=2, help='并行线程数（默认2，避免频率限制）')
    parser.add_argument('--source', type=str, default='tushare', choices=['tushare', 'akshare'], help='数据源（默认tushare）')
    args = parser.parse_args()

    # 设置数据源
    DATA_SOURCE = args.source

    strategy_names = None
    if args.strategies:
        strategy_names = [s.strip() for s in args.strategies.split(',')]

    run_historical_backtest(strategy_names=strategy_names, days=args.days, max_workers=args.workers)
