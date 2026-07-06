# -*- coding: utf-8 -*-
"""
策略基类
所有策略的父类
"""

from abc import ABC, abstractmethod
from datetime import datetime
import pandas as pd


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name, category, initial_capital=30000):
        self.name = name
        self.category = category
        self.initial_capital = initial_capital  # 初始资金3万
        self.current_capital = initial_capital  # 当前资金
        self.holdings = []  # 当前持仓
        self.trades = []  # 历史交易记录
        self.equity_curve = []  # 权益曲线
        
    @abstractmethod
    def select_stocks(self, helper, date=None):
        """
        选股：返回选中的股票列表
        返回格式: [{'symbol': '000001', 'name': '平安银行', 'reason': 'ROE排名第3'}, ...]
        """
        pass
    
    def get_params(self):
        """获取策略参数"""
        return {}
    
    def get_description(self):
        """获取策略描述"""
        return self.name
    
    def add_holding(self, symbol, name, price, quantity, reason, timing_reason):
        """添加持仓"""
        cost = price * quantity
        self.current_capital -= cost
        
        holding = {
            'symbol': symbol,
            'name': name,
            'buy_price': price,
            'quantity': quantity,
            'buy_date': datetime.now().strftime("%Y-%m-%d"),
            'cost': cost,
            'stock_reason': reason,  # 选股逻辑
            'timing_reason': timing_reason,  # 择时逻辑
            'hold_days': 0
        }
        self.holdings.append(holding)
        return holding
    
    def remove_holding(self, symbol, sell_price, sell_reason):
        """卖出持仓"""
        for i, h in enumerate(self.holdings):
            if h['symbol'] == symbol:
                holding = self.holdings.pop(i)
                revenue = sell_price * holding['quantity']
                profit = revenue - holding['cost']
                profit_pct = profit / holding['cost'] * 100
                
                self.current_capital += revenue
                
                trade = {
                    'symbol': symbol,
                    'name': holding['name'],
                    'buy_date': holding['buy_date'],
                    'buy_price': holding['buy_price'],
                    'sell_date': datetime.now().strftime("%Y-%m-%d"),
                    'sell_price': sell_price,
                    'quantity': holding['quantity'],
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'hold_days': holding['hold_days'],
                    'stock_reason': holding['stock_reason'],
                    'timing_reason': holding['timing_reason'],
                    'sell_reason': sell_reason
                }
                self.trades.append(trade)
                return trade
        return None
    
    def update_holdings(self):
        """更新持仓天数"""
        for h in self.holdings:
            h['hold_days'] += 1
    
    def get_total_value(self, prices):
        """计算总权益"""
        holdings_value = sum(
            prices.get(h['symbol'], h['buy_price']) * h['quantity']
            for h in self.holdings
        )
        return self.current_capital + holdings_value
    
    def get_total_return(self):
        """计算总收益率"""
        return (self.current_capital + sum(
            h['buy_price'] * h['quantity'] for h in self.holdings
        ) - self.initial_capital) / self.initial_capital
    
    def get_win_rate(self):
        """计算胜率"""
        if not self.trades:
            return 0
        wins = sum(1 for t in self.trades if t['profit'] > 0)
        return wins / len(self.trades)
    
    def get_max_drawdown(self):
        """计算最大回撤"""
        if not self.equity_curve:
            return 0
        peak = self.initial_capital
        max_dd = 0
        for value in self.equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd
    
    def get_sharpe_ratio(self):
        """计算夏普比率（简化版）"""
        if len(self.equity_curve) < 2:
            return 0
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        if returns.std() == 0:
            return 0
        return (returns.mean() / returns.std()) * (252 ** 0.5)
    
    def to_dict(self, prices=None):
        """转换为字典格式（用于JSON输出）"""
        total_value = self.get_total_value(prices or {})
        
        return {
            'name': self.name,
            'category': self.category,
            'description': self.get_description(),
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_value': total_value,
            'total_return': self.get_total_return(),
            'monthly_return': self.get_total_return(),  # 简化
            'sharpe_ratio': self.get_sharpe_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'win_rate': self.get_win_rate(),
            'holdings': self.holdings,
            'trades': self.trades[-10:],  # 最近10笔交易
            'equity_curve': self.equity_curve[-30:]  # 最近30天曲线
        }


class FactorStrategy(BaseStrategy):
    """因子选股策略基类"""
    
    def __init__(self, name, category, factor_name, top_n=10, **kwargs):
        super().__init__(name, category, **kwargs)
        self.factor_name = factor_name
        self.top_n = top_n
    
    @abstractmethod
    def calculate_factor(self, helper, date=None):
        """
        计算因子值
        返回: DataFrame with columns ['symbol', 'name', 'factor_value']
        """
        pass
    
    def select_stocks(self, helper, date=None):
        """按因子值排序选股"""
        df = self.calculate_factor(helper, date)
        if df.empty:
            return []
        
        # 按因子值排序
        df = df.sort_values('factor_value', ascending=False)
        
        # 取前N只
        selected = df.head(self.top_n)
        
        return [
            {
                'symbol': row['symbol'],
                'name': row.get('name', row['symbol']),
                'reason': f"{self.factor_name}:{row['factor_value']:.4f}"
            }
            for _, row in selected.iterrows()
        ]


class EventStrategy(BaseStrategy):
    """事件驱动策略基类"""
    
    def __init__(self, name, category, **kwargs):
        super().__init__(name, category, **kwargs)
    
    @abstractmethod
    def detect_events(self, helper, date=None):
        """
        检测事件
        返回: [{'symbol': '000001', 'name': 'xxx', 'reason': '涨停'}, ...]
        """
        pass
    
    def select_stocks(self, helper, date=None):
        """基于事件选股"""
        events = self.detect_events(helper, date)
        return events[:10]  # 最多10只
