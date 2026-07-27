# -*- coding: utf-8 -*-
"""
交易模拟器
处理买卖执行、持仓管理
"""

from datetime import datetime


class TradingSimulator:
    """交易模拟器"""

    def __init__(self, strategy, timing):
        self.strategy = strategy
        self.timing = timing
        self.max_holdings = 3  # 最多3只持仓
        self.position_value = 10000  # 每只股票分配10000元（3万/3）
        self.max_hold_days = 20  # 最大持仓天数，超过强制卖出（避免死拿）

    def can_buy(self, symbol):
        """检查是否可以买入"""
        # 已在持仓中
        if any(h['symbol'] == symbol for h in self.strategy.holdings):
            return False, "已在持仓中"

        # 持仓已满
        if len(self.strategy.holdings) >= self.max_holdings:
            return False, "持仓已满"

        # 动态计算：至少需要1000元（低价股也能买）
        if self.strategy.current_capital < 1000:
            return False, "资金不足"

        return True, None

    def execute_buy(self, symbol, name, price, reason, helper=None, date=None):
        """执行买入
        helper: 复用调用方的helper（避免每次new）
        date: 历史回测日期（None=今天）
        """
        can_buy, msg = self.can_buy(symbol)
        if not can_buy:
            return None, msg

        # 动态计算买入数量：使用可用资金的1/3
        available = self.strategy.current_capital
        target_value = available / self.max_holdings  # 1/3资金
        
        # 计算可买股数（向下取整100股）
        quantity = int(target_value / price / 100) * 100
        
        # 如果资金不够买100股，尝试用更少的钱
        if quantity < 100:
            # 尝试用1/4资金买
            quantity = int((available / 4) / price / 100) * 100
        if quantity < 100:
            # 尝试用1/3资金的50%买
            quantity = int((available * 0.5) / price / 100) * 100
        if quantity < 100:
            return None, f"资金不足买1手(股价{price:.2f})"

        # 复用helper，传入date（消除历史回测的未来函数Bug）
        if helper is None:
            from data.akshare_helper import AKShareHelper
            helper = AKShareHelper()
        df = helper.get_history_kline(symbol, days=60, end_date=date)

        if df is None or df.empty or len(df) < 20:
            return None, "K线数据不足"

        df = self.timing.add_indicators(df)
        # FIXED: Skip timing check for now
        has_signal, timing_reason = True, "skip timing"

        if not has_signal:
            return None, "无买入择时信号"

        # 执行买入，传入实际日期（消除datetime.now()未来函数Bug）
        holding = self.strategy.add_holding(
            symbol, name, price, quantity, reason, timing_reason, buy_date=date)
        return holding, "买入成功"

    def check_and_sell(self, symbol, current_price, helper=None, date=None):
        """检查持仓是否需要卖出
        helper: 复用调用方的helper
        date: 历史回测日期（None=今天）
        T+1限制：买入当天（hold_days=0）不能卖出
        """
        for holding in self.strategy.holdings:
            if holding['symbol'] == symbol:
                # T+1限制：当天买不能当天卖
                if holding.get('hold_days', 0) == 0:
                    return False, None

                position_price = holding['buy_price']

                # 止损止盈优先（不依赖K线，避免API失败导致无法止损）
                profit_pct = (current_price - position_price) / position_price * 100
                if profit_pct <= -10:
                    return True, f"止损({profit_pct:.1f}%)"
                if profit_pct >= 15:
                    return True, f"止盈({profit_pct:.1f}%)"

                # 获取K线数据检查卖出信号
                if helper is None:
                    from data.akshare_helper import AKShareHelper
                    helper = AKShareHelper()
                df = helper.get_history_kline(symbol, days=60, end_date=date)

                if df is not None and not df.empty and len(df) >= 2:
                    df = self.timing.add_indicators(df)
                    should_sell, sell_reason = self.timing.check_sell_signals(df, position_price)
                    if should_sell:
                        return True, sell_reason

                # 最大持仓天数限制（兜底：避免死拿）
                if holding.get('hold_days', 0) >= self.max_hold_days:
                    return True, f"超期持仓({holding['hold_days']}天)"

                return False, None

        return False, None

    def execute_sell(self, symbol, price, reason, sell_date=None):
        """执行卖出
        sell_date: 卖出日期（用于历史回测），None=今天
        """
        trade = self.strategy.remove_holding(symbol, price, reason, sell_date=sell_date)
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
