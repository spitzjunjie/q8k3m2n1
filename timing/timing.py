# -*- coding: utf-8 -*-
"""
择时信号模块
提供买卖时机判断
"""

import pandas as pd
import numpy as np


class TimingEngine:
    """择时引擎"""
    
    def __init__(self):
        self.name = "择时引擎"
    
    def add_indicators(self, df):
        """添加技术指标"""
        df = df.copy()

        # 移动平均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['signal']

        # KDJ
        low14 = df['low'].rolling(window=14).min()
        high14 = df['high'].rolling(window=14).max()
        rsv = (df['close'] - low14) / (high14 - low14) * 100
        df['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False).mean()
        df['kdj_j'] = df['kdj_k'] * 3 - df['kdj_d'] * 2

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 成交量均线
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()
        df['vol_ma10'] = df['volume'].rolling(window=10).mean()

        # ATR（Average True Range）- 用于动态止损
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        tr = []
        for i in range(len(close)):
            if i == 0:
                tr.append(high[i] - low[i])
            else:
                h_l = high[i] - low[i]
                h_pc = abs(high[i] - close[i - 1])
                pc_l = abs(close[i - 1] - low[i])
                tr.append(max(h_l, h_pc, pc_l))

        df['tr'] = tr
        df['atr14'] = pd.Series(tr).rolling(window=14).mean()

        # 历史波动率（用于辅助判断）
        df['returns'] = df['close'].pct_change()
        df['volatility20'] = df['returns'].rolling(window=20).std() * 100  # 百分比形式

        return df
    
    def check_buy_signals(self, df):
        """
        检查买入信号
        返回: (是否买入, 信号原因)
        """
        if len(df) < 20:
            return False, None
        
        signals = []
        row = df.iloc[-1]
        
        # 1. 回踩MA5/MA20
        if row['ma5'] and row['ma20']:
            if row['low'] <= row['ma5'] <= row['close']:
                signals.append("回踩MA5")
            if row['low'] <= row['ma20'] <= row['close']:
                signals.append("回踩MA20")
        
        # 2. MACD绿柱缩脚（金叉前兆）
        if len(df) >= 3:
            prev_hist = df['macd_hist'].iloc[-2]
            curr_hist = row['macd_hist']
            if prev_hist < 0 and curr_hist > prev_hist and curr_hist < 0:
                signals.append("MACD绿柱缩脚")
            # MACD金叉
            if df['macd'].iloc[-2] < df['signal'].iloc[-2] and row['macd'] > row['signal']:
                signals.append("MACD金叉")
        
        # 3. KDJ超卖金叉
        if len(df) >= 3:
            prev_k = df['kdj_k'].iloc[-2]
            curr_k = row['kdj_k']
            if prev_k < 30 and curr_k > 30:
                signals.append("KDJ超卖金叉")
            # 金叉
            if df['kdj_k'].iloc[-2] < df['kdj_d'].iloc[-2] and curr_k > row['kdj_d']:
                signals.append("KDJ金叉")
        
        # 4. RSI超卖（放宽到60）
        if row['rsi'] < 60:
            signals.append(f"RSI偏低({row['rsi']:.1f})")

        # 5. 温和放量上涨（放宽条件）
        if len(df) >= 10:
            avg_vol = df['volume'].iloc[-10:-1].mean()
            if avg_vol > 0 and row['volume'] > avg_vol * 0.5:
                if row['close'] >= df['close'].iloc[-2] * 0.98:  # 允许小幅回调
                    signals.append("量能正常")

        # 6. 均线多头排列（买入信号确认）
        if row['ma5'] and row['ma10'] and row['ma20']:
            if row['ma5'] > row['ma10'] > row['ma20']:
                signals.append("均线多头排列")

        # 7. 兜底信号：更宽松的判断，确保能产生交易
        if not signals:
            # 放宽条件：只要不是极端情况就允许买入
            if row['ma5'] and row['ma20']:
                # 价格在MA20附近（±10%以内）
                price_vs_ma20 = abs(row['close'] - row['ma20']) / row['ma20'] if row['ma20'] else 1
                # RSI在正常范围
                if price_vs_ma20 < 0.1 and 20 < row['rsi'] < 80:
                    signals.append("趋势正常(兜底)")
                # 价格在MA5附近
                elif abs(row['close'] - row['ma5']) / row['ma5'] < 0.05 if row['ma5'] else False:
                    signals.append("价格企稳(兜底)")

        # 返回最强信号
        if signals:
            return True, "; ".join(signals)
        return False, None
    
    def check_sell_signals(self, df, position_price):
        """
        检查卖出信号
        返回: (是否卖出, 卖出原因)
        """
        if len(df) < 2:
            return False, None
        
        row = df.iloc[-1]
        signals = []
        
        # 1. 止损 -10%
        if position_price > 0:
            loss_pct = (row['close'] - position_price) / position_price * 100
            if loss_pct <= -10:
                return True, f"止损({loss_pct:.1f}%)"
        
        # 2. 止盈 +15%
        if position_price > 0:
            profit_pct = (row['close'] - position_price) / position_price * 100
            if profit_pct >= 15:
                return True, f"止盈({profit_pct:.1f}%)"
        
        # 3. MACD红柱缩短
        if len(df) >= 3:
            prev_hist = df['macd_hist'].iloc[-2]
            curr_hist = row['macd_hist']
            if prev_hist > 0 and curr_hist < prev_hist:
                signals.append("MACD红柱缩短")
            # 死叉
            if df['macd'].iloc[-2] > df['signal'].iloc[-2] and row['macd'] < row['signal']:
                signals.append("MACD死叉")
        
        # 4. KDJ高位死叉
        if len(df) >= 3:
            if df['kdj_k'].iloc[-2] > 70 and row['kdj_k'] < row['kdj_d']:
                signals.append("KDJ高位死叉")
        
        # 5. RSI超买
        if row['rsi'] > 80:
            signals.append(f"RSI超买({row['rsi']:.1f})")
        
        # 6. 放量滞涨
        if len(df) >= 3:
            avg_vol = df['volume'].iloc[-5:-1].mean()
            if row['volume'] > avg_vol * 1.5:
                if row['close'] <= df['close'].iloc[-2]:
                    signals.append("放量滞涨")
        
        # 7. 均线破位
        if row['ma5'] and row['close'] < row['ma5']:
            signals.append("跌破MA5")
        if row['ma20'] and row['close'] < row['ma20']:
            signals.append("跌破MA20")
        
        if signals:
            return True, "; ".join(signals)
        return False, None
    
    def get_trend(self, df):
        """
        获取趋势方向
        返回: "up", "down", "neutral"
        """
        if len(df) < 20:
            return "neutral"

        row = df.iloc[-1]
        prev_row = df.iloc[-5]

        # 简单趋势判断
        if row['close'] > row['ma20'] and row['ma5'] > row['ma20']:
            return "up"
        elif row['close'] < row['ma20'] and row['ma5'] < row['ma20']:
            return "down"
        return "neutral"

    def get_market_drop(self, helper, index_symbol="000001", date=None):
        """获取大盘今日跌幅
        index_symbol: 指数代码（默认上证指数）
        返回: 大盘跌幅百分比
        """
        try:
            df = helper.get_history_kline(index_symbol, days=5, end_date=date)
            if df is None or df.empty or len(df) < 2:
                return 0.0

            # 计算今日跌幅
            prev_close = df['close'].iloc[-2]
            curr_close = df['close'].iloc[-1]

            if prev_close <= 0:
                return 0.0

            drop_pct = (curr_close - prev_close) / prev_close * 100
            return drop_pct
        except Exception:
            return 0.0

    def calculate_confidence(self, df):
        """根据指标计算机票信心度
        返回: "high", "medium", "low"
        """
        if len(df) < 20:
            return "medium"

        row = df.iloc[-1]
        signals = []

        # 均线多头排列 - 高信心
        if row['ma5'] and row['ma10'] and row['ma20']:
            if row['ma5'] > row['ma10'] > row['ma20']:
                signals.append(2)  # 强信号

        # MACD金叉 - 中等信心
        if len(df) >= 2:
            if df['macd'].iloc[-2] < df['signal'].iloc[-2] and row['macd'] > row['signal']:
                signals.append(1)

        # RSI适中 - 中等信心
        if 40 < row['rsi'] < 60:
            signals.append(1)

        # KDJ金叉超卖 - 高信心
        if len(df) >= 2:
            if df['kdj_k'].iloc[-2] < 30 and row['kdj_k'] > 30:
                signals.append(2)

        # 成交量放大 - 确认信号
        if len(df) >= 5:
            avg_vol = df['volume'].iloc[-5:-1].mean()
            if avg_vol > 0 and row['volume'] > avg_vol * 1.2:
                signals.append(1)

        # 综合评分
        score = sum(signals)

        if score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"