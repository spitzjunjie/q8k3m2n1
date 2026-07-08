"""
价值成长策略

策略逻辑：
- 筛选PE < 20且净利润增速 > 15%的股票
- 要求ROE > 10%（盈利质量）
- 要求股价在60日均线上方（趋势向上）
- 持有20天，月度调仓

参考：价值与成长相结合，长期有效
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ValueGrowthStrategy:
    """价值成长策略"""
    
    def __init__(self, 
                 max_pe=20,  # 最大PE
                 min_profit_growth=15,  # 最小净利润增速%
                 min_roe=10,  # 最小ROE%
                 ma_days=60,  # 均线天数
                 holding_days=20,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.max_pe = max_pe
        self.min_profit_growth = min_profit_growth
        self.min_roe = min_roe
        self.ma_days = ma_days
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "价值成长"
        
    def get_price_data(self, code, days=70):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= self.ma_days:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def check_above_ma(self, df):
        """检查是否在均线上方"""
        if df is None or len(df) < self.ma_days:
            return False
        
        ma = df['close'].tail(self.ma_days).mean()
        latest_close = df['close'].iloc[-1]
        
        return latest_close > ma
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: PE<{self.max_pe}, 净利润增速>{self.min_profit_growth}%, ROE>{self.min_roe}%")
        print(f"趋势: 股价在{self.ma_days}日均线上方")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'max_pe': self.max_pe,
                'min_profit_growth': f'>{self.min_profit_growth}%',
                'min_roe': f'>{self.min_roe}%',
                'trend': f'{self.ma_days}日均线上方'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '价值+成长：寻找被低估的高成长股票',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ValueGrowthStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
