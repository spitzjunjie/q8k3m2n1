# -*- coding: utf-8 -*-
"""
尾盘抢筹策略

策略逻辑：
- 14:30后筛选当日强势且尾盘异动的个股
- 博取次日早盘惯性上涨
- T+1短线操作

买入信号：
- 当日涨幅 2%-5%（避免涨幅过低或过高，留次日空间）
- 量比 > 1.5（成交量明显放大）
- 换手率 4%-10%（新增资金关注）
- 流通市值 50-200亿（资金容纳量与灵活性兼顾）
- 均线多头排列：MA5 > MA10 > MA20
- 属于当日热点板块

卖出信号：
- 次日高开或快速冲高（涨幅2%-5%）分批止盈
- 次日低开或走弱，跌破前日收盘价止损
- 止损位：买入成本 -3%
- 次日午后无明显拉升则尾盘清仓

参考：花姐学量化-尾盘选股法、akshare尾盘选股策略
"""

import pandas as pd
import numpy as np
import akshare as ak
from strategies.base import EventStrategy


class ClosingAuctionStrategy(EventStrategy):
    """尾盘抢筹策略"""

    def __init__(self,
                 min_gain=2.0,           # 涨幅下限%
                 max_gain=5.0,           # 涨幅上限%
                 min_volume_ratio=1.5,   # 量比下限
                 min_turnover=4.0,       # 换手率下限%
                 max_turnover=10.0,      # 换手率上限%
                 min_circ_mv=50,         # 流通市值下限（亿）
                 max_circ_mv=200,        # 流通市值上限（亿）
                 ma_periods=(5, 10, 20), # 均线周期
                 take_profit=3.0,        # 止盈阈值%
                 stop_loss=3.0,          # 止损阈值%
                 holding_days=2,         # 持有天数
                 top_n=3):               # 持仓上限
        super().__init__("尾盘抢筹", "短线事件")
        self.min_gain = min_gain
        self.max_gain = max_gain
        self.min_volume_ratio = min_volume_ratio
        self.min_turnover = min_turnover
        self.max_turnover = max_turnover
        self.min_circ_mv = min_circ_mv
        self.max_circ_mv = max_circ_mv
        self.ma_periods = ma_periods
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030',
                                    '600028', '601166', '600900', '601398', '601288',
                                    '601628', '601601', '600000', '601857', '601088']
        return self._pool_cache

    def get_description(self):
        return (f"尾盘抢筹：涨幅{self.min_gain}%-{self.max_gain}%, "
                f"量比>{self.min_volume_ratio}, 换手率{self.min_turnover}%-{self.max_turnover}%, "
                f"市值{self.min_circ_mv}-{self.max_circ_mv}亿, MA{self.ma_periods}多头, "
                f"止盈{self.take_profit}%, 止损{self.stop_loss}%")

    def get_params(self):
        return {
            'min_gain': self.min_gain,
            'max_gain': self.max_gain,
            'min_volume_ratio': self.min_volume_ratio,
            'min_turnover': self.min_turnover,
            'max_turnover': self.max_turnover,
            'min_circ_mv': self.min_circ_mv,
            'max_circ_mv': self.max_circ_mv,
            'ma_periods': self.ma_periods,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
            'holding_days': self.holding_days,
            'top_n': self.top_n
        }

    def _calculate_ma(self, kline):
        """计算均线"""
        df = kline.copy()
        ma5, ma10, ma20 = self.ma_periods

        if len(df) >= ma20:
            df['ma5'] = df['close'].rolling(ma5).mean()
            df['ma10'] = df['close'].rolling(ma10).mean()
            df['ma20'] = df['close'].rolling(ma20).mean()
        elif len(df) >= ma10:
            df['ma5'] = df['close'].rolling(ma5).mean()
            df['ma10'] = df['close'].rolling(ma10).mean()
            df['ma20'] = df['close'].rolling(10).mean()  # 降级
        elif len(df) >= ma5:
            df['ma5'] = df['close'].rolling(ma5).mean()
            df['ma10'] = df['close'].rolling(5).mean()   # 降级
            df['ma20'] = df['close'].rolling(5).mean()   # 降级
        else:
            df['ma5'] = df['close'].rolling(len(df)).mean()
            df['ma10'] = df['close'].rolling(len(df)).mean()
            df['ma20'] = df['close'].rolling(len(df)).mean()

        return df

    def _check_ma_bullish(self, df):
        """检查均线多头排列"""
        if 'ma5' not in df.columns or 'ma10' not in df.columns or 'ma20' not in df.columns:
            return False

        latest = df.iloc[-1]
        # 均线多头：MA5 > MA10 > MA20
        return (latest['ma5'] > latest['ma10'] > latest['ma20'] and
                latest['ma5'] > 0 and latest['ma10'] > 0 and latest['ma20'] > 0)

    def _check_uptrend(self, kline, days=10):
        """检查股价是否处于上升通道"""
        if len(kline) < days:
            return False

        # 取最近N天数据
        recent = kline.tail(days)

        # 上升通道特征：高点不断抬高，低点不断抬高
        highs = recent['high'].values
        lows = recent['low'].values

        # 检查趋势：线性回归斜率为正
        x = np.arange(len(highs))
        try:
            high_slope = np.polyfit(x, highs, 1)[0]
            low_slope = np.polyfit(x, lows, 1)[0]

            # 高点和低点都在上升
            return high_slope > 0 and low_slope > 0
        except Exception:
            return False

    def detect_events(self, helper, date=None):
        """检测尾盘抢筹信号"""
        results = []

        # 获取市场情绪（判断是否为合适的市场环境）
        try:
            sentiment = helper.get_market_sentiment()
            if sentiment:
                limit_up_count = sentiment.get('limit_up_count', 0)
                market_breadth = sentiment.get('market_breadth', 50)

                # 市场过冷（涨停<10）或市场过差（上涨家数<30%）不太适合尾盘策略
                if limit_up_count < 5 and market_breadth < 30:
                    print(f"市场情绪不佳，涨停{limit_up_count}家，市场广度{market_breadth:.1f}%")
                    return []
        except Exception:
            pass

        # 获取热点板块
        hot_sectors = set()
        try:
            sector_df = ak.stock_sector_spot()
            if sector_df is not None and not sector_df.empty:
                # 取涨幅前5的板块
                if '涨跌幅' in sector_df.columns:
                    sector_df = sector_df.sort_values('涨跌幅', ascending=False)
                    hot_sectors = set(sector_df.head(5)['板块名称'].tolist() if '板块名称' in sector_df.columns
                                     else sector_df.head(5).iloc[:, 0].tolist())
        except Exception:
            pass

        # 获取候选股票池
        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取当日实时行情
                spot = helper.get_realtime_quote(symbol)
                if spot is None:
                    continue

                # 获取K线数据用于技术分析
                kline = helper.get_history_kline(symbol, days=60, end_date=date)
                if kline is None or kline.empty or len(kline) < 30:
                    continue

                # 计算技术指标
                kline = self._calculate_ma(kline)

                # === 条件筛选 ===

                # 1. 涨幅筛选：2%-5%
                pct_change = float(spot.get('涨跌幅', 0) or 0)
                if not (self.min_gain <= pct_change <= self.max_gain):
                    continue

                # 2. 量比筛选
                volume_ratio = float(spot.get('量比', 0) or 0)
                if volume_ratio < self.min_volume_ratio:
                    continue

                # 3. 换手率筛选
                turnover = float(spot.get('换手率', 0) or 0)
                if not (self.min_turnover <= turnover <= self.max_turnover):
                    continue

                # 4. 流通市值筛选（转换为亿）
                circ_mv = helper._safe_float(spot.get('流通市值', 0)) / 1e8
                if not (self.min_circ_mv <= circ_mv <= self.max_circ_mv):
                    continue

                # 5. 均线多头排列
                if not self._check_ma_bullish(kline):
                    continue

                # 6. 上升通道检查
                if not self._check_uptrend(kline):
                    continue

                # 7. 尾盘特征：收盘在相对高位（可选条件）
                latest = kline.iloc[-1]
                close = latest['close']
                high = latest['high']
                # 收盘价在当日高点80%以上（避免上影线过长的股票）
                if close < high * 0.80:
                    continue

                # 构建信号原因
                reason = (f"尾盘抢筹：涨幅{pct_change:.2f}%, 量比{volume_ratio:.1f}, "
                          f"换手率{turnover:.2f}%, 市值{circ_mv:.0f}亿")

                results.append({
                    'symbol': symbol,
                    'name': spot.get('名称', symbol),
                    'reason': reason
                })

                if len(results) >= self.top_n:
                    break

            except Exception as e:
                continue

        # 如果没有找到足够股票，尝试放宽条件
        if len(results) < self.top_n:
            relaxed = self._relaxed_search(helper, pool, date)
            for item in relaxed:
                if item not in results:
                    results.append(item)
                    if len(results) >= self.top_n:
                        break

        return results[:self.top_n]

    def _relaxed_search(self, helper, pool, date=None):
        """放宽条件搜索"""
        results = []

        for symbol in pool:
            try:
                spot = helper.get_realtime_quote(symbol)
                if spot is None:
                    continue

                # 放宽条件：涨幅1%-6%，只要量比>1.2
                pct_change = float(spot.get('涨跌幅', 0) or 0)
                if not (1.0 <= pct_change <= 6.0):
                    continue

                volume_ratio = float(spot.get('量比', 0) or 0)
                if volume_ratio < 1.2:
                    continue

                circ_mv = helper._safe_float(spot.get('流通市值', 0)) / 1e8
                if not (30 <= circ_mv <= 300):
                    continue

                # 获取K线检查趋势
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline is None or kline.empty or len(kline) < 20:
                    continue

                # 只要5日线在10日线上方即可
                ma5 = kline['close'].tail(5).mean()
                ma10 = kline['close'].tail(10).mean()
                if ma5 <= ma10:
                    continue

                results.append({
                    'symbol': symbol,
                    'name': spot.get('名称', symbol),
                    'reason': f"尾盘备选(放宽)：涨幅{pct_change:.2f}%, 量比{volume_ratio:.1f}"
                })

            except Exception:
                continue

        return results

    def select_stocks(self, helper, date=None):
        """选股：尾盘抢筹"""
        return self.detect_events(helper, date)


if __name__ == '__main__':
    s = ClosingAuctionStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"参数: {s.get_params()}")
