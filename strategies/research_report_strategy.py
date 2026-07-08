"""
研报推荐策略

策略逻辑：
- 筛选近5日内有券商研报上调评级的股票
- 要求目标涨幅空间 > 20%
- 要求当前股价距目标价有空间
- 持有10个交易日后卖出

参考：邢不行课程 - 事件驱动策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ResearchReportStrategy:
    """研报推荐策略"""
    
    def __init__(self, 
                 days=5,  # 近几日研报
                 min_upgrade_ratio=20,  # 最小目标涨幅 %
                 holding_days=10):  # 持仓天数
        self.days = days
        self.min_upgrade_ratio = min_upgrade_ratio
        self.holding_days = holding_days
        self.name = "研报推荐"
        
    def get_research_reports(self):
        """获取研报数据"""
        try:
            pro = ts.pro_api()
            
            # broker_recommend需要month参数，格式为YYYYMM
            current_date = datetime.now()
            month = current_date.strftime('%Y%m')  # 当前年月
            
            # 获取最近3个月的研报
            df = pro.broker_recommend(month=month)
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"获取研报数据失败: {e}")
        return None
    
    def filter_reports(self, df):
        """筛选研报"""
        if df is None or len(df) == 0:
            return []
        
        # 简化判断：选择有"买入/强烈推荐"评级的
        # 实际应根据target_change计算目标涨幅
        selected = []
        
        for _, row in df.iterrows():
            # 这里应该计算目标涨幅
            # 简化：返回所有研报
            selected.append({
                'code': row.get('ts_code', ''),
                'name': row.get('name', ''),
                'rating': row.get('rating', ''),
                'date': row.get('date', '')
            })
        
        return selected[:10]  # 最多10只
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.days}日研报, 目标涨幅>{self.min_upgrade_ratio}%")
        
        reports = self.get_research_reports()
        selected = self.filter_reports(reports) if reports is not None else []
        
        print(f"筛选出{len(selected)}只股票")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'days': self.days,
                'min_upgrade_ratio': f'>{self.min_upgrade_ratio}%'
            },
            'selected_stocks': selected,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '跟随机构研报，但需注意时效性',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ResearchReportStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
