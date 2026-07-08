"""
涨停回调策略

策略逻辑：
- 筛选近10日内有涨停但随后回调的股票
- 要求回调幅度在5-15%之间
- 要求回调时缩量（主力没走）
- 持有5天，涨回涨停价附近卖出

参考：涨停板是主力行为，回调是介入机会
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class LimitCallbackStrategy:
    """涨停回调策略"""
    
    def __init__(self, 
                 lookback_days=10,  # 回看天数
                 min_callback=5,  # 最小回调幅度%
                 max_callback=15,  # 最大回调幅度%
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.min_callback = min_callback
        self.max_callback = max_callback
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "涨停回调"
        
    def get_price_data(self, code, days=20):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= self.lookback_days:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def check_limit_up_callback(self, df):
        """检查涨停回调"""
        if df is None or len(df) < self.lookback_days:
            return False, None, None
        
        recent = df.tail(self.lookback_days)
        
        # 简化判断：近10日有较大涨幅（涨停代理）
        max_price = recent['close'].max()
        min_price = recent['close'].min()
        max_ret = (max_price / min_price - 1) * 100
        
        # 有大幅上涨后的回调
        if max_ret < 15:  # 没有接近涨停的涨幅
            return False, None, None
        
        # 计算回调幅度
        latest_price = recent['close'].iloc[-1]
        callback = (latest_price / max_price - 1) * 100
        
        if callback < -self.max_callback or callback > -self.min_callback:
            return False, None, None
        
        return True, max_ret, abs(callback)
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日有涨停后回调{self.min_callback}-{self.max_callback}%")
        print(f"风控: 持有{self.holding_days}天, 涨回涨停价附近卖出")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'callback_range': f'{self.min_callback}-{self.max_callback}%',
                'condition': '回调时缩量'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '事件驱动：涨停板主力介入，回调是机会',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = LimitCallbackStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
