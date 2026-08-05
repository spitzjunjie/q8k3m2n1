# -*- coding: utf-8 -*-
"""
快速回测3个策略 - 使用缓存数据
"""
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak

# 策略列表
TARGET_STRATEGIES = ['量价齐升', 'ETF二八轮动', '财务基本面过滤小市值']

# 导入必要模块
from strategies.new_strategies import get_new_strategy
from strategies.base import BaseStrategy
from trading.simulator import TradingSimulator
from timing.timing import TimingEngine
from data.akshare_helper import AKShareHelper

# 模拟helper使用缓存
class CachedAKShareHelper(AKShareHelper):
    """使用缓存的AKShareHelper，避免网络请求"""
    
    def __init__(self, cache_dir="data/cache"):
        super().__init__(cache_dir)
        self._cache_data = {}
        self._load_all_cache()
    
    def _load_all_cache(self):
        """加载所有缓存数据"""
        cache_dir = self.cache_dir
        if not os.path.exists(cache_dir):
            return
        
        for f in os.listdir(cache_dir):
            if f.startswith('kline_') and f.endswith('_now.json'):
                filepath = os.path.join(cache_dir, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        # 解析缓存key
                        parts = f.replace('kline_', '').replace('_now.json', '').split('_')
                        if len(parts) >= 2:
                            symbol = parts[0]
                            self._cache_data[symbol] = data
                except:
                    pass
    
    def get_history_kline(self, symbol, period="daily", days=60, end_date=None):
        """从缓存获取K线数据"""
        if symbol in self._cache_data:
            df = pd.DataFrame(self._cache_data[symbol])
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'date', 'open': 'open', 'close': 'close', 
                                        'high': 'high', 'low': 'low', 'volume': 'volume'})
                return df.tail(days)
        return pd.DataFrame()
    
    def get_stock_list(self):
        """获取股票列表（使用缓存）"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return cache
        return []

def get_trading_dates(helper, n=32, end_date=None):
    """获取过去n个交易日"""
    if end_date:
        end_norm = end_date.replace('-', '') if '-' in end_date else end_date
    else:
        end_norm = datetime.now().strftime("%Y%m%d")
    
    # 从缓存获取交易日
    try:
        df = ak.stock_zh_index_daily(symbol='sh000300')
        if df is not None and not df.empty:
            df['date'] = df['date'].astype(str)
            df = df[df['date'].str.replace('-', '') <= end_norm]
            dates = df['date'].tail(n).tolist()
            return [d.replace('-', '') for d in dates]
    except:
        pass
    
    # 备用：使用日期推算
    dates = []
    current = datetime.now()
    while len(dates) < n:
        if current.weekday() < 5:  # 周一到周五
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates[::-1]


def run_strategy(strategy, helper, timing, dates):
    """在历史日期上运行策略"""
    simulator = TradingSimulator(strategy, timing)
    
    print(f"\n开始回测: {strategy.name}")
    
    for date in dates:
        try:
            # 选股
            selected = strategy.select_stocks(helper, date)
            
            # 获取价格
            prices = {}
            for stock in selected[:30]:
                df = helper.get_history_kline(stock['symbol'], days=5, end_date=date)
                if not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price):
                        prices[stock['symbol']] = float(close_price)
            
            # 检查持仓并卖出
            for holding in list(strategy.holdings):
                symbol = holding['symbol']
                df = helper.get_history_kline(symbol, days=5, end_date=date)
                if not df.empty and 'close' in df.columns:
                    close_price = df['close'].iloc[-1]
                    if pd.notna(close_price):
                        prices[symbol] = float(close_price)
                        should_sell, reason = simulator.check_and_sell(symbol, prices[symbol], helper=helper, date=date)
                        if should_sell:
                            simulator.execute_sell(symbol, prices[symbol], reason, sell_date=date)
            
            # 买入新股票
            for stock in selected:
                if len(strategy.holdings) >= simulator.max_holdings:
                    break
                symbol = stock['symbol']
                if symbol in prices:
                    result, msg = simulator.execute_buy(
                        symbol, stock.get('name', symbol), prices[symbol],
                        stock.get('reason', ''), helper=helper, date=date
                    )
                    if result:
                        print(f"  [{date}] 买入 {stock.get('name', symbol)}")
            
            # 更新持仓
            simulator.update_positions(prices)
            
            # 记录权益
            total_value = strategy.get_total_value(prices)
            strategy.equity_curve.append({'date': date, 'value': total_value})
            
        except Exception as e:
            print(f"  [{date}] 错误: {e}")
            continue
    
    # 计算最终收益
    result = strategy.to_dict(prices if 'prices' in dir() else {})
    return result


def main():
    print("=" * 60)
    print("快速回测3个策略（使用缓存数据）")
    print("=" * 60)
    
    # 初始化
    helper = CachedAKShareHelper(cache_dir="data/cache")
    timing = TimingEngine()
    
    print(f"已加载 {len(helper._cache_data)} 个股票的缓存数据")
    
    # 获取交易日
    import akshare as ak
    end_norm = datetime.now().strftime("%Y%m%d")
    dates = []
    try:
        df = ak.stock_zh_index_daily(symbol='sh000300')
        if df is not None and not df.empty:
            df['date'] = df['date'].astype(str)
            df = df[df['date'].str.replace('-', '') <= end_norm]
            dates = df['date'].tail(32).tolist()
            dates = [d.replace('-', '') for d in dates]
    except:
        pass
    
    if not dates:
        print("无法获取交易日历")
        return
    
    print(f"回测区间: {dates[0]} ~ {dates[-1]} ({len(dates)}个交易日)")
    
    # 运行策略
    results = []
    for name in TARGET_STRATEGIES:
        strategy = get_new_strategy(name)
        if strategy:
            result = run_strategy(strategy, helper, timing, dates)
            results.append(result)
            print(f"完成: {name} 总收益={result.get('total_return', 0)*100:.2f}% 交易次数={len(result.get('trades', []))}")
        else:
            print(f"策略不存在: {name}")
    
    # 保存结果
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_type': 'historical',
        'backtest_start': dates[0],
        'backtest_end': dates[-1],
        'backtest_days': len(dates),
        'strategy_count': len(results),
        'strategies': results
    }
    
    # 合并到主数据
    main_file = 'output/strategy_data.json'
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
    else:
        main_data = {'strategies': []}
    
    old_names = {s['name'] for s in main_data.get('strategies', [])}
    added_count = 0
    
    for s in results:
        trades = len(s.get('trades', []))
        if trades > 0:  # 只合并有交易的策略
            if s['name'] in old_names:
                for i, old_s in enumerate(main_data['strategies']):
                    if old_s['name'] == s['name']:
                        main_data['strategies'][i] = s
                        added_count += 1
                        print(f"🔄 更新: {s['name']}")
                        break
            else:
                main_data['strategies'].append(s)
                added_count += 1
                print(f"✅ 新增: {s['name']}")
    
    if added_count > 0:
        main_data['strategy_count'] = len(main_data['strategies'])
        main_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n📊 已合并 {added_count} 个策略到 strategy_data.json")
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    for r in results:
        print(f"{r['name']}: 收益={r.get('total_return', 0)*100:.2f}% 交易={len(r.get('trades', []))}")


if __name__ == "__main__":
    main()
