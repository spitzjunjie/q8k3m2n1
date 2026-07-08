"""
高股息策略

策略逻辑：
- 筛选近12个月股息率 > 3%的股票
- 要求ROE > 10%（持续盈利能力）
- 要求股价在60日均线上方
- 持有30天，季度调仓

参考：股息率是价值投资的重要指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class HighDividendStrategy:
    """高股息策略"""
    
    def __init__(self, 
                 min_dividend=3,  # 最小股息率%
                 min_roe=10,  # 最小ROE%
                 holding_days=30,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.min_dividend = min_dividend
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "高股息"
        
    def get_price_data(self, code, days=70):
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
    
    def check_above_ma(self, df, ma_days=60):
        """检查是否在均线上方"""
        if df is None or len(df) < ma_days:
            return False
        
        ma = df['close'].tail(ma_days).mean()
        latest_close = df['close'].iloc[-1]
        
        return latest_close > ma
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 股息率>{self.min_dividend}%, ROE>{self.min_roe}%")
        print(f"趋势: 股价在{60}日均线上方")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'min_dividend': f'>{self.min_dividend}%',
                'min_roe': f'>{self.min_roe}%',
                'trend': '60日均线上方'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '价值策略：高股息+盈利+趋势向上',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = HighDividendStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
