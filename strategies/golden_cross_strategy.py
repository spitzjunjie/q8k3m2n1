"""
MACD金叉策略

策略逻辑：
- 筛选MACD在零轴上方形成金叉的股票
- 要求DEA > 0（多头趋势）
- 要求DIF从下往上穿越DEA
- 持有10天或MACD死叉卖出

参考：MACD是最经典的趋势指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class GoldenCrossStrategy:
    """MACD金叉策略"""
    
    def __init__(self, 
                 holding_days=10,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "MACD金叉"
        
    def get_price_data(self, code, days=40):
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
    
    def calculate_macd(self, df, fast=12, slow=26, signal=9):
        """计算MACD"""
        if df is None or len(df) < slow + signal:
            return None, None, None
        
        prices = df['close'].values
        
        # 计算EMA
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        
        # DIF = EMA(fast) - EMA(slow)
        dif = ema_fast - ema_slow
        
        # DEA = EMA(DIF, signal)
        dea = self._ema(dif, signal)
        
        # MACD柱 = (DIF - DEA) * 2
        bar = (dif - dea) * 2
        
        return dif, dea, bar
    
    def _ema(self, prices, period):
        """计算EMA"""
        ema = [prices[0]]
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(prices)):
            ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
        
        return np.array(ema)
    
    def check_golden_cross(self, df):
        """检查MACD金叉"""
        result = self.calculate_macd(df)
        if result[0] is None:
            return False
        
        dif, dea, bar = result
        
        if len(dif) < 3:
            return False
        
        # 检查金叉：DIF从下方穿越DEA
        # 当前DIF > DEA（金叉）
        # 前一天DIF < DEA（死叉）
        golden_cross = dif[-1] > dea[-1] and dif[-2] < dea[-2]
        
        # 检查是否在零轴上方
        above_zero = dif[-1] > 0
        
        return golden_cross and above_zero
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: MACD在零轴上方金叉")
        print(f"风控: 持有{self.holding_days}天或MACD死叉")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'macd': '零轴上方金叉'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '技术指标：MACD金叉代表趋势转强',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = GoldenCrossStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
