# -*- coding: utf-8 -*-
"""
快速回测脚本 - 测试新上线的9个策略
只回测今天，快速验证策略有效性
"""

import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator

# 9个新上线策略
from strategies.new_strategies import (
    SouthboundMoneyStrategy,    # 南向资金
    ContinuousVolumeStrategy,   # 量价齐升
    ResearchReportStrategy,     # 研报推荐
    MoneyFlowEventStrategy,     # 资金流事件
    ProfitExplosionStrategy,    # 业绩暴增
    NorthboundMoneyStrategy,    # 北向资金
    ETFRotationStrategy,        # ETF二八轮动
    ShortTermMomentumStrategy,  # 短线动量
    DragonTigerListStrategy,    # 龙虎榜
)

# 另外3个
from strategies.new_strategies import (
    AntiOverconfidenceStrategy,     # 反过度自信
    SuperShortReboundStrategy,      # 超跌反弹
    FundamentalSmallCapStrategy,    # 财务基本面过滤小市值
)

# 策略映射
NEW_STRATEGY_MAPPING = {
    '南向资金': SouthboundMoneyStrategy,
    '量价齐升': ContinuousVolumeStrategy,
    '研报推荐': ResearchReportStrategy,
    '资金流事件': MoneyFlowEventStrategy,
    '业绩暴增': ProfitExplosionStrategy,
    '北向资金': NorthboundMoneyStrategy,
    'ETF二八轮动': ETFRotationStrategy,
    '短线动量': ShortTermMomentumStrategy,
    '龙虎榜': DragonTigerListStrategy,
    '反过度自信': AntiOverconfidenceStrategy,
    '超跌反弹': SuperShortReboundStrategy,
    '财务基本面过滤小市值': FundamentalSmallCapStrategy,
}


def run_single_strategy(strategy_name, helper):
    """运行单个策略"""
    strategy_class = NEW_STRATEGY_MAPPING.get(strategy_name)
    if not strategy_class:
        return None
    
    strategy = strategy_class()
    timing = TimingEngine()
    simulator = TradingSimulator(strategy, timing)
    
    print(f"\n测试策略: {strategy_name}")
    
    try:
        # 选股
        selected = strategy.select_stocks(helper, date=None)
        print(f"  选股结果: {len(selected)} 只")
        
        for stock in selected[:3]:
            print(f"    - {stock.get('name', stock['symbol'])} ({stock['symbol']}): {stock.get('reason', '')}")
        
        # 获取价格并尝试买入
        prices = {}
        for stock in selected[:10]:
            try:
                df = helper.get_history_kline(stock['symbol'], days=5)
                if df is not None and not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if close_price and close_price > 0:
                        prices[stock['symbol']] = float(close_price)
            except Exception as e:
                continue
        
        print(f"  获取价格: {len(prices)} 只")
        
        # 执行买入
        buy_count = 0
        for stock in selected:
            if len(strategy.holdings) >= simulator.max_holdings:
                break
            symbol = stock['symbol']
            if symbol in prices:
                result, msg = simulator.execute_buy(
                    symbol, stock.get('name', symbol), prices[symbol],
                    stock.get('reason', ''), helper=helper, date=None
                )
                if result:
                    buy_count += 1
                    print(f"  买入: {stock.get('name', symbol)} @ {prices[symbol]:.2f}")
        
        print(f"  买入: {buy_count} 只")
        print(f"  持仓: {len(strategy.holdings)} 只")
        print(f"  当前资金: ¥{strategy.current_capital:.2f}")
        
        # 返回结果
        return strategy.to_dict(prices)
        
    except Exception as e:
        print(f"  策略运行失败: {e}")
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
    print("=" * 60)
    print("新策略快速回测")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 初始化数据源
    helper = AKShareHelper(cache_dir="data/cache")
    timing = TimingEngine()
    
    # 获取所有新策略名称
    strategy_names = list(NEW_STRATEGY_MAPPING.keys())
    print(f"\n共 {len(strategy_names)} 个新策略待测试\n")
    
    results = []
    
    # 串行执行（避免并发过高）
    for name in strategy_names:
        result = run_single_strategy(name, helper)
        if result:
            results.append(result)
        time.sleep(1)  # 避免请求过快
    
    # 按收益率排序
    results.sort(key=lambda x: x.get('total_return', 0), reverse=True)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("回测结果排名")
    print("=" * 60)
    
    for i, r in enumerate(results, 1):
        name = r.get('name', 'Unknown')
        ret = r.get('total_return', 0) * 100
        value = r.get('total_value', 0)
        holdings = len(r.get('holdings', []))
        trades = len(r.get('trades', []))
        print(f"{i:2}. {name:<20} 收益:{ret:>+7.2f}%  持仓:{holdings:>2}只  交易:{trades:>2}笔  权益:¥{value:,.0f}")
    
    # 保存结果
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # 合并到主数据文件
    main_file = os.path.join(output_dir, 'strategy_data.json')
    
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
        existing_strategies = {s['name']: s for s in main_data.get('strategies', [])}
    else:
        main_data = {'strategies': []}
        existing_strategies = {}
    
    # 只更新有交易的策略
    merged_count = 0
    for result in results:
        name = result['name']
        # 只要有持仓或交易就更新
        if result.get('holdings') or result.get('trades') or result.get('total_return', 0) != 0:
            existing_strategies[name] = result
            merged_count += 1
    
    main_data['strategies'] = list(existing_strategies.values())
    main_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    main_data['strategy_count'] = len(main_data['strategies'])
    
    with open(main_file, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 已合并 {merged_count} 个策略到 strategy_data.json")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    main()
