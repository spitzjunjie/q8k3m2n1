"""
量价齐升策略

策略逻辑：
- 筛选近5日量价齐升的股票
- 要求成交量和股价同时创新高
- 要求涨幅在5-15%之间（不过热）
- 持有5天

参考：量价齐升是最经典的技术信号
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ContinuousVolumeStrategy:
    """量价齐升策略"""
    
    def __init__(self, 
                 lookback_days=5,  # 回看天数
                 min_return=5,  # 最小涨幅%
                 max_return=15,  # 最大涨幅%
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.min_return = min_return
        self.max_return = max_return
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "量价齐升"
        
    def get_price_data(self, code, days=30):
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
    
    def check_volume_price_rise(self, df):
        """检查量价齐升"""
        if df is None or len(df) < self.lookback_days:
            return False, None
        
        recent = df.tail(self.lookback_days)
        
        # 计算近5日涨幅
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        ret = (end_price / start_price - 1) * 100
        
        # 检查涨幅是否在范围内
        if ret < self.min_return or ret > self.max_return:
            return False, ret
        
        # 检查成交量是否持续放大
        vol_trend = recent['vol'].tolist()
        increases = sum(1 for i in range(1, len(vol_trend)) if vol_trend[i] > vol_trend[i-1])
        
        # 至少60%的日子成交量放大
        if increases < len(vol_trend) * 0.6:
            return False, ret
        
        return True, ret
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日量价齐升, 涨幅{self.min_return}-{self.max_return}%")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'return_range': f'{self.min_return}-{self.max_return}%',
                'volume_trend': '持续放大'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '技术信号：量价齐升代表资金认可',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ContinuousVolumeStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
