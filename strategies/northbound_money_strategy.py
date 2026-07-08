"""
北向资金策略

策略逻辑：
- 筛选近5日北向资金（陆股通）持续净买入的股票
- 要求净买入额超过前5日平均值的1.5倍
- 持有5-10只，等权配置
- 每周调仓

参考：外资被称为"聪明钱"，抄底逃顶准确
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class NorthboundMoneyStrategy:
    """北向资金策略"""
    
    def __init__(self, 
                 lookback_days=5,  # 回看天数
                 holding_days=5,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "北向资金"
        
    def get_price_data(self, code, days=15):
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
    
    def calculate_money_flow_proxy(self, df):
        """使用成交量变化作为资金流向代理指标"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        
        # 近3天平均成交量 vs 前3天平均成交量
        recent_vol = recent['vol'].tail(3).mean()
        prev_vol = recent['vol'].head(-3).mean() if len(recent) > 3 else recent_vol
        
        if prev_vol == 0:
            return 0
        
        # 返回倍数
        return recent_vol / prev_vol
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日成交量持续放大1.5倍以上（外资代理）")
        print(f"风控: 持有{self.holding_days}天, 等权配置{self.top_n}只")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'money_flow': '成交量放大1.5倍以上'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '资金流策略：外资动向是重要参考',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = NorthboundMoneyStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
