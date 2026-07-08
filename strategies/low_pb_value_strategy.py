"""
低PB价值策略

策略逻辑：
- 筛选PB < 1.5的低估值股票
- 要求ROE > 5%（不是垃圾股）
- 要求股价在年线上方（趋势向上）
- 持有30天

参考：PB是最直接的价值指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class LowPBValueStrategy:
    """低PB价值策略"""
    
    def __init__(self, 
                 max_pb=1.5,  # 最大PB
                 min_roe=5,  # 最小ROE%
                 holding_days=30,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "低PB价值"
        
    def get_price_data(self, code, days=250):
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
    
    def check_above_annual_ma(self, df):
        """检查是否在年线上方"""
        if df is None or len(df) < 250:
            return False
        
        annual_ma = df['close'].tail(250).mean()
        latest_close = df['close'].iloc[-1]
        
        return latest_close > annual_ma
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: PB<{self.max_pb}, ROE>{self.min_roe}%")
        print(f"趋势: 股价在年线上方")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'max_pb': f'<{self.max_pb}',
                'min_roe': f'>{self.min_roe}%',
                'trend': '年线上方'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '价值策略：低PB+盈利+趋势向上',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = LowPBValueStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
