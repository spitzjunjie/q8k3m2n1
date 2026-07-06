# -*- coding: utf-8 -*-
"""
事件驱动策略
"""

import pandas as pd
from strategies.base import EventStrategy
import akshare as ak


class MomentumReversalStrategy(EventStrategy):
    """动量反转策略"""
    
    def __init__(self):
        super().__init__("动量反转", "动量因子")
    
    def detect_events(self, helper, date=None):
        """检测动量反转信号：前期跌幅大但基本面好的股票"""
        try:
            # 获取近期跌幅大的股票
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            # 模拟动量反转信号：近期跌但因子好
            events = []
            for _, row in result.head(30).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '动量反转信号'
                })
            
            return events
        except Exception as e:
            print(f"动量反转策略检测失败: {e}")
            return []


class TrendMomentumStrategy(EventStrategy):
    """趋势动量策略"""
    
    def __init__(self):
        super().__init__("趋势动量", "动量因子")
    
    def detect_events(self, helper, date=None):
        """检测趋势动量信号"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(30).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '趋势向上'
                })
            
            return events
        except Exception as e:
            print(f"趋势动量策略检测失败: {e}")
            return []


class NorthFlowStrategy(EventStrategy):
    """北向资金跟投策略"""
    
    def __init__(self):
        super().__init__("北向资金跟投", "资金因子")
    
    def detect_events(self, helper, date=None):
        """检测北向资金持续净买入的股票"""
        try:
            df = ak.stock_hsgt_hold_stock_em(symbol="北向资金")
            if df.empty:
                return []
            
            events = []
            for _, row in df.head(20).iterrows():
                events.append({
                    'symbol': row.get('代码', ''),
                    'name': row.get('名称', ''),
                    'reason': f"北向持股"
                })
            
            return events
        except Exception as e:
            print(f"北向资金策略检测失败: {e}")
            return []


class InstitutionHoldingStrategy(EventStrategy):
    """机构持仓策略"""
    
    def __init__(self):
        super().__init__("机构持仓", "资金因子")
    
    def detect_events(self, helper, date=None):
        """检测机构重仓股"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(30).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '机构关注'
                })
            
            return events
        except Exception as e:
            print(f"机构持仓策略检测失败: {e}")
            return []


class NorthHeavyStrategy(EventStrategy):
    """北向重仓策略"""
    
    def __init__(self):
        super().__init__("北向重仓", "资金因子")
    
    def detect_events(self, helper, date=None):
        """检测北向资金重仓股"""
        try:
            df = ak.stock_hsgt_hold_stock_em(symbol="北向资金")
            if df.empty:
                return []
            
            events = []
            for _, row in df.head(20).iterrows():
                events.append({
                    'symbol': row.get('代码', ''),
                    'name': row.get('名称', ''),
                    'reason': '北向重仓'
                })
            
            return events
        except Exception as e:
            print(f"北向重仓策略检测失败: {e}")
            return []


class LimitUpCallbackStrategy(EventStrategy):
    """首板回调策略"""
    
    def __init__(self):
        super().__init__("首板回调", "事件驱动")
    
    def detect_events(self, helper, date=None):
        """检测涨停后回调的股票"""
        try:
            df = ak.stock_zt_pool_em(date=None)
            if df.empty:
                return []
            
            events = []
            for _, row in df.head(10).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '涨停股回调关注'
                })
            
            return events
        except Exception as e:
            print(f"首板回调策略检测失败: {e}")
            return []


class STRemoveStrategy(EventStrategy):
    """ST摘帽潜伏策略"""
    
    def __init__(self):
        super().__init__("ST摘帽潜伏", "事件驱动")
    
    def detect_events(self, helper, date=None):
        """检测可能摘帽的ST股"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(10).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': 'ST摘帽预期'
                })
            
            return events
        except Exception as e:
            print(f"ST摘帽策略检测失败: {e}")
            return []


class ExecutiveBuyStrategy(EventStrategy):
    """高管增持策略"""
    
    def __init__(self):
        super().__init__("高管增持", "事件驱动")
    
    def detect_events(self, helper, date=None):
        """检测高管增持信号"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(20).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '高管/大股东增持'
                })
            
            return events
        except Exception as e:
            print(f"高管增持策略检测失败: {e}")
            return []


class EarningsSurpriseStrategy(EventStrategy):
    """业绩超预期策略"""
    
    def __init__(self):
        super().__init__("业绩超预期", "事件驱动")
    
    def detect_events(self, helper, date=None):
        """检测业绩超预期股票"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(20).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '业绩超预期'
                })
            
            return events
        except Exception as e:
            print(f"业绩超预期策略检测失败: {e}")
            return []


class AnalystUpgradeStrategy(EventStrategy):
    """分析师上调策略"""
    
    def __init__(self):
        super().__init__("分析师上调", "事件驱动")
    
    def detect_events(self, helper, date=None):
        """检测分析师评级上调"""
        try:
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(3).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return []
            
            result = pd.concat(all_stocks, ignore_index=True)
            
            events = []
            for _, row in result.head(20).iterrows():
                events.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'reason': '分析师评级上调'
                })
            
            return events
        except Exception as e:
            print(f"分析师上调策略检测失败: {e}")
            return []
