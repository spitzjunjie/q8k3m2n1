# -*- coding: utf-8 -*-
"""
多时间框架共振策略
日线、周线、月线趋势同向上时买入
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy


class MultiTimeframeStrategy(EventStrategy):
    """多时间框架共振策略基类"""

    def __init__(self, name="多时间框架共振", category="技术共振"):
        super().__init__(name, category)

    def get_universe(self, helper, sample=80):
        """获取股票池（沪深300，按市值降序抽样）"""
        stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
        return stocks[:sample] if len(stocks) > sample else stocks

    def calculate_daily_ma(self, df):
        """计算日线均线指标 MA5/MA20"""
        df = df.copy()
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        return df

    def calculate_weekly_ma(self, df_daily):
        """计算周线均线指标 MA10/MA50"""
        df = df_daily.copy()
        df['date'] = pd.to_datetime(df['date'])
        df_weekly = df.resample('W', on='date').agg({
            'close': 'last',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'volume': 'sum'
        }).dropna()
        df_weekly['ma10'] = df_weekly['close'].rolling(10).mean()
        df_weekly['ma50'] = df_weekly['close'].rolling(50).mean()
        return df_weekly

    def calculate_monthly_ma(self, df_daily):
        """计算月线均线指标 MA20/MA60"""
        df = df_daily.copy()
        df['date'] = pd.to_datetime(df['date'])
        df_monthly = df.resample('M', on='date').agg({
            'close': 'last',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'volume': 'sum'
        }).dropna()
        df_monthly['ma20'] = df_monthly['close'].rolling(20).mean()
        df_monthly['ma60'] = df_monthly['close'].rolling(60).mean()
        return df_monthly

    def get_description(self):
        return "日线、周线、月线趋势同向上时买入，多周期共振确认"

    def detect_events(self, helper, date=None):
        """检测多时间框架共振信号"""
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:60]  # 样本量适中

        for symbol in sample_symbols:
            try:
                # 获取日线数据（需要更长时间用于计算月线）
                df_daily = helper.get_history_kline(symbol, days=300)
                if df_daily is None or len(df_daily) < 120:
                    continue

                # 计算各周期均线
                df_daily = self.calculate_daily_ma(df_daily)
                df_weekly = self.calculate_weekly_ma(df_daily)
                df_monthly = self.calculate_monthly_ma(df_daily)

                # 获取最新数据
                daily_latest = df_daily.iloc[-1]
                weekly_latest = df_weekly.iloc[-1] if len(df_weekly) > 0 else None
                monthly_latest = df_monthly.iloc[-1] if len(df_monthly) > 0 else None

                if weekly_latest is None or monthly_latest is None:
                    continue

                # 多周期共振条件：
                # 1. 日线：MA5 > MA20（短中期多头）
                # 2. 周线：MA10 > MA50（中期多头）
                # 3. 月线：MA20 > MA60（长期多头）
                daily_bullish = daily_latest['ma5'] > daily_latest['ma20']
                weekly_bullish = weekly_latest['ma10'] > weekly_latest['ma50']
                monthly_bullish = monthly_latest['ma20'] > monthly_latest['ma60']

                if daily_bullish and weekly_bullish and monthly_bullish:
                    # 计算各周期强度
                    daily_strength = (daily_latest['ma5'] / daily_latest['ma20'] - 1) * 100
                    weekly_strength = (weekly_latest['ma10'] / weekly_latest['ma50'] - 1) * 100
                    monthly_strength = (monthly_latest['ma20'] / monthly_latest['ma60'] - 1) * 100
                    total_strength = daily_strength + weekly_strength + monthly_strength

                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"三周期共振强势，日+{daily_strength:.1f}%/周+{weekly_strength:.1f}%/月+{monthly_strength:.1f}%"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results
