# -*- coding: utf-8 -*-
"""
回测12个未上线策略
遵守API限制：延迟≥1.5秒，并发≤2
"""
import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 导入12个目标策略
from strategies.southbound_money_strategy import SouthboundMoneyStrategy
from strategies.continuous_volume_strategy import ContinuousVolumeStrategy
from strategies.research_report_strategy import ResearchReportStrategy
from strategies.money_flow_event_strategy import MoneyFlowEventStrategy
from strategies.profit_explosion_strategy import ProfitExplosionStrategy
from strategies.northbound_money_strategy import NorthboundMoneyStrategy
from strategies.etf_rotation_strategy import ETFRotationStrategy
from strategies.short_term_momentum_strategy import ShortTermMomentumStrategy
from strategies.dragon_tiger_list_strategy import DragonTigerListStrategy
from strategies.anti_overconfidence_strategy import AntiOverconfidenceStrategy
from strategies.super_short_rebound_strategy import SuperShortReboundStrategy
from strategies.fundamental_small_cap_strategy import FundamentalSmallCapStrategy

from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator

# API限制
API_DELAY = 1.5  # 延迟≥1.5秒
MAX_WORKERS = 2  # 并发≤2

# 12个目标策略列表
TARGET_STRATEGIES = [
    '南向资金', '量价齐升', '研报推荐', '资金流事件', '业绩暴增',
    '北向资金', 'ETF二八轮动', '短线动量', '龙虎榜', '反过度自信',
    '超跌反弹', '财务基本面过滤小市值'
]


def get_strategy_instance(name):
    """获取策略实例"""
    strategy_map = {
        '南向资金': SouthboundMoneyStrategy(),
        '量价齐升': ContinuousVolumeStrategy(),
        '研报推荐': ResearchReportStrategy(),
        '资金流事件': MoneyFlowEventStrategy(),
        '业绩暴增': ProfitExplosionStrategy(),
        '北向资金': NorthboundMoneyStrategy(),
        'ETF二八轮动': ETFRotationStrategy(),
        '短线动量': ShortTermMomentumStrategy(),
        '龙虎榜': DragonTigerListStrategy(),
        '反过度自信': AntiOverconfidenceStrategy(),
        '超跌反弹': SuperShortReboundStrategy(),
        '财务基本面过滤小市值': FundamentalSmallCapStrategy(),
    }
    return strategy_map.get(name)


def run_strategy_backtest(strategy_name, helper, timing, dates):
    """回测单个策略"""
    print(f"\n{'='*50}")
    print(f"回测策略: {strategy_name}")
    print(f"{'='*50}")
    
    strategy = get_strategy_instance(strategy_name)
    if strategy is None:
        return {'name': strategy_name, 'error': '策略不存在', 'trades': [], 'total_return': 0}
    
    simulator = TradingSimulator(strategy, timing)
    
    # 按日期顺序回测
    for i, date in enumerate(dates):
        print(f"  [{i+1}/{len(dates)}] 回测日期: {date}")
        time.sleep(API_DELAY)  # API延迟
        
        try:
            # 1. 选股
            selected = strategy.select_stocks(helper, date)
            print(f"    选出 {len(selected)} 只股票")
            
            if not selected:
                continue
            
            # 2. 获取价格
            prices = {}
            for stock in selected[:30]:
                try:
                    df = helper.get_history_kline(stock['symbol'], days=5, end_date=date)
                    if df is not None and not df.empty and 'close' in df.columns:
                        close_price = df['close'].iloc[-1]
                        if close_price > 0:
                            prices[stock['symbol']] = float(close_price)
                            time.sleep(0.3)  # 获取K线数据的延迟
                except Exception as e:
                    continue
            
            # 3. 检查现有持仓
            for holding in list(strategy.holdings):
                symbol = holding['symbol']
                try:
                    df = helper.get_history_kline(symbol, days=5, end_date=date)
                    if df is not None and not df.empty and 'close' in df.columns:
                        current_price = df['close'].iloc[-1]
                        prices[symbol] = float(current_price)
                        
                        should_sell, reason = simulator.check_and_sell(
                            symbol, current_price, helper=helper, date=date)
                        if should_sell:
                            simulator.execute_sell(symbol, current_price, reason, sell_date=date)
                            print(f"    卖出 {holding['name']}: {reason}")
                except:
                    continue
            
            # 4. 买入新股票
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
                        print(f"    买入 {stock['name']}: {msg}")
            
            # 5. 更新持仓状态
            simulator.update_positions(prices)
            
            # 6. 记录权益曲线
            total_value = strategy.get_total_value(prices)
            strategy.equity_curve.append({'date': date, 'value': total_value})
            
        except Exception as e:
            print(f"    错误: {e}")
            continue
    
    # 转换为结果字典
    result = strategy.to_dict()
    
    # 计算最终收益率
    total_return = result.get('total_return', 0) or 0
    trades_count = len(result.get('trades', []))
    
    print(f"\n  结果:")
    print(f"    - 总收益率: {total_return*100:.2f}%")
    print(f"    - 交易次数: {trades_count}")
    print(f"    - 胜率: {result.get('win_rate', 0)*100:.1f}%")
    print(f"    - 夏普比率: {result.get('sharpe_ratio', 0):.2f}")
    print(f"    - 最大回撤: {result.get('max_drawdown', 0)*100:.2f}%")
    
    return result


