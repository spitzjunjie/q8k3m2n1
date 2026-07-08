# -*- coding: utf-8 -*-
"""
因子选股策略（真实数据驱动）
所有因子值来自AKShare真实财务/估值/行情数据
"""

import pandas as pd
import numpy as np
from strategies.base import FactorStrategy


class FactorStrategyBase(FactorStrategy):
    """因子策略基类，提供通用选股流程"""

    def get_universe(self, helper, sample=80):
        """获取股票池（沪深300，按市值降序抽样）
        按市值排序确保抽样的是大盘股而非代码最小的股票
        """
        stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
        return stocks[:sample] if len(stocks) > sample else stocks

    def build_result(self, symbols, factor_values, reason_template):
        """构建结果DataFrame
        自动过滤 None 和 NaN 值（数据获取失败的股票不参与排序）
        """
        data = []
        for sym, val in zip(symbols, factor_values):
            if val is None:
                continue
            try:
                if np.isnan(val):
                    continue
            except (TypeError, ValueError):
                continue
            data.append({'symbol': sym, 'name': sym, 'factor_value': float(val)})
        df = pd.DataFrame(data)
        if not df.empty:
            # 优化：从head(30)增加到head(50)，增加可选标的
            df = df.sort_values('factor_value', ascending=False).head(50)
            df['reason'] = df.apply(lambda r: reason_template.format(val=r['factor_value']), axis=1)
        return df

    def calculate_factor(self, helper, date=None):
        """子类实现具体因子计算"""
        raise NotImplementedError


class ROEStrategy(FactorStrategyBase):
    """ROE选股策略 - 真实ROE排名"""

    def __init__(self):
        super().__init__("ROE选股", "盈利因子", "ROE")

    def calculate_factor(self, helper, date=None):
        # 优化：扩大样本池从60到120
        symbols = self.get_universe(helper, sample=120)
        values = []
        for sym in symbols:
            try:
                fin = helper.get_financial_indicator(sym)
                roe = fin.get('roe')
                values.append(roe if roe else None)  # 失败返回None被过滤
            except:
                values.append(None)
        return self.build_result(symbols, values, "ROE={val:.2f}%")


class ProfitGrowthStrategy(FactorStrategyBase):
    """净利润增速策略 - 真实净利润同比增长率"""

    def __init__(self):
        super().__init__("净利润增速", "盈利因子", "净利润增速")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                growth = helper.get_growth_data(sym)
                g = growth.get('profit_growth')
                values.append(g if g else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "净利润增速={val:.2f}%")


class RevenueGrowthStrategy(FactorStrategyBase):
    """营收增长策略 - 真实营收同比增长率"""

    def __init__(self):
        super().__init__("营收增长", "盈利因子", "营收增速")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                growth = helper.get_growth_data(sym)
                g = growth.get('revenue_growth')
                values.append(g if g else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "营收增速={val:.2f}%")


class LowPEStrategy(FactorStrategyBase):
    """低PE策略优化版 - 避免低估值陷阱"""

    def __init__(self):
        super().__init__("低PE", "价值因子", "市盈率")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                fin = helper.get_financial_indicator(sym)
                pe = val.get('pe_ttm', 0)
                roe = fin.get('roe', 0)
                
                # 优化：避免低估值陷阱
                # PE 5-30 + ROE > 0 才有效
                if 5 < pe < 30 and roe > 0:
                    # 用 PEG 修正：PE / 净利润增速
                    growth = helper.get_growth_data(sym)
                    profit_growth = growth.get('profit_growth', 0)
                    if profit_growth and profit_growth > 0:
                        peg = pe / profit_growth
                        # PEG < 1.5 是好价格
                        score = -peg if peg < 1.5 else -9999
                    else:
                        score = -pe  # 用PE原始值排序
                else:
                    score = -9999
                values.append(score)
            except:
                values.append(-9999)
        return self.build_result(symbols, values, "PE={val:.2f}, 排除陷阱")


class LowPBStrategy(FactorStrategyBase):
    """低PB策略 - 真实市净率，选最低的"""

    def __init__(self):
        super().__init__("低PB", "价值因子", "市净率")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                pb = val.get('pb', 0)
                values.append(-pb if pb > 0 else -9999)
            except:
                values.append(-9999)
        return self.build_result(symbols, values, "PB={val:.2f}")


class PSRStrategy(FactorStrategyBase):
    """PSR低估值策略 - 真实市销率，选最低的"""

    def __init__(self):
        super().__init__("PSR低估值", "价值因子", "市销率")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                ps = val.get('ps_ttm', 0)
                values.append(-ps if ps > 0 else -9999)
            except:
                values.append(-9999)
        return self.build_result(symbols, values, "PS={val:.2f}")


class LowValuationStrategy(FactorStrategyBase):
    """低估值修复策略 - PB历史分位数低位"""

    def __init__(self):
        super().__init__("低估值修复", "价值因子", "PB分位数")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                # 简化：用PB绝对值排序，越低越"低估"
                pb = val.get('pb', 0)
                values.append(-pb if 0 < pb < 10 else -9999)
            except:
                values.append(-9999)
        return self.build_result(symbols, values, "PB修复空间={val:.2f}")


class CashFlowQualityStrategy(FactorStrategyBase):
    """现金流质量策略 - 经营现金流/净利润"""

    def __init__(self):
        super().__init__("现金流质量", "质量因子", "现金流质量")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=50)
        values = []
        for sym in symbols:
            try:
                cf = helper.get_cash_flow(sym)
                q = cf.get('cf_quality')
                values.append(q if q else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "现金流质量={val:.2f}")


