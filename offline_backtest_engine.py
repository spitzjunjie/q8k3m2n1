# -*- coding: utf-8 -*-
"""
离线回测引擎
使用本地缓存数据，不依赖网络
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

try:
    from multi_data_source_helper import MultiDataSourceHelper
    from local_data_manager import LocalDataManager
    HAS_ADVANCED = True
except Exception:
    HAS_ADVANCED = False


class OfflineBacktestEngine:
    """离线回测引擎"""
    
    def __init__(self, days=30):
        self.days = days
        self.initial_capital = 30000
        
        # 优先使用本地数据
        if HAS_ADVANCED:
            self.local_manager = LocalDataManager()
            self.multi_source = MultiDataSourceHelper()
        else:
            self.local_manager = None
            self.multi_source = None
    
    def backtest(self, strategy, helper=None) -> Dict:
        """执行回测"""
        
        # 生成日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=self.days)).strftime('%Y%m%d')
        
        # 初始化
        cash = self.initial_capital
        holdings = {}
        trades = []
        equity_curve = []
        
        # 获取交易日列表
        trading_days = self._get_trading_days(start_date, end_date)
        
        for date in trading_days:
            # 1. 选股
            try:
                selected = strategy.select_stocks(helper or self.multi_source, date)
            except Exception:
                selected = []
            
            # 2. 获取价格
            prices = self._get_prices(selected, date)
            
            # 3. 买入
            for stock in selected[:5]:
                symbol = stock.get('symbol', '')
                if symbol in prices and symbol not in holdings:
                    price = prices[symbol]
                    if cash >= price * 100:
                        shares = min(100, int(cash / price / 100) * 100)
                        holdings[symbol] = {'shares': shares, 'cost': shares * price}
                        cash -= shares * price
                        trades.append({
                            'date': date, 'symbol': symbol,
                            'action': 'buy', 'price': price,
                            'shares': shares
                        })
            
            # 4. 计算权益
            total_value = cash
            for symbol, pos in holdings.items():
                price = prices.get(symbol, pos['cost'] / pos['shares'])
                total_value += pos['shares'] * price
            
            equity_curve.append(total_value)
        
        # 计算指标
        return self._calculate_metrics(equity_curve, trades, holdings)
    
    def _get_trading_days(self, start: str, end: str) -> List[str]:
        """获取交易日"""
        # 优先从本地获取
        if self.local_manager:
            df = self.local_manager.get_index_hist("000001", start, end)
            if df is not None and len(df) > 0:
                return df['date'].tolist()
        
        # 备用：从多数据源获取
        if self.multi_source:
            days = self.multi_source.get_trading_days(start, end)
            if days:
                return days
        
        # 最终备用：生成工作日
        days = []
        current = datetime.strptime(end, '%Y%m%d')
        start_dt = datetime.strptime(start, '%Y%m%d')
        while current >= start_dt:
            if current.weekday() < 5:
                days.append(current.strftime('%Y%m%d'))
            current -= timedelta(days=1)
        return days[:self.days]
    
    def _get_prices(self, selected: List, date: str) -> Dict:
        """获取价格"""
        prices = {}
        
        for stock in selected[:10]:
            symbol = stock.get('symbol', '')
            if not symbol:
                continue
            
            # 优先从本地获取
            if self.local_manager:
                df = self.local_manager.get_stock_hist(symbol, date, date)
                if df is not None and len(df) > 0:
                    prices[symbol] = float(df.iloc[0]['close'])
                    continue
            
            # 备用：从多数据源获取
            if self.multi_source:
                try:
                    price = self.multi_source.get_realtime_price(symbol)
                    if price:
                        prices[symbol] = price
                except Exception:
                    pass
        
        return prices
    
    def _calculate_metrics(self, equity_curve: List, trades: List, holdings: Dict) -> Dict:
        """计算绩效指标"""
        
        if not equity_curve or len(equity_curve) < 2:
            return {
                'total_return': 0, 'sharpe_ratio': 0,
                'max_drawdown': 0, 'win_rate': 0,
                'equity_curve': [self.initial_capital],
                'trades': [], 'holdings': {}
            }
        
        initial = equity_curve[0]
        final = equity_curve[-1]
        
        # 收益率
        total_return = (final - initial) / initial
        
        # 最大回撤
        peak = initial
        max_drawdown = 0
        for v in equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 夏普比率
        returns = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] 
                    for i in range(1, len(equity_curve))]
        if returns and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        # 胜率
        sell_trades = [t for t in trades if t['action'] == 'sell']
        win_rate = len([t for t in sell_trades if t.get('profit', 0) > 0]) / max(len(sell_trades), 1)
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'equity_curve': equity_curve,
            'trades': trades,
            'holdings': holdings,
            'trade_count': len(trades)
        }


def run_offline_backtest(strategy, helper=None, days=30) -> Dict:
    """运行离线回测"""
    engine = OfflineBacktestEngine(days=days)
    result = engine.backtest(strategy, helper)
    result['name'] = strategy.name
    result['category'] = strategy.category
    return result
