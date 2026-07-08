"""
反过度自信策略

策略逻辑：
- 筛选近20日跌幅较大的股票（过度悲观）
- 要求跌幅 > 10%但 < 30%（不是持续下跌）
- 要求RSI < 40（超卖）
- 持有5-10只，等权配置
- 持有10个交易日后卖出

参考：邢不行 - 反过度自信选股（年化17.06%，2026年至今+1.55%）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class AntiOverconfidenceStrategy:
    """反过度自信策略（逆向策略）"""
    
    def __init__(self, 
                 lookback_days=20,  # 回看天数
                 min_drop=10,  # 最小跌幅 %
                 max_drop=30,  # 最大跌幅 %
                 max_rsi=40,  # RSI最大值
                 holding_days=10,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.min_drop = min_drop
        self.max_drop = max_drop
        self.max_rsi = max_rsi
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "反过度自信"
        
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
    
    def calculate_rsi(self, df, period=14):
        """计算RSI"""
        if df is None or len(df) < period + 1:
            return None
        
        prices = df['close'].values
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_drop(self, df):
        """计算区间跌幅（返回负数表示下跌）"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        
        # 返回负数表示跌幅（例如：-15 表示下跌15%）
        drop = (end_price / start_price - 1) * 100
        return drop
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日跌幅{self.min_drop}-{self.max_drop}%, RSI<{self.max_rsi}")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'drop_range': f'{self.min_drop}%-{self.max_drop}%',
                'max_rsi': self.max_rsi
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '逆向策略：人弃我取，在悲观时买入',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = AntiOverconfidenceStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
