# -*- coding: utf-8 -*-
"""
交易模拟器
处理买卖执行、持仓管理
"""

from datetime import datetime
from core.execution import check_buy, check_sell


class TradingSimulator:
    """交易模拟器"""

    def __init__(self, strategy, timing):
        self.strategy = strategy
        self.timing = timing
        self.max_holdings = 3  # 最多3只持仓
        self.position_value = 10000  # 每只股票分配10000元（3万/3）
        self.max_hold_days = 20  # 最大持仓天数，超过强制卖出（避免死拿）

        # ========== 风控参数 ==========
        # 基础止损止盈（百分比）
        self.base_stop_loss = -10  # 基础止损 -10%
        self.base_take_profit = 15  # 基础止盈 +15%

        # 动态止损参数
        self.use_dynamic_stop_loss = True  # 是否启用动态止损
        self.volatility_period = 20  # 计算波动率的周期
        self.volatility_multiplier = 2.0  # 波动率倍数（用于动态止损 = ATR * multiplier）

        # 单日最大亏损限制
        self.max_daily_loss_pct = 5.0  # 单日亏损超过此比例时禁止买入

        # 仓位管理
        self.use_position_sizing = True  # 是否启用仓位管理
        self.high_confidence_weight = 1.0  # 高信心权重（满仓）
        self.medium_confidence_weight = 0.5  # 中信心权重（半仓）
        self.low_confidence_weight = 0.25  # 低信心权重（1/4仓）

        # 连续亏损追踪
        self.max_consecutive_losses = 3  # 连续亏损超过此次数后降低仓位
        self.consecutive_loss_reduction = 0.5  # 连续亏损后仓位缩减比例

        # 市场择时风控
        self.use_market_timing = True  # 是否启用市场择时风控
        self.max_market_drop_pct = -3.0  # 大盘跌幅超过此比例时禁止新买入

        # ========== 内部状态（由外部更新） ==========
        self.daily_pnl = 0.0  # 当日盈亏
        self.last_trade_date = None  # 上次交易日期
        self.consecutive_losses = 0  # 连续亏损次数
        self.current_position_size = 1.0  # 当前仓位系数（0-1）
        self.market_drop_today = 0.0  # 今日大盘跌幅

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

        # 检查单日最大亏损限制
        can_buy, msg = self.check_daily_loss_limit()
        if not can_buy:
            return False, msg

        # 检查市场择时风控
        can_buy, msg = self.check_market_risk()
        if not can_buy:
            return False, msg

        return True, None

    def execute_buy(self, symbol, name, price, reason, confidence="medium", helper=None, date=None):
        """执行买入
        confidence: 信心度 "high", "medium", "low"（用于仓位管理）
        helper: 复用调用方的helper（避免每次new）
        date: 历史回测日期（None=今天）
        """
        can_buy, msg = self.can_buy(symbol)
        if not can_buy:
            return None, msg

        # 动态计算买入数量：使用可用资金的1/3
        available = self.strategy.current_capital
        target_value = available / self.max_holdings  # 1/3资金

        # ========== 仓位管理：根据信心度调整仓位 ==========
        if self.use_position_sizing:
            # 基础仓位系数
            if confidence == "high":
                position_weight = self.high_confidence_weight
            elif confidence == "low":
                position_weight = self.low_confidence_weight
            else:
                position_weight = self.medium_confidence_weight

            # 连续亏损后降低仓位
            position_weight *= self.current_position_size

            # 应用仓位权重
            target_value *= position_weight

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

        # 涨跌停 / 停牌执行约束
        chk = check_buy(df, symbol, name, ref_col="close", target_date=date)
        if not chk.can_trade:
            return None, chk.reason
        price = chk.fill_price if chk.fill_price else price

        df = self.timing.add_indicators(df)
        has_signal, timing_reason = self.timing.check_buy_signals(df)

        if not has_signal:
            return None, "无买入择时信号"

        # 执行买入，传入实际日期（消除datetime.now()未来函数Bug）
        holding = self.strategy.add_holding(
            symbol, name, price, quantity, reason, timing_reason, buy_date=date)

        # 记录信心度和仓位权重到持仓
        holding['confidence'] = confidence
        holding['position_weight'] = position_weight if self.use_position_sizing else 1.0

        return holding, "买入成功"

    def check_and_sell(self, symbol, current_price, helper=None, date=None):
        """检查持仓是否需要卖出
        helper: 复用调用方的helper
        date: 历史回测日期（None=今天）
        T+1限制：买入当天（hold_days=0）不能卖出
        """
        for holding in self.strategy.holdings:
            if holding['symbol'] == symbol:
                # T+1限制：当天买入不能当天卖。
                # 用 buy_date 与目标日比较（按日历），而不是 hold_days——
                # hold_days 会在买入当日被 update_positions 加到 1，
                # 同一天重跑回测会误把当日买入当成可卖（产生幻影同日交易）。
                target_day = (date or datetime.now().strftime('%Y-%m-%d'))
                buy_day = str(holding.get('buy_date', ''))[:10].replace('-', '')
                if buy_day == target_day.replace('-', ''):
                    return False, None

                position_price = holding['buy_price']

                # ========== 动态止损计算 ==========
                stop_loss_pct = self._calculate_dynamic_stop_loss(
                    symbol, position_price, helper, date
                ) if self.use_dynamic_stop_loss else self.base_stop_loss

                # 止损止盈优先（不依赖K线，避免API失败导致无法止损）
                profit_pct = (current_price - position_price) / position_price * 100
                if profit_pct <= stop_loss_pct:
                    return True, f"止损({profit_pct:.1f}%, 动态{stop_loss_pct:.1f}%)"
                if profit_pct >= self.base_take_profit:
                    return True, f"止盈({profit_pct:.1f}%)"

                # 获取K线数据检查卖出信号
                if helper is None:
                    from data.akshare_helper import AKShareHelper
                    helper = AKShareHelper()
                df = helper.get_history_kline(symbol, days=60, end_date=date)

                if df is not None and not df.empty and len(df) >= 2:
                    # 涨跌停卖出约束：跌停卖不掉，止损失效
                    chk = check_sell(df, symbol, holding.get('name', ''), ref_col="close", target_date=date)
                    if not chk.can_trade:
                        # 卖不掉就得继续持有，记录被阻塞的天数
                        holding['blocked_sell_days'] = holding.get('blocked_sell_days', 0) + 1
                        return False, chk.reason

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

    # ========== 新增风控方法 ==========

    def _calculate_dynamic_stop_loss(self, symbol, position_price, helper=None, date=None):
        """计算动态止损幅度
        使用ATR（Average True Range）或历史波动率计算
        返回：止损百分比（负数）
        """
        try:
            if helper is None:
                from data.akshare_helper import AKShareHelper
                helper = AKShareHelper()

            df = helper.get_history_kline(symbol, days=self.volatility_period + 10, end_date=date)
            if df is None or df.empty or len(df) < self.volatility_period:
                return self.base_stop_loss

            # 计算 ATR（Average True Range）
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values

            # True Range = max(H-L, |H-PC|, |PC-L|)
            tr = []
            for i in range(len(close)):
                if i == 0:
                    tr.append(high[i] - low[i])
                else:
                    h_l = high[i] - low[i]
                    h_pc = abs(high[i] - close[i - 1])
                    pc_l = abs(close[i - 1] - low[i])
                    tr.append(max(h_l, h_pc, pc_l))

            # ATR = 简单移动平均
            atr = sum(tr[-self.volatility_period:]) / self.volatility_period

            # 动态止损 = ATR * multiplier / 买入价 * 100
            atr_loss_pct = (atr / position_price) * 100 * self.volatility_multiplier

            # 限制在合理范围内：最低3%，最高15%
            dynamic_stop_loss = -min(max(atr_loss_pct, 3.0), 15.0)

            # 如果计算出的止损比基础止损更大（损失更小），使用更保守的
            return min(dynamic_stop_loss, self.base_stop_loss)

        except Exception:
            return self.base_stop_loss

    def check_daily_loss_limit(self):
        """检查单日最大亏损限制
        返回：(是否可以买入, 原因)
        """
        if not hasattr(self, 'daily_pnl'):
            return True, None

        # 计算当日亏损占初始资金的比例
        daily_loss_pct = abs(self.daily_pnl) / self.strategy.initial_capital * 100 if self.daily_pnl < 0 else 0

        if self.daily_pnl < 0 and daily_loss_pct > self.max_daily_loss_pct:
            return False, f"单日亏损超限({daily_loss_pct:.1f}% > {self.max_daily_loss_pct}%)"

        return True, None

    def check_market_risk(self):
        """检查市场择时风控
        根据大盘跌幅决定是否禁止新买入
        返回：(是否可以买入, 原因)
        """
        if not self.use_market_timing:
            return True, None

        if self.market_drop_today < self.max_market_drop_pct:
            return False, f"大盘大跌({self.market_drop_today:.1f}%), 禁止新买入"

        return True, None

    def update_daily_pnl(self, pnl):
        """更新当日盈亏（由外部调用）"""
        self.daily_pnl = pnl

    def reset_daily_pnl(self):
        """重置当日盈亏（新的一天开始时调用）"""
        self.daily_pnl = 0.0

    def record_trade_result(self, profit_pct):
        """记录交易结果，用于追踪连续亏损
        profit_pct: 本次交易收益率（百分比）
        """
        if profit_pct < 0:
            self.consecutive_losses += 1
            # 连续亏损超过阈值，降低仓位
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.current_position_size *= self.consecutive_loss_reduction
                self.current_position_size = max(self.current_position_size, 0.25)  # 最低25%
        else:
            # 盈利后重置连续亏损计数和仓位
            self.consecutive_losses = 0
            self.current_position_size = 1.0

    def set_market_drop(self, drop_pct):
        """设置大盘今日跌幅（由外部调用）
        drop_pct: 大盘跌幅百分比，如 -2.5 表示下跌2.5%
        """
        self.market_drop_today = drop_pct

    def get_risk_status(self):
        """获取当前风控状态（用于监控）"""
        return {
            'consecutive_losses': self.consecutive_losses,
            'current_position_size': self.current_position_size,
            'daily_pnl': self.daily_pnl,
            'market_drop_today': self.market_drop_today,
            'use_dynamic_stop_loss': self.use_dynamic_stop_loss,
            'use_position_sizing': self.use_position_sizing,
            'use_market_timing': self.use_market_timing
        }
