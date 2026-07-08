# -*- coding: utf-8 -*-
"""
技术突破策略：捕捉放量突破、动能突破前的股票
基于技术指标选股，与择时信号配合使用
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy


class TechnicalBreakoutStrategy(EventStrategy):
    """技术突破策略基类"""

    def __init__(self, name, category="技术突破"):
        super().__init__(name, category)

    def get_universe(self, helper, sample=80):
        """获取股票池（沪深300，按市值降序抽样）"""
        stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
        return stocks[:sample] if len(stocks) > sample else stocks

    def calculate_indicators(self, df):
        """计算技术指标"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()

        # 成交量均线
        df['vol_ma5'] = df['volume'].rolling(5).mean()
        df['vol_ma10'] = df['volume'].rolling(10).mean()

        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['dif'] - df['dea']) * 2

        # KDJ
        low_min = df['low'].rolling(9, min_periods=1).min()
        high_max = df['high'].rolling(9, min_periods=1).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        df['k'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['d'] = df['k'].ewm(alpha=1/3, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 前期高点（20日）
        df['high_20'] = df['high'].rolling(20).max().shift(1)

        return df


class VolumeBreakoutStrategy(TechnicalBreakoutStrategy):
    """量价突破策略：放量突破前期高点"""

    def __init__(self):
        super().__init__("量价突破")

    def get_description(self):
        return "放量突破前期高点，捕捉动能启动"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        # 抽样检查（避免全量扫描太慢）
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=90)
                if df is None or len(df) < 60:
                    continue

                df = self.calculate_indicators(df)
                latest = df.iloc[-1]
                prev = df.iloc[-2]

                # 信号条件：
                # 1. 收盘价突破20日最高点
                # 2. 成交量放大（>5日均量1.5倍）
                # 3. 均线多头排列（ma5>ma10>ma20）
                breakout_price = latest['close'] > latest['high_20']
                volume_surge = latest['volume'] > latest['vol_ma5'] * 1.5
                ma_bullish = (latest['ma5'] > latest['ma10'] > latest['ma20'])

                if breakout_price and volume_surge and ma_bullish:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,  # 简化，实际可查询股票名称
                        'reason': f"放量突破20日高点，量比{(latest['volume']/latest['vol_ma5']):.2f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results


class MACDCrossStrategy(TechnicalBreakoutStrategy):
    """MACD金叉策略 - 放宽条件"""

    def __init__(self):
        super().__init__("MACD金叉")

    def get_description(self):
        return "MACD金叉信号，捕捉动能转强（放宽至任意金叉）"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=90)
                if df is None or len(df) < 60:
                    continue

                df = self.calculate_indicators(df)
                latest = df.iloc[-1]
                prev = df.iloc[-2]

                # 放宽条件：
                # 1. 金叉即可（不要求零轴上方）
                # 2. 或者 DIF > 0 但 DEA < 0（金叉即将形成）
                golden_cross = (prev['dif'] <= prev['dea']) and (latest['dif'] > latest['dea'])
                # 放宽：只要金叉即可
                if golden_cross:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"MACD金叉，DIF={latest['dif']:.3f}, DEA={latest['dea']:.3f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results


class KDJOversoldStrategy(TechnicalBreakoutStrategy):
    """KDJ超卖金叉策略：低位金叉，捕捉反转启动"""

    def __init__(self):
        super().__init__("KDJ超卖金叉")

    def get_description(self):
        return "KDJ低位金叉，捕捉超卖反转"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        # 优化：扩大样本池从80到120
        sample_symbols = symbols[:120]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=90)
                if df is None or len(df) < 60:
                    continue

                df = self.calculate_indicators(df)
                latest = df.iloc[-1]
                prev = df.iloc[-2]

                # 优化：放宽条件
                # 1. K上穿D（金叉）
                # 2. K值<50（放宽超卖区域，原来是<40）
                # 3. 移除J值从负转正要求（过于严格）
                k_cross_d = (prev['k'] <= prev['d']) and (latest['k'] > latest['d'])
                oversold = latest['k'] < 50  # 原来是 < 40

                if k_cross_d and oversold:  # 移除了j_recover条件
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"KDJ超卖金叉，K={latest['k']:.1f} D={latest['d']:.1f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results


class RSIReversalStrategy(TechnicalBreakoutStrategy):
    """RSI超卖反转策略：RSI<40后回升，捕捉反弹机会"""

    def __init__(self):
        super().__init__("RSI超卖反转")

    def get_description(self):
        return "RSI超卖区域回升，捕捉反弹机会"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=90)
                if df is None or len(df) < 60:
                    continue

                df = self.calculate_indicators(df)
                latest = df.iloc[-1]
                prev = df.iloc[-2]

                # 信号条件：
                # 1. 前一日RSI<40（超卖）
                # 2. 今日RSI回升（>前一日）
                # 3. 价格站稳MA5
                oversold = prev['rsi'] < 40
                recovering = latest['rsi'] > prev['rsi']
                above_ma5 = latest['close'] > latest['ma5']

                if oversold and recovering and above_ma5:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"RSI超卖回升，RSI={latest['rsi']:.1f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results


class MomentumBreakoutStrategy(TechnicalBreakoutStrategy):
    """动量突破策略：突破60日高点+成交量放大+均线多头"""

    def __init__(self):
        super().__init__("动量突破")

    def get_description(self):
        return "突破60日高点+放量，捕捉主升浪启动"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        # 优化：扩大样本池从80到120
        sample_symbols = symbols[:120]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=120)
                if df is None or len(df) < 90:
                    continue

                df = self.calculate_indicators(df)
                df['high_60'] = df['high'].rolling(60).max().shift(1)
                latest = df.iloc[-1]

                # 优化：放宽条件组合，从4个条件改为2个核心条件
                # 核心条件：突破 + 放量
                breakout = latest['close'] > latest['high_60']
                volume_surge = latest['volume'] > latest['vol_ma10'] * 1.5  # 放宽量比要求
                
                # 附加条件（可选，有更好）
                ma_bullish = (latest['ma5'] > latest['ma10'] > latest['ma20'])

                # 优化：只要满足核心条件（突破+放量）即可入选
                if breakout and volume_surge:
                    reason = f"突破60日高点，量比{(latest['volume']/latest['vol_ma10']):.2f}"
                    if ma_bullish:
                        reason += "，均线多头"
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': reason
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results
