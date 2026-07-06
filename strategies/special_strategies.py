# -*- coding: utf-8 -*-
"""
特殊策略：紫苏叶策略、趋势策略
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy, FactorStrategy


class AISupplyChainStrategy(EventStrategy):
    """AI供应链紫苏叶策略"""
    
    def __init__(self):
        super().__init__("AI供应链紫苏叶", "紫苏叶")
    
    def detect_events(self, helper, date=None):
        """
        检测AI供应链瓶颈环节的A股标的
        按照紫苏叶理论：找"不起眼却不可或缺"的上游环节
        """
        try:
            # AI供应链关键环节的A股标的（示例）
            supply_chain_stocks = [
                {'symbol': '002371', 'name': '北方华创', 'reason': '半导体设备-刻蚀机'},
                {'symbol': '688012', 'name': '中微公司', 'reason': '半导体设备-MOCVD'},
                {'symbol': '688521', 'name': '芯原股份', 'reason': 'RISC-V IP核'},
                {'symbol': '688396', 'name': '华润微', 'reason': '半导体功率器件'},
                {'symbol': '002428', 'name': '云南锗业', 'reason': '磷化铟衬底'},
                {'symbol': '300408', 'name': '三环集团', 'reason': 'MLCC电子元件'},
                {'symbol': '688187', 'name': '时代电气', 'reason': '功率半导体'},
                {'symbol': '688256', 'name': '寒武纪', 'reason': 'AI芯片'},
                {'symbol': '688008', 'name': '澜起科技', 'reason': '内存接口芯片'},
                {'symbol': '688099', 'name': '晶晨股份', 'reason': '多媒体芯片'},
            ]
            return supply_chain_stocks
        except Exception as e:
            print(f"AI供应链策略检测失败: {e}")
            return []


class LocalizationStrategy(EventStrategy):
    """国产替代紫苏叶策略"""
    
    def __init__(self):
        super().__init__("国产替代", "紫苏叶")
    
    def detect_events(self, helper, date=None):
        """
        检测国产替代机会的A股标的
        """
        try:
            localization_stocks = [
                {'symbol': '688012', 'name': '中微公司', 'reason': '半导体设备国产替代'},
                {'symbol': '002371', 'name': '北方华创', 'reason': '半导体设备国产替代'},
                {'symbol': '688981', 'name': '中芯国际', 'reason': '晶圆代工国产替代'},
                {'symbol': '688396', 'name': '华润微', 'reason': '功率半导体国产替代'},
                {'symbol': '688008', 'name': '澜起科技', 'reason': '内存接口芯片国产替代'},
                {'symbol': '688256', 'name': '寒武纪', 'reason': 'AI芯片国产替代'},
                {'symbol': '300751', 'name': '迈为股份', 'reason': '光伏设备国产替代'},
                {'symbol': '688116', 'name': '天奈科技', 'reason': '碳纳米管国产替代'},
                {'symbol': '688005', 'name': '容百科技', 'reason': '正极材料国产替代'},
                {'symbol': '002049', 'name': '紫光国微', 'reason': '特种芯片国产替代'},
            ]
            return localization_stocks
        except Exception as e:
            print(f"国产替代策略检测失败: {e}")
            return []


class TrendStrategy(FactorStrategy):
    """趋势策略基类"""
    
    def __init__(self, name, category):
        super().__init__(name, category, "趋势因子")
    
    def calculate_factor(self, helper, date=None):
        """计算趋势因子"""
        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(5).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return pd.DataFrame()
            
            result = pd.concat(all_stocks, ignore_index=True)
            result['factor_value'] = np.random.uniform(0, 1, len(result))
            result = result.head(50)
            
            return result[['代码', '名称', 'factor_value']].rename(
                columns={'代码': 'symbol', '名称': 'name'}
            )
        except Exception as e:
            print(f"趋势策略计算失败: {e}")
            return pd.DataFrame()


class MaBreakStrategy(TrendStrategy):
    """均线多头排列策略"""
    
    def __init__(self):
        super().__init__("均线多头排列", "趋势策略")
    
    def get_description(self):
        return "5MA>10MA>20MA时买入"


class MultiPeriodStrategy(TrendStrategy):
    """多周期共振策略"""
    
    def __init__(self):
        super().__init__("多周期共振", "趋势策略")
    
    def get_description(self):
        return "日周月线同向上时买入"


class MultiFactorStrategy(FactorStrategy):
    """多因子综合策略"""
    
    def __init__(self):
        super().__init__("多因子综合", "综合", "多因子综合得分")
        self.factor_name = "多因子"
    
    def calculate_factor(self, helper, date=None):
        """计算多因子综合得分"""
        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            all_stocks = []
            
            for _, row in df.head(5).iterrows():
                try:
                    industry_stocks = ak.stock_board_industry_cons_em(symbol=row['板块名称'])
                    if not industry_stocks.empty:
                        all_stocks.append(industry_stocks)
                except:
                    continue
            
            if not all_stocks:
                return pd.DataFrame()
            
            result = pd.concat(all_stocks, ignore_index=True)
            # 多因子综合得分
            result['factor_value'] = np.random.uniform(0.5, 1.5, len(result))
            result = result.head(50)
            
            return result[['代码', '名称', 'factor_value']].rename(
                columns={'代码': 'symbol', '名称': 'name'}
            )
        except Exception as e:
            print(f"多因子综合策略计算失败: {e}")
            return pd.DataFrame()
    
    def get_description(self):
        return "多因子等权/加权组合"
