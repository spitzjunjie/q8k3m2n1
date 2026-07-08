"""
RSI超卖反转策略

策略逻辑：
- 筛选RSI < 30的超卖股票
- 要求股价在20日均线附近（不破位）
- 要求成交量萎缩（抛压减轻）
- 持有5天，RSI > 50时卖出

参考：RSI是最经典的超买超卖指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class RSIReboundStrategy:
    """RSI超卖反转策略"""
    
    def __init__(self, 
                 rsi_period=14,  # RSI周期
                 rsi_oversold=30,  # 超卖阈值
                 rsi_sell=50,  # 卖出阈值
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_sell = rsi_sell
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "RSI超卖反转"
        
    def get_price_data(self, code, days=30):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= self.rsi_period + 1:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def calculate_rsi(self, df):
        """计算RSI"""
        if df is None or len(df) < self.rsi_period + 1:
            return None
        
        prices = df['close'].values
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def check_volume_shrink(self, df):
        """检查成交量萎缩"""
        if df is None or len(df) < 5:
            return False
        
        recent = df.tail(5)
        avg_vol = recent['vol'].mean()
        latest_vol = recent['vol'].iloc[-1]
        
        return latest_vol < avg_vol * 0.7
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: RSI<{self.rsi_oversold}, 成交量萎缩")
        print(f"风控: RSI>{self.rsi_sell}时卖出, 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'rsi_oversold': f'<{self.rsi_oversold}',
                'volume_shrink': '近5日缩量'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '技术指标：超卖反弹，但需快进快出',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = RSIReboundStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
