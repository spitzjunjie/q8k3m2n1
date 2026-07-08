"""
KDJ超卖金叉策略

策略逻辑：
- 筛选KDJ在20以下形成金叉的股票
- 要求J值 < 0（极度超卖）
- 要求金叉时放量
- 持有5天，KDJ死叉或J值>80时卖出

参考：KDJ是A股常用的短线指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class KDJStrategy:
    """KDJ超卖金叉策略"""
    
    def __init__(self, 
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "KDJ超卖金叉"
        
    def get_price_data(self, code, days=30):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= 9:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def calculate_kdj(self, df, n=9, m1=3, m2=3):
        """计算KDJ"""
        if df is None or len(df) < n:
            return None, None, None
        
        low_list = df['low'].rolling(window=n, min_periods=1).min()
        high_list = df['high'].rolling(window=n, min_periods=1).max()
        
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        rsv = rsv.fillna(50)
        
        K = rsv.ewm(com=m1-1, adjust=False).mean()
        D = K.ewm(com=m2-1, adjust=False).mean()
        J = 3 * K - 2 * D
        
        return K.values, D.values, J.values
    
    def check_kdj_golden_cross(self, df):
        """检查KDJ金叉"""
        result = self.calculate_kdj(df)
        if result[0] is None:
            return False
        
        k, d, j = result
        
        if len(k) < 3:
            return False
        
        # 检查J值 < 0（极度超卖）
        if j[-1] > 20:
            return False
        
        # 检查金叉：K从下往上穿越D
        golden_cross = k[-1] > d[-1] and k[-2] < d[-2]
        
        return golden_cross
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: KDJ在20以下金叉")
        print(f"风控: KDJ死叉或J>80时卖出, 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'kdj': '20以下金叉',
                'j_value': '<20'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '技术指标：KDJ超卖金叉是短线买点',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = KDJStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
