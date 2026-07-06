# -*- coding: utf-8 -*-
"""
事件驱动策略（真实事件检测）
所有信号基于真实市场事件数据
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy


class EventStrategyBase(EventStrategy):
    """事件策略基类"""

    def __init__(self, name, category="事件驱动", **kwargs):
        super().__init__(name, category, **kwargs)

    def get_universe(self, helper, sample=80):
        stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
        return stocks[:sample] if len(stocks) > sample else stocks


class LimitUpCallbackStrategy(EventStrategyBase):
    """首板回调策略 - 真实涨停板后回踩均线"""

    def __init__(self):
        super().__init__("首板回调")

    def get_description(self):
        return "涨停后回踩MA10均线，捕捉二次启动"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        results = []
        for sym in symbols:
            try:
                kline = helper.get_history_kline(sym, days=30)
                if kline.empty or len(kline) < 15:
                    continue
                # 检测10日内是否有涨停（涨幅>9.5%）
                recent = kline.tail(10)
                limit_up = recent[(recent['close'] / recent['close'].shift(1) - 1) > 0.095]
                if not limit_up.empty:
                    # 当前价格回踩MA10
                    ma10 = kline['close'].rolling(10).mean().iloc[-1]
                    current = kline['close'].iloc[-1]
                    # 回踩条件：当前价在MA10附近（±3%）
                    if 0.97 * ma10 < current < 1.03 * ma10:
                        results.append({
                            'symbol': sym, 'name': sym,
                            'reason': f"涨停后回踩MA10，MA10={ma10:.2f}"
                        })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class STRemoveStrategy(EventStrategyBase):
    """ST摘帽潜伏策略 - 筛选ST股中基本面改善的"""

    def __init__(self):
        super().__init__("ST摘帽潜伏")

    def get_description(self):
        return "筛选ST股中扭亏预期，潜伏摘帽行情"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        results = []
        for sym in symbols:
            try:
                # 检查是否为ST股（名称含ST）
                # 简化：用财务指标判断是否处于困境反转
                fin = helper.get_financial_indicator(sym)
                growth = helper.get_growth_data(sym)
                # 条件：过去亏损但近期净利润增速转正
                profit_growth = growth.get('profit_growth', 0)
                roe = fin.get('roe', 0)
                if profit_growth > 50 and -5 < roe < 5:
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"困境反转，净利润增速={profit_growth:.1f}%"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class ExecutiveBuyStrategy(EventStrategyBase):
    """高管增持策略 v1.1.0 - 优化：过滤N/A数据+增加变动比例排序"""

    def __init__(self):
        super().__init__("高管增持")

    def get_description(self):
        return "高管增持信号（变动比例>0），捕捉内部人看好"

    def detect_events(self, helper, date=None):
        try:
            df = helper.get_executive_trading()
            if df.empty:
                return []
            # 优化：只选择变动比例>0且非N/A的记录，并按变动比例排序
            if '变动比例' in df.columns:
                # 过滤N/A值
                df = df[df['变动比例'].notna()]
                # 只选择变动比例>0的
                buy_df = df[df['变动比例'] > 0].sort_values('变动比例', ascending=False).head(20)
            else:
                buy_df = df.head(20)
            results = []
            for _, row in buy_df.iterrows():
                symbol = str(row.get('代码', row.get('股票代码', '')))
                ratio = row.get('变动比例', 'N/A')
                # 过滤无效symbol和N/A的变动比例
                if symbol and ratio != 'N/A':
                    try:
                        ratio_val = float(ratio) if ratio else 0
                        if ratio_val > 0:
                            results.append({
                                'symbol': symbol,
                                'name': row.get('名称', row.get('股票简称', symbol)),
                                'reason': f"高管增持，变动比例={ratio_val:.2f}%"
                            })
                    except (ValueError, TypeError):
                        continue
                if len(results) >= 10:
                    break
            return results
        except Exception as e:
            print(f"高管增持策略失败: {e}")
            return []


class EarningsSurpriseStrategy(EventStrategyBase):
    """业绩超预期策略 - 财报数据 vs 市场预期"""

    def __init__(self):
        super().__init__("业绩超预期")

    def get_description(self):
        return "财报数据超市场预期，捕捉业绩行情"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        results = []
        for sym in symbols:
            try:
                growth = helper.get_growth_data(sym)
                # 简化：净利润增速 > 30% 视为超预期
                profit_growth = growth.get('profit_growth', 0)
                if profit_growth > 30:
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"业绩超预期，净利润增速={profit_growth:.1f}%"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class AnalystUpgradeStrategy(EventStrategyBase):
    """分析师上调策略 - 真实分析师评级"""

    def __init__(self):
        super().__init__("分析师上调")

    def get_description(self):
        return "分析师评级上调，捕捉机构看好"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=50)
        results = []
        for sym in symbols:
            try:
                rating = helper.get_analyst_rating(sym)
                if rating and rating.get('rating'):
                    # 简化：评级为"买入"或"增持"
                    if '买入' in str(rating.get('rating', '')) or '增持' in str(rating.get('rating', '')):
                        results.append({
                            'symbol': sym, 'name': sym,
                            'reason': f"分析师{rating.get('rating')}，机构={rating.get('institution', '')}"
                        })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class NorthFlowStrategy(EventStrategyBase):
    """北向资金跟投策略 - 真实北向资金持股"""

    def __init__(self):
        super().__init__("北向资金跟投")

    def get_description(self):
        return "北向资金持续净买入，跟投外资"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        results = []
        for sym in symbols:
            try:
                north = helper.get_north_holding(sym)
                hold_ratio = north.get('hold_ratio', 0)
                # 北向持股比例 > 3% 视为重仓
                if hold_ratio > 3:
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"北向持股={hold_ratio:.2f}%"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class MomentumReversalStrategy(EventStrategyBase):
    """动量反转策略 - 真实跌幅 + 基本面好"""

    def __init__(self):
        super().__init__("动量反转")

    def get_description(self):
        return "前期跌幅大但基本面好，捕捉反弹"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        results = []
        for sym in symbols:
            try:
                kline = helper.get_history_kline(sym, days=30)
                if kline.empty or len(kline) < 20:
                    continue
                # 过去20日跌幅
                ret_20d = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100
                # 基本面过滤
                fin = helper.get_financial_indicator(sym)
                roe = fin.get('roe', 0)
                # 跌幅>5% 且 ROE>8%（被错杀的好公司）
                if ret_20d < -5 and roe > 8:
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"20日跌幅{ret_20d:.1f}%，ROE={roe:.1f}%"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class TrendMomentumStrategy(EventStrategyBase):
    """趋势动量策略 v1.1.0 - 优化：降低动量阈值+增加均线多头确认"""

    def __init__(self):
        super().__init__("趋势动量")

    def get_description(self):
        return "60日动量>5%且均线多头，捕捉趋势延续"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        results = []
        for sym in symbols:
            try:
                kline = helper.get_history_kline(sym, days=90)
                if kline.empty or len(kline) < 60:
                    continue
                # 60日动量
                ret_60d = (kline['close'].iloc[-1] / kline['close'].iloc[-60] - 1) * 100
                # 优化：降低阈值从10%到5%，增加均线多头确认
                ma5 = kline['close'].rolling(5).mean().iloc[-1]
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                ma_bull = ma5 > ma10 > ma20  # 均线多头
                # 原条件：60日涨幅>10% -> 优化：60日涨幅>5% + 均线多头
                if ret_60d > 5 and ma_bull:
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"60日涨幅{ret_60d:.1f}%，均线多头"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results


class MultiFactorStrategy(EventStrategyBase):
    """多因子综合策略 - 组合多个真实因子"""

    def __init__(self):
        super().__init__("多因子综合")

    def get_description(self):
        return "等权组合ROE+低PE+动量+北向，综合评分"

    def detect_events(self, helper, date=None):
        symbols = self.get_universe(helper, sample=50)
        results = []
        for sym in symbols:
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

                if score > 50:  # 综合分>50才入选
                    results.append({
                        'symbol': sym, 'name': sym,
                        'reason': f"综合评分={score:.1f}（ROE={roe:.1f}/PE={pe:.1f}/动量={ret_60d:.1f}/北向={north_ratio:.1f}）"
                    })
                if len(results) >= 10:
                    break
            except:
                continue
        return results
