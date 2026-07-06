# -*- coding: utf-8 -*-
"""
交易模拟器
处理买卖执行、持仓管理
"""

from datetime import datetime
import random


class TradingSimulator:
    """交易模拟器"""
    
    def __init__(self, strategy, timing):
        self.strategy = strategy
        self.timing = timing
        self.max_holdings = 3  # 最多3只持仓
        self.position_value = 10000  # 每只股票分配10000元（3万/3）
    
    def can_buy(self, symbol):
        """检查是否可以买入"""
        # 已在持仓中
        if any(h['symbol'] == symbol for h in self.strategy.holdings):
            return False, "已在持仓中"
        
        # 持仓已满
        if len(self.strategy.holdings) >= self.max_holdings:
            return False, "持仓已满"
        
        # 资金不足
        if self.strategy.current_capital < self.position_value:
            return False, "资金不足"
        
        return True, None
    
    def execute_buy(self, symbol, name, price, reason):
        """
        执行买入
        """
        can_buy, msg = self.can_buy(symbol)
        if not can_buy:
            return None, msg
        
        # 检查涨跌停
        # 简化处理：随机跳过涨跌停
        if random.random() < 0.1:  # 10%概率涨跌停
            return None, "涨跌停无法买入"
        
        # 计算买入数量（向下取整100股）
        quantity = int(self.position_value / price / 100) * 100
        if quantity < 100:
            return None, "资金不足以买入1手"
        
        # 检查择时信号
        from data.akshare_helper import AKShareHelper
        helper = AKShareHelper()
        df = helper.get_history_kline(symbol, days=60)
        
        if df.empty:
            return None, "无法获取K线数据"
        
        df = self.timing.add_indicators(df)
        has_signal, timing_reason = self.timing.check_buy_signals(df)
        
        if not has_signal:
            return None, "无买入择时信号"
        
        # 执行买入
        holding = self.strategy.add_holding(symbol, name, price, quantity, reason, timing_reason)
        return holding, "买入成功"
    
    def check_and_sell(self, symbol, current_price):
        """
        检查持仓是否需要卖出
        """
        for holding in self.strategy.holdings:
            if holding['symbol'] == symbol:
                position_price = holding['buy_price']
                
                # 获取K线数据检查卖出信号
                from data.akshare_helper import AKShareHelper
                helper = AKShareHelper()
                df = helper.get_history_kline(symbol, days=60)
                
                if not df.empty:
                    df = self.timing.add_indicators(df)
                    should_sell, sell_reason = self.timing.check_sell_signals(df, position_price)
                    
                    if should_sell:
                        return True, sell_reason
                
                # 检查止损止盈（简化版）
                profit_pct = (current_price - position_price) / position_price * 100
                if profit_pct <= -10:
                    return True, f"止损({profit_pct:.1f}%)"
                if profit_pct >= 15:
                    return True, f"止盈({profit_pct:.1f}%)"
                
                return False, None
        
        return False, None
    
    def execute_sell(self, symbol, price, reason):
        """
        执行卖出
        """
        trade = self.strategy.remove_holding(symbol, price, reason)
        return trade
    
    def rebalance(self, selected_stocks, prices):
        """
        重新平衡持仓
        根据最新选股结果调整持仓
        """
        selected_symbols = {s['symbol'] for s in selected_stocks}
        
        # 卖出不在选中列表中的持仓
        for holding in list(self.strategy.holdings):
            if holding['symbol'] not in selected_symbols:
                price = prices.get(holding['symbol'], holding['buy_price'])
                self.execute_sell(holding['symbol'], price, "调仓")
    
    def update_positions(self, prices):
        """
        更新所有持仓状态
        """
        self.strategy.update_holdings()
        
        for holding in self.strategy.holdings:
            symbol = holding['symbol']
            price = prices.get(symbol, holding['buy_price'])
            holding['current_price'] = price
            holding['profit'] = (price - holding['buy_price']) * holding['quantity']
            holding['profit_pct'] = (price - holding['buy_price']) / holding['buy_price'] * 100
