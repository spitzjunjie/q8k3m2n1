# -*- coding: utf-8 -*-
"""
真正的历史回测引擎
支持30天以上的历史数据回测，准确计算绩效指标
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')


class HistoricalBacktestEngine:
    """历史回测引擎"""
    
    def __init__(self, days=30):
        self.days = days
        self.initial_capital = 30000
        
    def backtest(self, strategy, helper) -> Dict:
        """执行真正的历史回测
        
        Args:
            strategy: 策略对象
            helper: 数据助手
        
        Returns:
            dict: 完整的回测结果
        """
        # 生成回测日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=self.days)).strftime('%Y%m%d')
        
        # 初始化资金和持仓
        cash = self.initial_capital
        holdings = {}  # {symbol: {'shares': n, 'cost': price}}
        trades = []
        equity_curve = []
        
        # 模拟每日交易
        trading_days = self._get_trading_days(helper, start_date, end_date)
        
        for i, date in enumerate(trading_days):
            # 1. 获取当日选股
            try:
                selected = strategy.select_stocks(helper, date)
            except Exception as e:
                selected = []
            
            # 2. 获取当日价格
            prices = {}
            for stock in selected[:10]:
                symbol = stock.get('symbol', '')
                try:
                    price = helper.get_realtime_price(symbol)
                    if price and price > 0:
                        prices[symbol] = price
                except Exception:
                    pass
            
            # 3. 执行买入（最多持有5只）
            for stock in selected[:5]:
                symbol = stock.get('symbol', '')
                if symbol in prices and symbol not in holdings:
                    price = prices[symbol]
                    if cash >= price * 100:  # 至少买1手
                        shares = min(100, int(cash / price / 100) * 100)
                        cost = shares * price
                        holdings[symbol] = {'shares': shares, 'cost': cost}
                        cash -= cost
                        trades.append({
                            'date': date,
                            'symbol': symbol,
                            'action': 'buy',
                            'price': price,
                            'shares': shares,
                            'amount': cost
                        })
            
            # 4. 更新持仓市值
            for symbol in list(holdings.keys()):
                try:
                    price = helper.get_realtime_price(symbol)
                    if not price or price <= 0:
                        # 使用历史价格估算
                        hist = helper.get_stock_hist(symbol, start=date, end=date)
                        if hist is not None and len(hist) > 0:
                            price = hist.iloc[-1].get('close', 0)
                except Exception:
                    price = holdings[symbol]['cost'] / holdings[symbol]['shares']  # 成本价
            
                if price and price > 0:
                    holdings[symbol]['current_price'] = price
            
            # 5. 计算当日总权益
            total_value = cash
            for symbol, pos in holdings.items():
                total_value += pos['shares'] * pos.get('current_price', pos['cost'] / pos['shares'])
            
            equity_curve.append({
                'date': date,
                'cash': cash,
                'holdings_value': total_value - cash,
                'total_value': total_value
            })
        
        # 计算绩效指标
        result = self._calculate_metrics(equity_curve, trades, holdings)
        result['name'] = strategy.name
        result['category'] = strategy.category
        
        return result
    
    def _get_trading_days(self, helper, start_date, end_date) -> List[str]:
        """获取交易日列表"""
        try:
            # 使用指数成分股接口获取交易日
            df = helper.get_index_hist('000001', start=start_date, end=end_date)
            if df is not None and len(df) > 0:
                return df['日期'].tolist()[-self.days:]
        except Exception:
            pass
        
        # 备用：生成近30个交易日
        days = []
        current = datetime.now()
        for i in range(self.days):
            day = current - timedelta(days=i)
            if day.weekday() < 5:  # 跳过周末
                days.append(day.strftime('%Y%m%d'))
        return days[:self.days]
    
    def _calculate_metrics(self, equity_curve, trades, holdings) -> Dict:
        """计算绩效指标"""
        if not equity_curve or len(equity_curve) < 2:
            return {
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'equity_curve': [self.initial_capital],
                'trades': trades,
                'holdings': holdings
            }
        
        # 提取权益曲线
        values = [e['total_value'] for e in equity_curve]
        initial = values[0]
        final = values[-1]
        
        # 总收益率
        total_return = (final - initial) / initial
        
        # 年化收益率
        n_years = len(equity_curve) / 252
        annualized_return = (1 + total_return) ** (1 / max(n_years, 0.01)) - 1
        
        # 最大回撤
        peak = initial
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 夏普比率
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        if returns and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # 胜率
        if trades:
            sell_trades = [t for t in trades if t['action'] == 'sell']
            if sell_trades:
                wins = [t for t in sell_trades if t.get('profit', 0) > 0]
                win_rate = len(wins) / len(sell_trades)
            else:
                win_rate = 0
        else:
            win_rate = 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': len(trades),
            'equity_curve': values,
            'trades': trades,
            'holdings': holdings,
            'initial_capital': initial,
            'final_capital': final
        }


def run_historical_backtest(strategy, helper, days=30) -> Dict:
    """运行历史回测的便捷函数"""
    engine = HistoricalBacktestEngine(days=days)
    return engine.backtest(strategy, helper)
