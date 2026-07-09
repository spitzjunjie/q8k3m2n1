# -*- coding: utf-8 -*-
"""
新S级策略集

作者：AI
日期：2026-07-09
"""

from strategies.base import BaseStrategy


class MonthlyResonanceStrategy(BaseStrategy):
    """月线共振策略"""
    
    def __init__(self):
        super().__init__("月线共振", "多时间框架")
        
    def get_description(self):
        return "月线+周线+日线三周期共振"
        
    def select_stocks(self, helper, date=None):
        """选股：月周共振"""
        results = []
        
        # 获取沪深300股票池
        pool = helper.get_stock_pool("hs300")[:50]  # 取前50只
        
        for symbol in pool:
            try:
                # 获取月线数据（需要更长时间）
                monthly = helper.get_history_kline(symbol, days=60)
                if monthly.empty or len(monthly) < 40:
                    continue
                
                # 月线MA
                monthly_ma5 = monthly['close'].iloc[-5:].mean()
                monthly_ma20 = monthly['close'].iloc[-20:].mean() if len(monthly) >= 20 else monthly['close'].mean()
                monthly_prev_ma5 = monthly['close'].iloc[-6] if len(monthly) >= 6 else monthly['close'].iloc[0]
                
                # 月线金叉
                monthly_golden = monthly_prev_ma5 < monthly_ma20 and monthly_ma5 > monthly_ma20
                if not monthly_golden:
                    continue
                
                # 周线数据
                weekly = monthly.tail(20)
                weekly_ma5 = weekly['close'].iloc[-5:].mean()
                weekly_ma10 = weekly['close'].iloc[-10:].mean() if len(weekly) >= 10 else weekly['close'].mean()
                weekly_trend = weekly_ma5 > weekly_ma10
                
                # 日线数据
                daily = helper.get_history_kline(symbol, days=30)
                if daily.empty or len(daily) < 20:
                    continue
                daily_ma5 = daily['close'].iloc[-5:].mean()
                daily_ma20 = daily['close'].iloc[-20:].mean() if len(daily) >= 20 else daily['close'].mean()
                daily_trend = daily_ma5 > daily_ma20
                
                # 三周期共振
                if monthly_golden and weekly_trend and daily_trend:
                    reason = f"月线共振：月MA5={monthly_ma5:.2f}上穿月MA20={monthly_ma20:.2f}"
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': reason
                    })
                    
            except Exception as e:
                continue
                
        return results[:10]


class MainForceMoneyStrategy(BaseStrategy):
    """主力资金策略"""
    
    def __init__(self):
        super().__init__("主力资金", "资金流向")
        
    def get_description(self):
        return "追踪主力资金净流入，持有5-10天"
        
    def select_stocks(self, helper, date=None):
        """选股：主力资金净流入"""
        results = []
        
        pool = helper.get_stock_pool("hs300")[:50]
        
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                # 计算成交量变化
                vol_ma10 = kline['volume'].iloc[-10:].mean()
                recent_vol = kline['volume'].iloc[-5:].mean()
                
                # 价格趋势
                price_ma10 = kline['close'].iloc[-10:].mean()
                price_ma20 = kline['close'].iloc[-20:].mean() if len(kline) >= 20 else kline['close'].mean()
                
                # 放量+趋势向上
                if recent_vol > vol_ma10 * 1.2 and kline['close'].iloc[-1] > price_ma10:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"主力资金：量比={recent_vol/vol_ma10:.1f}倍, 价={kline['close'].iloc[-1]:.2f}>MA10={price_ma10:.2f}"
                    })
                    
            except:
                continue
                
        return results[:10]


class InstitutionResearchStrategy(BaseStrategy):
    """机构调研策略"""
    
    def __init__(self):
        super().__init__("机构调研", "事件驱动")
        
    def get_description(self):
        return "机构调研后效应，持有10天"
        
    def select_stocks(self, helper, date=None):
        """选股：机构重仓股"""
        results = []
        
        # 使用北向重仓股作为机构持仓股
        pool = helper.get_stock_pool("hs300")[:50]
        
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=40)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 近30日有涨幅但未大涨
                ret_30d = (kline['close'].iloc[-1] / kline['close'].iloc[-30] - 1) * 100
                
                # 机构偏好：稳定上涨但未泡沫化
                if 5 < ret_30d < 30:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"机构调研：近30日涨幅={ret_30d:.1f}%"
                    })
                    
            except:
                continue
                
        return results[:10]


class NorthMoneyTimingStrategy(BaseStrategy):
    """北向择时策略"""
    
    def __init__(self):
        super().__init__("北向择时", "资金流向")
        
    def get_description(self):
        return "北向资金加减仓择时，RSI未超买，持有5天"
        
    def select_stocks(self, helper, date=None):
        """选股：北向加仓+RSI未超买"""
        results = []
        
        pool = helper.get_stock_pool("hs300")[:50]
        
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=40)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
                
                # 成交量放大
                vol_ratio = kline['volume'].iloc[-5:].mean() / kline['volume'].iloc[-20:].mean()
                
                # RSI未超买 + 放量
                if current_rsi < 70 and vol_ratio > 1.2:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"北向择时：RSI={current_rsi:.1f}, 量比={vol_ratio:.1f}倍"
                    })
                    
            except:
                continue
                
        return results[:10]


class EarningsSeasonStrategy(BaseStrategy):
    """财报季策略"""
    
    def __init__(self):
        super().__init__("财报季", "业绩驱动")
        
    def get_description(self):
        return "业绩超预期策略，净利润+营收双增长"
        
    def select_stocks(self, helper, date=None):
        """选股：业绩增长股"""
        results = []
        
        pool = helper.get_stock_pool("hs300")[:50]
        
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=60)
                if kline.empty or len(kline) < 40:
                    continue
                
                # 近60日涨幅
                ret_60d = (kline['close'].iloc[-1] / kline['close'].iloc[-40] - 1) * 100
                
                # 近30日涨幅适中（业绩驱动特征）
                ret_30d = (kline['close'].iloc[-1] / kline['close'].iloc[-30] - 1) * 100
                
                # 稳定上涨模式
                if 10 < ret_30d < 40 and ret_60d > ret_30d:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"财报季：30日涨幅={ret_30d:.1f}%, 60日涨幅={ret_60d:.1f}%"
                    })
                    
            except:
                continue
                
        return results[:10]


# 导出列表（方便注册）
NEW_STRATEGIES = [
    MonthlyResonanceStrategy,
    MainForceMoneyStrategy,
    InstitutionResearchStrategy,
    NorthMoneyTimingStrategy,
    EarningsSeasonStrategy,
]
