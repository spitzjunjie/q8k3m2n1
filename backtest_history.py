# -*- coding: utf-8 -*-
"""
历史回测引擎
在过去N个交易日逐日运行策略，生成历史权益曲线和交易记录
用于验证策略在历史数据上的表现
"""

import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator
from backtest import get_all_strategies


def run_strategy_on_date(strategy, helper, timing, date):
    """在指定历史日期运行单个策略
    date: YYYY-MM-DD格式字符串
    """
    try:
        simulator = TradingSimulator(strategy, timing)

        # 1. 选股（传入历史日期）
        selected = strategy.select_stocks(helper, date)

        # 2. 获取选股当日收盘价
        prices = {}
        for stock in selected[:30]:  # 扩大到前30只
            try:
                df = helper.get_history_kline(stock['symbol'], days=5, end_date=date)
                if not df.empty:
                    prices[stock['symbol']] = df['close'].iloc[-1]
            except Exception:
                continue

        # 3. 检查现有持仓并卖出
        for holding in strategy.holdings:
            symbol = holding['symbol']
            try:
                df = helper.get_history_kline(symbol, days=5, end_date=date)
                if not df.empty:
                    prices[symbol] = df['close'].iloc[-1]
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


def run_historical_backtest(strategy_names=None, days=60, max_workers=5):
    """历史回测主函数

    Args:
        strategy_names: 指定策略名列表，None=全部
        days: 回测交易日天数
        max_workers: 并行线程数

    Returns:
        dict: 回测结果，包含每个策略的最终状态
    """
    print("=" * 60)
    print("历史回测引擎")
    print(f"回测天数: {days}个交易日")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    helper = AKShareHelper(cache_dir="data/cache")
    timing = TimingEngine()

    # 获取交易日列表
    trading_dates = helper.get_trading_dates(n=days)
    if not trading_dates:
        print("获取交易日失败，无法回测")
        return None

    print(f"回测区间: {trading_dates[0]} ~ {trading_dates[-1]}")

    # 获取策略
    all_strategies = get_all_strategies()
    if strategy_names:
        strategies = [s for s in all_strategies if s.name in strategy_names]
    else:
        strategies = all_strategies

    print(f"回测策略数: {len(strategies)}\n")

    # 逐日运行（每个策略独立，但日期是共享的）
    # 对每个策略，从头开始逐日运行
    results = []

    def run_single_strategy(strategy):
        """运行单个策略的完整历史回测"""
        # 重置策略状态（保留initial_capital）
        strategy.current_capital = strategy.initial_capital
        strategy.holdings = []
        strategy.trades = []
        strategy.equity_curve = []
        strategy.realized_pnl = 0.0
        strategy.realized_pnl_pct = 0.0

        print(f"\n开始回测: {strategy.name}")
        for date in trading_dates:
            run_strategy_on_date(strategy, helper, timing, date)

        # 返回策略最终状态
        # 获取最新价格计算浮动收益
        last_date = trading_dates[-1]
        prices = {}
        for h in strategy.holdings:
            try:
                df = helper.get_history_kline(h['symbol'], days=5, end_date=last_date)
                if not df.empty:
                    prices[h['symbol']] = df['close'].iloc[-1]
            except Exception:
                continue

        result = strategy.to_dict(prices)
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

    # 保存结果
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'backtest_history.json')

    # 自定义JSON序列化，处理numpy类型、datetime类型和equity_curve的dict格式
    def json_serializer(obj):
        """处理无法被json.dump的类型的序列化"""
        import numpy as np
        from datetime import datetime, date

        # 【修复Minor问题2】添加datetime类型处理
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
            # equity_curve 中的 {'date': str, 'value': float} 格式
            if 'date' in obj and 'value' in obj:
                return {'date': str(obj['date']), 'value': float(obj['value'])}
            return obj
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=json_serializer)

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

    print(f"\n结果已保存到: {output_file}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='历史回测引擎')
    parser.add_argument('--days', type=int, default=60, help='回测天数（默认60）')
    parser.add_argument('--strategies', type=str, default=None, help='指定策略名（逗号分隔），默认全部')
    parser.add_argument('--workers', type=int, default=5, help='并行线程数')
    args = parser.parse_args()

    strategy_names = None
    if args.strategies:
        strategy_names = [s.strip() for s in args.strategies.split(',')]

    run_historical_backtest(strategy_names=strategy_names, days=args.days, max_workers=args.workers)
