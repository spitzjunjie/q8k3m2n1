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

    def get_universe(self, helper):
        """获取股票池（沪深300成分股）"""
        try:
            import akshare as ak
            df = ak.index_stock_cons(symbol="000300")
            if df.empty:
                return []
            return df['品种代码'].tolist()
        except Exception as e:
            print(f"获取股票池失败: {e}")
            return []

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
    """MACD金叉策略：零轴上方金叉，动能转强"""

    def __init__(self):
        super().__init__("MACD金叉")

    def get_description(self):
        return "MACD零轴上方金叉，捕捉动能转强"

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
                # 1. DIF上穿DEA（金叉）
                # 2. 零轴上方（DIF>0）
                # 3. MACD柱由负转正
                golden_cross = (prev['dif'] <= prev['dea']) and (latest['dif'] > latest['dea'])
                above_zero = latest['dif'] > 0
                macd_positive = latest['macd'] > 0

                if golden_cross and above_zero and macd_positive:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"MACD零轴上方金叉，DIF={latest['dif']:.3f}"
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
                # 1. K上穿D（金叉）
                # 2. K值<40（超卖区域）
                # 3. J值从负转正
                k_cross_d = (prev['k'] <= prev['d']) and (latest['k'] > latest['d'])
                oversold = latest['k'] < 40
                j_recover = (prev['j'] < 0) and (latest['j'] > 0)

                if k_cross_d and oversold and j_recover:
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
        return "突破60日高点+放量+均线多头，捕捉主升浪启动"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=120)
                if df is None or len(df) < 90:
                    continue

                df = self.calculate_indicators(df)
                df['high_60'] = df['high'].rolling(60).max().shift(1)
                latest = df.iloc[-1]

                # 信号条件：
                # 1. 突破60日最高点
                # 2. 成交量放大（>10日均量2倍）
                # 3. 均线多头排列（ma5>ma10>ma20>ma60）
                # 4. RSI在40-70之间（健康区间）
                breakout = latest['close'] > latest['high_60']
                volume_surge = latest['volume'] > latest['vol_ma10'] * 2
                ma_bullish = (latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60'])
                rsi_healthy = 40 < latest['rsi'] < 70

                if breakout and volume_surge and ma_bullish and rsi_healthy:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"突破60日高点，量比{(latest['volume']/latest['vol_ma10']):.2f}，RSI={latest['rsi']:.0f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results
