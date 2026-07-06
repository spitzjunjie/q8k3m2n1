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
        
        # 4. RSI超卖
        if row['rsi'] < 40:
            signals.append(f"RSI超卖({row['rsi']:.1f})")
        
        # 5. 缩量整理后温和放量
        if len(df) >= 10:
            avg_vol = df['volume'].iloc[-10:-1].mean()
            if row['volume'] > avg_vol * 0.8 and row['volume'] < avg_vol * 1.5:
                if row['close'] > df['close'].iloc[-2]:
                    signals.append("温和放量上涨")
        
        # 6. 均线多头排列（买入信号确认）
        if row['ma5'] and row['ma10'] and row['ma20']:
            if row['ma5'] > row['ma10'] > row['ma20']:
                signals.append("均线多头排列")
        
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
        if row['rsi'] > 70:
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


if __name__ == "__main__":
    # 测试
    from data.akshare_helper import AKShareHelper
    
    helper = AKShareHelper()
    df = helper.get_history_kline("000001", days=60)
    
    if not df.empty:
        engine = TimingEngine()
        df = engine.add_indicators(df)
        print(df.tail(5))
        
        buy_signal, reason = engine.check_buy_signals(df)
        print(f"买入信号: {buy_signal}, 原因: {reason}")
        
        sell_signal, reason = engine.check_sell_signals(df, df['close'].iloc[-1] * 0.95)
        print(f"卖出信号: {sell_signal}, 原因: {reason}")
