"""
资金流事件策略

策略逻辑：
- 筛选近5日主力资金连续净流入的股票
- 要求主力净流入占比 > 3%
- 持有5-10只，等权配置
- 每周调仓

参考：邢不行 - 资金流事件策略（年化30.90%，2026年至今+35.85%）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class MoneyFlowEventStrategy:
    """资金流事件策略"""
    
    def __init__(self, 
                 consecutive_days=5,  # 连续净流入天数
                 min_ratio=3,  # 主力净流入占比最小值 %
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.consecutive_days = consecutive_days
        self.min_ratio = min_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "资金流事件"
        
    def get_money_flow(self, code, days=10):
        """获取资金流数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            # 使用Tushare资金流向接口
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= self.consecutive_days:
                df = df.sort_values('trade_date')
                return df.tail(self.consecutive_days)
        except Exception as e:
            print(f"获取{code}资金流失败: {e}")
        return None
    
    def calculate_main_ratio(self, df):
        """计算主力净流入占比"""
        if df is None or len(df) < self.consecutive_days:
            return 0
        
        # 简化计算：使用成交额变化估算
        # 实际应使用主力净流入数据
        avg_volume = df['vol'].mean()
        latest_volume = df['vol'].iloc[-1]
        volume_ratio = (latest_volume / avg_volume - 1) * 100 if avg_volume > 0 else 0
        
        return volume_ratio
    
    def check_consecutive_inflow(self, df):
        """检查是否连续净流入"""
        if df is None or len(df) < self.consecutive_days:
            return False
        
        # 使用成交量变化作为代理指标（更合理）
        # 连续3天及以上成交量放大视为资金流入
        increases = 0
        for i in range(1, len(df)):
            if df['vol'].iloc[i] > df['vol'].iloc[i-1]:
                increases += 1
        
        # 至少80%的天数成交量放大
        threshold = int(self.consecutive_days * 0.8)
        return increases >= threshold
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 连续{self.consecutive_days}日净流入, 主力占比>{self.min_ratio}%")
        
        # 这里应该扫描全市场股票
        # 简化：返回信号结构
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'consecutive_days': self.consecutive_days,
                'min_ratio': f'>{self.min_ratio}%'
            },
            'holding_count': self.top_n,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '需扫描全市场股票，优先选择资金持续流入标的',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = MoneyFlowEventStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