class HighROICStrategy(FactorStrategyBase):
    """高ROIC策略 - 真实投入资本回报率"""

    def __init__(self):
        super().__init__("高ROIC", "质量因子", "ROIC")

    def calculate_factor(self, helper, date=None):
        # 优化：扩大样本池从60到120
        symbols = self.get_universe(helper, sample=120)
        values = []
        for sym in symbols:
            try:
                fin = helper.get_financial_indicator(sym)
                roic = fin.get('roic')
                values.append(roic if roic else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "ROIC={val:.2f}%")


class LowDebtStrategy(FactorStrategyBase):
    """低负债率策略 - 真实资产负债率，选最低的"""

    def __init__(self):
        super().__init__("低负债率", "质量因子", "资产负债率")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                fin = helper.get_financial_indicator(sym)
                debt = fin.get('debt_ratio', 100)
                # 低负债：用负值排序，负债越低越靠前
                values.append(-debt if debt > 0 else -100)
            except:
                values.append(-100)
        return self.build_result(symbols, values, "资产负债率={val:.2f}%")


class HighDividendStrategy(FactorStrategyBase):
    """高股息策略 - 真实股息率"""

    def __init__(self):
        super().__init__("高股息", "红利因子", "股息率")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=80)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                dv = val.get('dv_ttm')
                values.append(dv if dv else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "股息率={val:.2f}%")


class DividendLowVolStrategy(FactorStrategyBase):
    """红利低波策略 - 高股息 + 低波动"""

    def __init__(self):
        super().__init__("红利低波", "红利因子", "股息率/波动率")

    def calculate_factor(self, helper, date=None):
        # 优化：扩大样本池从60到120
        symbols = self.get_universe(helper, sample=120)
        values = []
        for sym in symbols:
            try:
                val = helper.get_valuation_data(sym)
                dv = val.get('dv_ttm')
                if not dv:
                    values.append(None)
                    continue
                # 计算20日波动率（优化：使用更稳定的波动率计算）
                kline = helper.get_history_kline(sym, days=30, end_date=date)
                if not kline.empty and len(kline) > 5:
                    returns = kline['close'].pct_change().dropna()
                    if len(returns) > 3:
                        vol = returns.std() * np.sqrt(252)
                        # 红利低波 = 股息率 / 波动率
                        values.append(dv / vol if vol > 0 else None)
                    else:
                        values.append(None)
                else:
                    values.append(None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "红利低波={val:.2f}")


class MomentumReversalStrategy(FactorStrategyBase):
    """动量反转策略 - 前期跌幅大 + 基本面好"""

    def __init__(self):
        super().__init__("动量反转", "动量因子", "反转动量")

    def calculate_factor(self, helper, date=None):
        # 优化：扩大样本池从60到120，放宽ROE要求从5%到3%
        symbols = self.get_universe(helper, sample=120)
        values = []
        for sym in symbols:
            try:
                kline = helper.get_history_kline(sym, days=30, end_date=date)
                if not kline.empty and len(kline) > 10:
                    # 过去20日收益率（反转：跌幅大的得分高）
                    ret_20d = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100
                    # 优化：放宽ROE要求从5%到3%
                    fin = helper.get_financial_indicator(sym)
                    roe = fin.get('roe', 0)
                    if roe > 3:  # 原来是 roe > 5
                        # 反转得分 = -收益率（跌幅越大得分越高）
                        values.append(-ret_20d)
                    else:
                        values.append(None)
                else:
                    values.append(None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "反转动量={val:.2f}")


class TrendMomentumStrategy(FactorStrategyBase):
    """趋势动量策略 - 60日动量因子"""

    def __init__(self):
        super().__init__("趋势动量", "动量因子", "60日动量")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                kline = helper.get_history_kline(sym, days=90, end_date=date)
                if not kline.empty and len(kline) > 60:
                    # 60日动量
                    ret_60d = (kline['close'].iloc[-1] / kline['close'].iloc[-60] - 1) * 100
                    values.append(ret_60d)
                else:
                    values.append(None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "60日动量={val:.2f}%")


class NorthHeavyStrategy(FactorStrategyBase):
    """北向重仓策略 - 真实北向资金持股比例"""

    def __init__(self):
        super().__init__("北向重仓", "资金因子", "北向持股比例")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                north = helper.get_north_holding(sym)
                r = north.get('hold_ratio')
                values.append(r if r else None)
            except:
                values.append(None)
        return self.build_result(symbols, values, "北向持股={val:.2f}%")


class InstitutionHoldingStrategy(FactorStrategyBase):
    """机构持仓策略 - 基金重仓股（用北向资金近似）"""

    def __init__(self):
        super().__init__("机构持仓", "资金因子", "机构持股")

    def calculate_factor(self, helper, date=None):
        symbols = self.get_universe(helper, sample=60)
        values = []
        for sym in symbols:
            try:
                # 用北向资金持股比例近似机构关注度
                north = helper.get_north_holding(sym)
                hold = north.get('hold_ratio')
                # 叠加股息率作为机构偏好
                val = helper.get_valuation_data(sym)
                dv = val.get('dv_ttm')
                if hold is None or dv is None:
                    values.append(None)
                else:
                    values.append(hold + dv * 0.5)
            except:
                values.append(None)
        return self.build_result(symbols, values, "机构关注度={val:.2f}")
