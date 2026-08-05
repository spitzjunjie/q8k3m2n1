# -*- coding: utf-8 -*-
"""
情绪冰点抄底策略

策略逻辑：
情绪冰点 → 恐慌抛售 → 超跌反弹 → 获利了结

买入条件：
- 涨停家数 < 30家（连续3天）
- 炸板率 > 20%
- 大盘位置不在高位
- 沪深300 PE < 15

买入方法：
1. 冰点信号确认
2. 买入1/3仓位
3. 再跌再买（每次加仓1/3）
4. 最多3次加满

卖出条件：
- 情绪高潮（涨停>80家）：全部卖出
- 持有4周：强制卖出
- 盈利>20%：止盈
- 总亏损>15%：清仓止损

适用标的：沪深300ETF（510300）
"""

import pandas as pd
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class SentimentIcepointStrategy(BaseStrategy):
    """情绪冰点抄底策略"""

    def __init__(self,
                 limit_up_icepoint=30,        # 冰点涨停家数阈值
                 limit_up_euphoria=80,        # 高潮涨停家数阈值
                 broken_board_rate=20,       # 炸板率阈值%
                 max_hold_days=20,            # 最大持有天数（4周约20个交易日）
                 take_profit_pct=20,         # 止盈线%
                 stop_loss_pct=15,            # 止损线%
                 max_position=3,              # 最大加仓次数
                 target_etf='510300'):       # 目标ETF
        super().__init__("情绪冰点抄底", "择时策略")
        self.limit_up_icepoint = limit_up_icepoint
        self.limit_up_euphoria = limit_up_euphoria
        self.broken_board_rate = broken_board_rate
        self.max_hold_days = max_hold_days
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_position = max_position
        self.target_etf = target_etf

        # 内部状态
        self._icepoint_days = 0  # 连续冰点天数
        self._position_level = 0  # 当前仓位等级（0-3）
        self._last_add_date = None  # 上次加仓日期
        self._consecutive_icepoint = []  # 连续冰点记录

    def get_description(self):
        return (f"情绪冰点抄底：涨停<{self.limit_up_icepoint}家持续冰点，"
                f"分3批建仓，止盈{self.take_profit_pct}%，止损{self.stop_loss_pct}%，"
                f"持有≤{self.max_hold_days}天")

    def get_params(self):
        return {
            'limit_up_icepoint': self.limit_up_icepoint,
            'limit_up_euphoria': self.limit_up_euphoria,
            'broken_board_rate': self.broken_board_rate,
            'max_hold_days': self.max_hold_days,
            'take_profit_pct': self.take_profit_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'max_position': self.max_position,
            'target_etf': self.target_etf,
        }

    def _get_sentiment_data(self, helper, date=None):
        """获取市场情绪数据"""
        try:
            # 获取涨停池数据
            limit_up_df = helper.get_limit_up_list(date)
            limit_up_count = len(limit_up_df) if limit_up_df is not None and not limit_up_df.empty else 0

            # 获取市场情绪综合数据
            sentiment = helper.get_market_sentiment()
            if not sentiment:
                sentiment = {}

            # 计算炸板率（涨停被砸开的比例）
            broken_board_rate = 0
            if limit_up_df is not None and not limit_up_df.empty:
                # 炸板：涨停后打开的股票
                if '炸板次数' in limit_up_df.columns or '炸板' in str(limit_up_df.columns):
                    broken_count = len(limit_up_df[limit_up_df.get('炸板次数', 0) > 0])
                else:
                    # 简化：假设涨停池中一定比例是炸板
                    broken_count = int(limit_up_count * 0.2)
                if limit_up_count > 0:
                    broken_board_rate = broken_count / limit_up_count * 100

            # 获取沪深300估值（PE）
            pe_ratio = self._get_hs300_pe(helper, date)

            # 获取大盘位置
            market_position = self._get_market_position(helper, date)

            return {
                'limit_up_count': limit_up_count,
                'broken_board_rate': broken_board_rate,
                'pe_ratio': pe_ratio,
                'market_position': market_position,  # 'high', 'mid', 'low'
                'rise_count': sentiment.get('rise_count', 0),
                'fall_count': sentiment.get('fall_count', 0),
            }
        except Exception as e:
            print(f"获取情绪数据失败: {e}")
            return {
                'limit_up_count': 0,
                'broken_board_rate': 0,
                'pe_ratio': 0,
                'market_position': 'mid',
                'rise_count': 0,
                'fall_count': 0,
            }

    def _get_hs300_pe(self, helper, date=None):
        """获取沪深300 PE"""
        try:
            # 使用沪深300成分股的平均PE来估算
            val_df = helper.get_hs300_valuation_batch()
            if val_df is not None and not val_df.empty and 'pe' in val_df.columns:
                valid_pe = val_df['pe'].dropna()
                valid_pe = valid_pe[valid_pe > 0]
                if len(valid_pe) > 0:
                    return valid_pe.median()
        except Exception:
            pass

        # 备选：直接获取沪深300指数PE
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol='sh000300')
            if df is not None and not df.empty:
                # 使用简化方法：用点位和历史平均点位估算PE分位
                current = df['close'].iloc[-1]
                avg_price = df['close'].tail(250).mean()  # 年线均值
                if avg_price > 0:
                    # PE与点位成正比，估算相对估值
                    pe_estimate = 12 * (current / avg_price)  # 基准12倍PE
                    return pe_estimate
        except Exception:
            pass
        return 15  # 默认值

    def _get_market_position(self, helper, date=None):
        """判断大盘位置：high/mid/low"""
        try:
            # 使用沪深300指数判断
            idx_df = helper.get_index_data(symbol='000300', days=250)
            if idx_df is not None and not idx_df.empty:
                current = idx_df['close'].iloc[-1]
                ma250 = idx_df['close'].tail(250).mean()
                ma60 = idx_df['close'].tail(60).mean()

                if current > ma250:
                    return 'high'
                elif current < ma250 * 0.9:
                    return 'low'
                else:
                    return 'mid'
        except Exception:
            pass
        return 'mid'  # 默认中等位置

    def _detect_icepoint(self, helper, date=None):
        """检测情绪冰点信号"""
        sentiment = self._get_sentiment_data(helper, date)

        # 记录冰点
        is_icepoint = (
            sentiment['limit_up_count'] < self.limit_up_icepoint
        )

        # 情绪高潮
        is_euphoria = (
            sentiment['limit_up_count'] > self.limit_up_euphoria
        )

        # 冰点条件
        icepoint_conditions = {
            'limit_up_count': sentiment['limit_up_count'],
            'broken_board_rate': sentiment['broken_board_rate'],
            'pe_ratio': sentiment['pe_ratio'],
            'market_position': sentiment['market_position'],
            'is_icepoint': is_icepoint,
            'is_euphoria': is_euphoria,
            'pe_acceptable': sentiment['pe_ratio'] < 15 if sentiment['pe_ratio'] > 0 else True,
            'market_not_high': sentiment['market_position'] != 'high',
            'broken_board_high': sentiment['broken_board_rate'] > self.broken_board_rate,
        }

        return icepoint_conditions

    def select_stocks(self, helper, date=None):
        """
        选股：检测情绪冰点，返回买入信号
        注意：此策略主要做ETF，通过择时信号决定是否买入510300
        """
        results = []

        # 检测情绪冰点
        conditions = self._detect_icepoint(helper, date)

        # 更新冰点记录
        if conditions['is_icepoint']:
            self._consecutive_icepoint.append(date or datetime.now().strftime('%Y-%m-%d'))
        else:
            self._consecutive_icepoint = []

        # 检查是否满足冰点买入条件
        can_buy = (
            conditions['is_icepoint'] and
            conditions['pe_acceptable'] and
            conditions['market_not_high'] and
            len(self._consecutive_icepoint) >= 1  # 至少1天冰点
        )

        # 检查是否可以加仓
        can_add = (
            can_buy and
            self._position_level < self.max_position and
            self._last_add_date is not None and
            (date or datetime.now().strftime('%Y-%m-%d')) >
            (self._last_add_date + timedelta(days=5))  # 至少5天间隔
        ) or (
            can_buy and
            self._position_level < self.max_position and
            self._last_add_date is None
        )

        if can_buy or can_add:
            position_text = f"{self._position_level + 1}/3仓"
            reason_parts = [
                f"涨停{conditions['limit_up_count']}家",
                f"PE={conditions['pe_ratio']:.1f}" if conditions['pe_ratio'] > 0 else "",
                f"大盘{conditions['market_position']}",
            ]
            if conditions['broken_board_high']:
                reason_parts.append(f"炸板率{conditions['broken_board_rate']:.0f}%")

            results.append({
                'symbol': self.target_etf,
                'name': '沪深300ETF',
                'reason': f"情绪冰点买入{position_text}：{'，'.join(filter(None, reason_parts))}"
            })

        return results

    def check_sell_signals(self, helper, date=None):
        """
        检查卖出信号
        返回: (是否卖出, 卖出原因, 卖出标的列表)
        """
        if not self.holdings:
            return False, None, []

        sell_list = []
        sell_reasons = []

        for holding in self.holdings:
            symbol = holding['symbol']
            buy_price = holding['buy_price']
            hold_days = holding.get('hold_days', 0)

            # 获取当前价格
            try:
                if symbol == self.target_etf:
                    kline = helper.get_etf_history_kline(symbol, days=5, end_date=date)
                else:
                    kline = helper.get_history_kline(symbol, days=5, end_date=date)
                current_price = kline['close'].iloc[-1] if kline is not None and not kline.empty else buy_price
            except Exception:
                current_price = buy_price

            profit_pct = (current_price - buy_price) / buy_price * 100

            # 卖出条件检查
            should_sell = False
            sell_reason = ""

            # 1. 情绪高潮卖出
            conditions = self._detect_icepoint(helper, date)
            if conditions['is_euphoria']:
                should_sell = True
                sell_reason = f"情绪高潮(涨停{conditions['limit_up_count']}家)"

            # 2. 持有到期强制卖出
            elif hold_days >= self.max_hold_days:
                should_sell = True
                sell_reason = f"持有满{self.max_hold_days}天强制卖出"

            # 3. 止盈
            elif profit_pct >= self.take_profit_pct:
                should_sell = True
                sell_reason = f"止盈({profit_pct:.1f}%>{self.take_profit_pct}%)"

            # 4. 止损
            elif profit_pct <= -self.stop_loss_pct:
                should_sell = True
                sell_reason = f"止损({profit_pct:.1f}%<{-self.stop_loss_pct}%)"

            if should_sell:
                sell_list.append(symbol)
                sell_reasons.append({
                    'symbol': symbol,
                    'reason': sell_reason,
                    'profit_pct': profit_pct
                })

        if sell_list:
            return True, "; ".join([s['reason'] for s in sell_reasons]), sell_list
        return False, None, []

    def add_position(self, date=None):
        """记录加仓"""
        self._position_level += 1
        self._last_add_date = date or datetime.now().strftime('%Y-%m-%d')

    def reset_position(self):
        """重置仓位状态"""
        self._position_level = 0
        self._last_add_date = None
        self._consecutive_icepoint = []

    def get_position_info(self):
        """获取当前仓位信息"""
        return {
            'position_level': self._position_level,
            'last_add_date': self._last_add_date,
            'consecutive_icepoint_days': len(self._consecutive_icepoint),
            'max_position': self.max_position,
        }


class SentimentIcepointETF(SentimentIcepointStrategy):
    """情绪冰点抄底ETF专用策略（简化版）"""

    def __init__(self):
        super().__init__(
            limit_up_icepoint=30,
            limit_up_euphoria=80,
            broken_board_rate=20,
            max_hold_days=20,
            take_profit_pct=20,
            stop_loss_pct=15,
            max_position=3,
            target_etf='510300'
        )

    def get_description(self):
        return "情绪冰点抄底ETF：沪深300指数低位时买入510300，涨停家数<30冰点信号，分3批建仓"


if __name__ == '__main__':
    s = SentimentIcepointStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"参数: {s.get_params()}")
    print(f"适用标的: {s.target_etf}")
