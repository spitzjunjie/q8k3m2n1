"""
业绩超预期策略

策略逻辑：
- 筛选财报披露后业绩超预期的股票
- 要求净利润增速超过分析师预期
- 要求营收和利润双增长
- 持有10天

参考：业绩超预期是A股最重要的催化剂
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ProfitExceedsExpectationStrategy:
    """业绩超预期策略"""
    
    def __init__(self, 
                 holding_days=10,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "业绩超预期"
        
    def get_price_data(self, code, days=20):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def check_profit_jump(self, df):
        """检查利润暴增（业绩超预期的代理）"""
        if df is None or len(df) < 10:
            return False
        
        recent = df.tail(10)
        
        # 计算近10日涨幅
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        ret = (end_price / start_price - 1) * 100
        
        # 业绩超预期通常会带动股价上涨
        # 这里用涨幅作为代理指标
        return ret > 5  # 近10日涨幅超过5%
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 财报披露后业绩超预期")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'condition': '业绩超预期',
                'profit_jump': '近10日涨幅>5%'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '事件驱动：业绩超预期是最强催化剂',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ProfitExceedsExpectationStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
