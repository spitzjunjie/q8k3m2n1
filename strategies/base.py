# -*- coding: utf-8 -*-
"""
策略基类
所有策略的父类
"""

from abc import ABC, abstractmethod
from datetime import datetime
import pandas as pd
from core.costs import DEFAULT_COSTS


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name, category, initial_capital=30000, costs=None):
        self.name = name
        self.category = category
        self.version = "1.0.0"  # 策略版本号（参数调优后+1）
        self.initial_capital = initial_capital  # 初始资金3万
        self.current_capital = initial_capital  # 当前资金
        self.holdings = []  # 当前持仓
        self.trades = []  # 历史交易记录（截断版，用于展示）
        self.all_trades = []  # 完整交易记录（不截断，用于统计检验）
        self.equity_curve = []  # 权益曲线
        self.realized_pnl = 0.0  # 累计已实现收益
        self.realized_pnl_pct = 0.0  # 已实现收益率
        self.costs = costs if costs is not None else DEFAULT_COSTS  # 交易成本模型
        self.total_fees = 0.0  # 累计手续费（用于归因分析）
        
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
    
    def add_holding(self, symbol, name, price, quantity, reason, timing_reason, buy_date=None):
        """添加持仓
        buy_date: 买入日期，None=今天（用于历史回测）
        → price 为参考价（如收盘价），实际成交价含滑点，总成本含手续费
        """
        # 含滑点的真实成交价
        fill = self.costs.fill_price_buy(price)
        gross = fill * quantity
        fee = self.costs.buy_cost(fill, quantity)
        cost = gross + fee

        self.current_capital -= cost
        self.total_fees += fee

        # 历史回测时buy_date从参数传入，非历史回测用当天日期
        if buy_date is None:
            buy_date = datetime.now().strftime("%Y-%m-%d")

        holding = {
            'symbol': symbol,
            'name': name,
            'buy_price': fill,          # 记录含滑点的成交价（原始参考价=price）
            'ref_price': price,         # 保留原始参考价，用于事后核算
            'quantity': quantity,
            'buy_date': buy_date,
            'cost': cost,               # 含费用的总成本，profit 用这个算才对
            'entry_fee': fee,           # 买入手续费
            'stock_reason': reason,     # 选股逻辑
            'timing_reason': timing_reason,  # 择时逻辑
            'hold_days': 0
        }
        self.holdings.append(holding)
        return holding

    def remove_holding(self, symbol, sell_price, sell_reason, sell_date=None):
        """卖出持仓
        sell_date: 卖出日期，None=今天（用于历史回测）
        → sell_price 为参考价（如收盘价），实际成交价含滑点，收入扣手续费
        """
        for i, h in enumerate(self.holdings):
            if h['symbol'] == symbol:
                holding = self.holdings.pop(i)

                # 含滑点的真实成交价
                fill = self.costs.fill_price_sell(sell_price)
                gross = fill * holding['quantity']
                fee = self.costs.sell_cost(fill, holding['quantity'])
                revenue = gross - fee
                profit = revenue - holding['cost']
                profit_pct = profit / holding['cost'] * 100

                self.current_capital += revenue
                self.total_fees += fee
                # 累计已实现收益
                self.realized_pnl += profit
                self.realized_pnl_pct = self.realized_pnl / self.initial_capital * 100

                # 历史回测时sell_date从参数传入
                if sell_date is None:
                    sell_date = datetime.now().strftime("%Y-%m-%d")

                trade = {
                    'symbol': symbol,
                    'name': holding['name'],
                    'buy_date': holding['buy_date'],
                    'buy_price': holding['buy_price'],
                    'sell_date': sell_date,
                    'sell_price': fill,
                    'ref_sell_price': sell_price,
                    'quantity': holding['quantity'],
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'hold_days': holding['hold_days'],
                    'stock_reason': holding['stock_reason'],
                    'timing_reason': holding['timing_reason'],
                    'sell_reason': sell_reason,
                    'entry_fee': holding.get('entry_fee', 0),
                    'exit_fee': fee,
                }
                self.trades.append(trade)
                self.all_trades.append(trade)
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
    
    def get_total_return(self, prices=None):
        """计算总收益率"""
        prices = prices or {}
        holdings_value = sum(
            prices.get(h['symbol'], h['buy_price']) * h['quantity']
            for h in self.holdings
        )
        return (self.current_capital + holdings_value - self.initial_capital) / self.initial_capital

    def get_floating_pnl(self, prices=None):
        """计算浮动收益（未实现盈亏）"""
        prices = prices or {}
        floating = 0.0
        for h in self.holdings:
            current_price = prices.get(h['symbol'], h['buy_price'])
            floating += (current_price - h['buy_price']) * h['quantity']
        return floating

    def get_floating_pnl_pct(self, prices=None):
        """浮动收益率"""
        return self.get_floating_pnl(prices) / self.initial_capital * 100

    def get_total_pnl(self, prices=None):
        """总收益 = 已实现 + 浮动"""
        return self.realized_pnl + self.get_floating_pnl(prices)

    def get_total_pnl_pct(self, prices=None):
        """总收益率"""
        return self.get_total_pnl(prices) / self.initial_capital * 100
    
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
        # 从字典列表中提取数值
        values = []
        for item in self.equity_curve:
            if isinstance(item, dict):
                val = item.get('value', 0)
            else:
                val = item
            if val is not None and isinstance(val, (int, float)):
                values.append(val)
        
        if not values:
            return 0
        peak = self.initial_capital
        max_dd = 0
        for value in values:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd
    
    def get_sharpe_ratio(self):
        """计算夏普比率（统一口径：ddof=1，扣无风险利率 1.5%）"""
        if len(self.equity_curve) < 2:
            return 0
        from core.metrics import compute, RISK_FREE_ANNUAL

        perf = compute(self.equity_curve, initial_capital=self.initial_capital,
                       periods_per_year=252, risk_free_annual=RISK_FREE_ANNUAL)
        return perf.sharpe
    
    def to_dict(self, prices=None):
        """转换为字典格式（用于JSON输出）"""
        prices = prices or {}
        total_value = self.get_total_value(prices)
        floating_pnl = self.get_floating_pnl(prices)
        floating_pnl_pct = self.get_floating_pnl_pct(prices)
        total_pnl = self.realized_pnl + floating_pnl
        total_pnl_pct = total_pnl / self.initial_capital * 100

        return {
            'name': self.name,
            'category': self.category,
            'version': self.version,
            'description': self.get_description(),
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_value': total_value,
            'total_return': self.get_total_return(prices),
            'monthly_return': self.get_total_return(prices),  # 简化
            'sharpe_ratio': self.get_sharpe_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'win_rate': self.get_win_rate(),
            # 双收益分类
            'realized_pnl': round(self.realized_pnl, 2),
            'realized_pnl_pct': round(self.realized_pnl_pct, 2),
            'floating_pnl': round(floating_pnl, 2),
            'floating_pnl_pct': round(floating_pnl_pct, 2),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'holdings': self.holdings,
            'total_fees': round(self.total_fees, 2),
            'trades': self.trades[-10:],  # 最近10笔（看板展示用）
            'all_trades': self.all_trades,  # 完整记录（统计检验用，不截断）
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
