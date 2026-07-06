# -*- coding: utf-8 -*-
"""
特殊策略：紫苏叶策略、趋势策略（真实数据驱动）
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy, FactorStrategy


class AISupplyChainStrategy(EventStrategy):
    """AI供应链紫苏叶策略 - 真实股票池 + 趋势确认"""

    def __init__(self):
        super().__init__("AI供应链紫苏叶", "紫苏叶")

    def get_description(self):
        return "找AI产业链卡脖子环节：磷化铟/谐波减速器/MLCC/半导体设备"

    def detect_events(self, helper, date=None):
        # AI供应链关键环节的真实A股标的
        supply_chain_stocks = [
            {'symbol': '002371', 'name': '北方华创', 'segment': '半导体设备-刻蚀机'},
            {'symbol': '688012', 'name': '中微公司', 'segment': '半导体设备-MOCVD'},
            {'symbol': '002428', 'name': '云南锗业', 'segment': '磷化铟衬底'},
            {'symbol': '300408', 'name': '三环集团', 'segment': 'MLCC电子元件'},
            {'symbol': '688187', 'name': '时代电气', 'segment': '功率半导体'},
            {'symbol': '688256', 'name': '寒武纪', 'segment': 'AI芯片'},
            {'symbol': '688008', 'name': '澜起科技', 'segment': '内存接口芯片'},
            {'symbol': '688099', 'name': '晶晨股份', 'segment': '多媒体芯片'},
            {'symbol': '688521', 'name': '芯原股份', 'segment': 'RISC-V IP核'},
            {'symbol': '688396', 'name': '华润微', 'segment': '半导体功率器件'},
        ]
        results = []
        for stock in supply_chain_stocks:
            try:
                # 用趋势确认：20日均线向上
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if not kline.empty and len(kline) > 20:
                    ma20 = kline['close'].rolling(20).mean()
                    if ma20.iloc[-1] > ma20.iloc[-5]:  # 20日均线上行
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"{stock['segment']}，20日均线上行"
                        })
                if len(results) >= 5:
                    break
            except:
                continue
        return results


class LocalizationStrategy(EventStrategy):
    """国产替代紫苏叶策略 - 真实股票池 + 基本面确认"""

    def __init__(self):
        super().__init__("国产替代", "紫苏叶")

    def get_description(self):
        return "半导体设备/材料国产替代，真实龙头股+基本面确认"

    def detect_events(self, helper, date=None):
        localization_stocks = [
            {'symbol': '688012', 'name': '中微公司', 'segment': '半导体设备'},
            {'symbol': '002371', 'name': '北方华创', 'segment': '半导体设备'},
            {'symbol': '688981', 'name': '中芯国际', 'segment': '晶圆代工'},
            {'symbol': '688396', 'name': '华润微', 'segment': '功率半导体'},
            {'symbol': '688008', 'name': '澜起科技', 'segment': '内存接口芯片'},
            {'symbol': '688256', 'name': '寒武纪', 'segment': 'AI芯片'},
            {'symbol': '300751', 'name': '迈为股份', 'segment': '光伏设备'},
            {'symbol': '688116', 'name': '天奈科技', 'segment': '碳纳米管'},
            {'symbol': '688005', 'name': '容百科技', 'segment': '正极材料'},
            {'symbol': '002049', 'name': '紫光国微', 'segment': '特种芯片'},
        ]
        results = []
        for stock in localization_stocks:
            try:
                # 基本面确认：营收增速 > 10%
                growth = helper.get_growth_data(stock['symbol'])
                revenue_growth = growth.get('revenue_growth', 0)
                if revenue_growth > 10:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"{stock['segment']}国产替代，营收增速={revenue_growth:.1f}%"
                    })
                if len(results) >= 5:
                    break
            except:
                continue
        return results


class MaBreakStrategy(FactorStrategy):
    """均线多头排列策略 v1.1.0 - 优化：增加ma60确认+20日动量过滤"""

    def __init__(self):
        super().__init__("均线多头排列", "趋势策略", "均线多头")

    def get_description(self):
        return "5MA>10MA>20MA>MA60，趋势更强时买入"

    def calculate_factor(self, helper, date=None):
        stocks = helper.get_stock_pool("hs300")[:80]
        data = []
        for sym in stocks:
            try:
                kline = helper.get_history_kline(sym, days=60)  # 增加获取天数
                if kline.empty or len(kline) < 30:
                    continue
                ma5 = kline['close'].rolling(5).mean().iloc[-1]
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                ma60 = kline['close'].rolling(60).mean().iloc[-1]
                # 优化：均线多头排列 + ma60上升 + 20日动量正
                ma60_rising = ma60 > kline['close'].rolling(60).mean().iloc[-5]  # ma60向上
                momentum_20d = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100 if len(kline) >= 20 else 0
                # 原条件 + ma60确认 + 动量正
                if ma5 > ma10 > ma20 and ma60_rising and momentum_20d > 0:
                    # 因子值 = 收盘价相对MA20的偏离度
                    score = (kline['close'].iloc[-1] / ma20 - 1) * 100
                    data.append({'symbol': sym, 'name': sym, 'factor_value': score})
            except:
                continue
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('factor_value', ascending=False).head(30)
            df['reason'] = df.apply(lambda r: f"均线多头，偏离MA20={r['factor_value']:.2f}%", axis=1)
        return df


class MultiPeriodStrategy(FactorStrategy):
    """多周期共振策略 v1.1.0 - 优化：增加20日动量确认"""

    def __init__(self):
        super().__init__("多周期共振", "趋势策略", "多周期共振")

    def get_description(self):
        return "日线和周线趋势同向+20日动量为正"

    def calculate_factor(self, helper, date=None):
        stocks = helper.get_stock_pool("hs300")[:60]
        data = []
        for sym in stocks:
            try:
                # 日线
                daily = helper.get_history_kline(sym, days=90)  # 增加天数以计算20日动量
                if daily.empty or len(daily) < 30:
                    continue
                # 周线（简化：用20日和5日均线模拟）
                ma5 = daily['close'].rolling(5).mean().iloc[-1]
                ma20 = daily['close'].rolling(20).mean().iloc[-1]
                ma10 = daily['close'].rolling(10).mean().iloc[-1]

                # 日线趋势：ma5 > ma10
                daily_bull = ma5 > ma10
                # 周线趋势：ma10 > ma20（近似周线）
                weekly_bull = ma10 > ma20
                # 优化：增加20日动量确认
                momentum_20d = (daily['close'].iloc[-1] / daily['close'].iloc[-20] - 1) * 100 if len(daily) >= 20 else 0

                if daily_bull and weekly_bull and momentum_20d > 0:  # 新增动量过滤
                    # 共振强度
                    score = (ma5 / ma20 - 1) * 100
                    data.append({'symbol': sym, 'name': sym, 'factor_value': score})
            except:
                continue
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('factor_value', ascending=False).head(30)
            df['reason'] = df.apply(lambda r: f"多周期共振，趋势强度={r['factor_value']:.2f}%", axis=1)
        return df


class MultiFactorStrategy(FactorStrategy):
    """多因子综合策略 - 真实因子等权组合"""

    def __init__(self):
        super().__init__("多因子综合", "综合", "多因子综合得分")
        self.factor_name = "多因子"

    def get_description(self):
        return "等权组合ROE+低PE+动量+北向，综合评分"

    def calculate_factor(self, helper, date=None):
        stocks = helper.get_stock_pool("hs300")[:50]
        data = []
        for sym in stocks:
            try:
                # 综合评分：ROE + 低PE + 60日动量 + 北向持股
                fin = helper.get_financial_indicator(sym)
                val = helper.get_valuation_data(sym)
                north = helper.get_north_holding(sym)
                kline = helper.get_history_kline(sym, days=90)

                roe = fin.get('roe', 0)
                pe = val.get('pe_ttm', 100)
                north_ratio = north.get('hold_ratio', 0)

                if kline is not None and not kline.empty and len(kline) > 60:
                    ret_60d = (kline['close'].iloc[-1] / kline['close'].iloc[-60] - 1) * 100
                else:
                    ret_60d = 0

                # 综合得分（归一化）
                score = 0
                score += min(roe / 20, 1) * 25  # ROE贡献25分
                score += min(20 / max(pe, 1), 1) * 25  # 低PE贡献25分
                score += min(ret_60d / 20, 1) * 25  # 动量贡献25分
                score += min(north_ratio / 5, 1) * 25  # 北向贡献25分

                if score > 40:
                    data.append({'symbol': sym, 'name': sym, 'factor_value': score})
            except:
                continue
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('factor_value', ascending=False).head(30)
            df['reason'] = df.apply(
                lambda r: f"综合评分={r['factor_value']:.1f}", axis=1)
        return df
