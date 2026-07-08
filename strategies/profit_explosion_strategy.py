"""
业绩暴增策略

策略逻辑：
- 筛选近2个季度净利润增速超过30%的股票
- 要求营收增速也超过20%（真增长）
- 要求股价在年线上方（趋势向上）
- 持有15天

参考：业绩超预期是A股最重要的驱动因素
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ProfitExplosionStrategy:
    """业绩暴增策略"""
    
    def __init__(self, 
                 min_profit_growth=30,  # 最小净利润增速%
                 min_revenue_growth=20,  # 最小营收增速%
                 holding_days=15,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.min_profit_growth = min_profit_growth
        self.min_revenue_growth = min_revenue_growth
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "业绩暴增"
        
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
        print(f"筛选条件: 净利润增速>{self.min_profit_growth}%, 营收增速>{self.min_revenue_growth}%")
        print(f"趋势: 股价在年线上方")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'min_profit_growth': f'>{self.min_profit_growth}%',
                'min_revenue_growth': f'>{self.min_revenue_growth}%',
                'trend': '年线上方'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '业绩驱动：真增长+趋势向上',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ProfitExplosionStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