def main():
    print("=" * 60)
    print("12个未上线策略回测")
    print(f"API延迟: {API_DELAY}秒, 并发数: {MAX_WORKERS}")
    print("=" * 60)
    
    # 初始化
    helper = AKShareHelper(cache_dir="data/cache")
    timing = TimingEngine()
    
    # 回测日期范围（近30个交易日）
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
    
    # 生成回测日期（每隔一个交易日）
    dates = []
    current = datetime.strptime(start_date, '%Y%m%d')
    end = datetime.strptime(end_date, '%Y%m%d')
    while current <= end:
        if current.weekday() < 5:  # 工作日
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    
    # 限制回测天数
    dates = dates[-30:]
    print(f"回测日期: {dates[0]} ~ {dates[-1]}, 共{len(dates)}个交易日")
    
    # 回测所有目标策略（并发≤2）
    results = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_strategy_backtest, name, helper, timing, dates): name
            for name in TARGET_STRATEGIES
        }
        
        for future in as_completed(futures):
            strategy_name = futures[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)
                print(f"\n✅ [{completed}/{len(TARGET_STRATEGIES)}] {strategy_name} 完成")
            except Exception as e:
                print(f"\n❌ [{completed}/{len(TARGET_STRATEGIES)}] {strategy_name} 失败: {e}")
                results.append({'name': strategy_name, 'error': str(e), 'trades': [], 'total_return': 0})
    
    # 筛选有交易的策略
    strategies_with_trades = []
    strategies_no_trades = []
    
    for r in results:
        trades_count = len(r.get('trades', []))
        total_return = r.get('total_return', 0) or 0
        
        if trades_count > 0 and total_return != 0:
            strategies_with_trades.append(r)
            print(f"✅ 有交易: {r['name']} - {trades_count}笔交易, {total_return*100:.2f}%收益")
        else:
            strategies_no_trades.append(r)
            print(f"⚠️ 无交易: {r['name']} - {trades_count}笔交易, {total_return*100:.2f}%收益")
    
    print(f"\n{'='*60}")
    print(f"回测完成统计")
    print(f"{'='*60}")
    print(f"有交易策略: {len(strategies_with_trades)} 个")
    print(f"无交易策略: {len(strategies_no_trades)} 个")
    
    # 合并到strategy_data.json（只合并有交易的策略）
    if strategies_with_trades:
        main_file = 'output/strategy_data.json'
        
        # 读取现有数据
        if os.path.exists(main_file):
            with open(main_file, 'r', encoding='utf-8') as f:
                main_data = json.load(f)
            existing_strategies = {s['name']: s for s in main_data.get('strategies', [])}
        else:
            main_data = {'strategies': []}
            existing_strategies = {}
        
        # 合并新策略
        for result in strategies_with_trades:
            existing_strategies[result['name']] = result
        
        # 按收益率排序
        main_data['strategies'] = list(existing_strategies.values())
        main_data['strategies'].sort(key=lambda x: x.get('total_return', 0), reverse=True)
        main_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        main_data['strategy_count'] = len(main_data['strategies'])
        
        # 保存
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✅ 已合并 {len(strategies_with_trades)} 个策略到 {main_file}")
    
    # 保存回测结果
    output_file = 'output/12_new_strategy_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategies_with_trades': strategies_with_trades,
            'strategies_no_trades': strategies_no_trades,
            'total_tested': len(TARGET_STRATEGIES),
            'with_trades': len(strategies_with_trades),
            'no_trades': len(strategies_no_trades)
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"回测结果已保存到: {output_file}")
    
    # 打印最终结果汇总
    print(f"\n{'='*60}")
    print("策略回测结果汇总")
    print(f"{'='*60}")
    print(f"{'策略名称':<20} {'收益率':>10} {'交易次数':>8} {'胜率':>8} {'夏普':>8} {'最大回撤':>10}")
    print("-" * 60)
    for r in results:
        name = r.get('name', 'Unknown')
        ret = (r.get('total_return', 0) or 0) * 100
        trades = len(r.get('trades', []))
        win_rate = (r.get('win_rate', 0) or 0) * 100
        sharpe = r.get('sharpe_ratio', 0) or 0
        max_dd = (r.get('max_drawdown', 0) or 0) * 100
        marker = "✅" if trades > 0 and ret != 0 else "❌"
        print(f"{marker}{name:<18} {ret:>+9.2f}% {trades:>8} {win_rate:>7.1f}% {sharpe:>8.2f} {max_dd:>9.2f}%")
    print("-" * 60)
    
    return results


if __name__ == '__main__':
    results = main()
