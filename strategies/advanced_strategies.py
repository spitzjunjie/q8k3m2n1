# -*- coding: utf-8 -*-
"""
高级策略：行业轮动、资金流、超跌反弹等
"""

import pandas as pd
import numpy as np
from strategies.base import BaseStrategy


class IndustryMomentumStrategy(BaseStrategy):
    """行业动量策略 - 追强势行业"""

    def __init__(self):
        super().__init__("行业动量", "轮动策略")
        self.top_industries = []

    def get_description(self):
        return "追强势行业：选取近20日涨幅最大的行业中的龙头股"

    def select_stocks(self, helper, date=None):
        """选择近20日涨幅最大的行业中的龙头股"""
        results = []

        # 行业分类（简化版）
        industry_leaders = {
            '科技': ['600519', '000858', '002475'],  # 茅台、五粮液、立讯
            '新能源': ['300750', '002594', '688012'],  # 宁德、比亚迪、中微
            '医药': ['600276', '000538', '300760'],  # 恒瑞、云南白药、迈瑞
            '消费': ['000568', '603288', '600887'],  # 泸州老窖、海天、伊利
        }

        best_industry = None
        best_return = -999

        # 简单模拟：选择成交额最大的行业
        for industry, stocks in industry_leaders.items():
            try:
                total_return = 0
                count = 0
                for sym in stocks[:3]:
                    kline = helper.get_history_kline(sym, days=20)
                    if not kline.empty and len(kline) >= 5:
                        ret = (kline['close'].iloc[-1] / kline['close'].iloc[0] - 1) * 100
                        total_return += ret
                        count += 1
                if count > 0:
                    avg_return = total_return / count
                    if avg_return > best_return:
                        best_return = avg_return
                        best_industry = industry
            except:
                continue

        if best_industry and best_industry in industry_leaders:
            for sym in industry_leaders[best_industry][:3]:
                try:
                    kline = helper.get_history_kline(sym, days=20)
                    if not kline.empty:
                        results.append({
                            'symbol': sym,
                            'name': sym,
                            'reason': f"行业动量：{best_industry}强势"
                        })
                except:
                    continue

        return results[:3]


class SouthboundFlowStrategy(BaseStrategy):
    """南向资金策略 - 跟随港资"""

    def __init__(self):
        super().__init__("南向资金", "资金流策略")

    def get_description(self):
        return "南向资金（港资）持续买入的A股"

    def select_stocks(self, helper, date=None):
        """选择北向资金持续净买入的股票"""
        results = []

        # 模拟北向重仓股
        north_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
        ]

        for stock in north_stocks:
            try:
                # 简单趋势确认
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if not kline.empty and len(kline) >= 10:
                    ma10 = kline['close'].rolling(10).mean().iloc[-1]
                    ma20 = kline['close'].rolling(20).mean().iloc[-1]
                    if kline['close'].iloc[-1] > ma10 > ma20:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': "南向资金重仓，趋势向上"
                        })
                if len(results) >= 5:
                    break
            except:
                continue

        return results


class OversoldReboundStrategy(BaseStrategy):
    """超跌反弹策略 - 捕捉错杀"""

    def __init__(self):
        super().__init__("超跌反弹", "逆向策略")

    def get_description(self):
        return "连续下跌后企稳：RSI<30超卖后反弹信号"

    def select_stocks(self, helper, date=None):
        """选择超跌后企稳的股票"""
        results = []

        # 模拟超跌股池
        oversold_stocks = [
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '002236', 'name': '大华股份'},
            {'symbol': '002236', 'name': '大华股份'},
            {'symbol': '300059', 'name': '东方财富'},
        ]

        for stock in oversold_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 15:
                    continue

                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]

                # RSI从超卖区域反弹
                if 30 < current_rsi < 50:
                    # 价格企稳：近3日收盘价高于开盘价
                    recent = kline.tail(3)
                    if (recent['close'] > recent['open']).sum() >= 2:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"超跌反弹：RSI={current_rsi:.1f}，企稳信号"
                        })
            except:
                continue

        return results[:5]


class ValueLowPBStrategy(BaseStrategy):
    """低估值策略 - PB历史低位"""

    def __init__(self):
        super().__init__("低PB价值", "价值策略")

    def get_description(self):
        return "市净率PB低于行业平均，处于历史低位"

    def select_stocks(self, helper, date=None):
        """选择低PB的股票"""
        results = []

        # 模拟低PB股票池
        value_stocks = [
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601288', 'name': '农业银行'},
            {'symbol': '601988', 'name': '中国银行'},
            {'symbol': '600016', 'name': '民生银行'},
            {'symbol': '601818', 'name': '光大银行'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]

        for stock in value_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if not kline.empty:
                    # 趋势确认：20日均线向上
                    ma20 = kline['close'].rolling(20).mean()
                    if ma20.iloc[-1] > ma20.iloc[-10]:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': "低PB价值：银行板块估值底部"
                        })
                if len(results) >= 5:
                    break
            except:
                continue

        return results


class EarningsSurpriseStrategy(BaseStrategy):
    """业绩超预期策略"""

    def __init__(self):
        super().__init__("业绩超预期", "事件驱动")

    def get_description(self):
        return "净利润增速超预期：实际>预期10%以上"

    def select_stocks(self, helper, date=None):
        """选择业绩超预期的股票"""
        results = []

        # 模拟业绩超预期股票
        surprise_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '688111', 'name': '金山办公'},
        ]

        for stock in surprise_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if not kline.empty and len(kline) >= 10:
                    # 动量确认：近10日上涨
                    ret_10d = (kline['close'].iloc[-1] / kline['close'].iloc[-10] - 1) * 100
                    if ret_10d > 0:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"业绩超预期：近10日+{ret_10d:.1f}%"
                        })
                if len(results) >= 5:
                    break
            except:
                continue

        return results


class VolumeBreakoutStrategy(BaseStrategy):
    """量价齐升策略"""

    def __init__(self):
        super().__init__("量价齐升", "技术策略")

    def get_description(self):
        return "放量突破：成交量放大2倍+价格突破"

    def select_stocks(self, helper, date=None):
        """选择量价齐升的股票"""
        results = []

        # 模拟热门股池
        breakout_stocks = [
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '600519', 'name': '贵州茅台'},
        ]

        for stock in breakout_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue

                # 计算成交量和价格变化
                vol_ma20 = kline['volume'].rolling(20).mean().iloc[-1]
                vol_today = kline['volume'].iloc[-1]

                # 价格突破
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                price_today = kline['close'].iloc[-1]

                # 放量 + 突破
                if vol_today > vol_ma20 * 2 and price_today > ma20:
                    vol_ratio = vol_today / vol_ma20
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"量价齐升：放量{vol_ratio:.1f}倍，突破MA20"
                    })
            except:
                continue

        return results[:5]
