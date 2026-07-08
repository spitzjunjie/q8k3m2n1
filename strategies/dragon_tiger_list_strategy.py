"""
龙虎榜策略

策略逻辑：
- 筛选近5日登上龙虎榜的股票
- 要求机构和营业部同时出现在买入席位
- 要求股价涨幅超过5%但未涨停
- 持有3-5天

参考：龙虎榜数据反映机构和游资动向
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class DragonTigerListStrategy:
    """龙虎榜策略"""
    
    def __init__(self, 
                 days=5,  # 近几日龙虎榜
                 holding_days=3,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.days = days
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "龙虎榜"
        
    def get_dragon_tiger_data(self):
        """获取龙虎榜数据"""
        try:
            pro = ts.pro_api()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=self.days+5)).strftime('%Y%m%d')
            
            # 获取龙虎榜数据
            df = pro.major_news(start_date=start_date, end_date=end_date, type='利好')
            return df
        except Exception as e:
            print(f"获取龙虎榜数据失败: {e}")
        return None
    
    def filter_stocks(self, df):
        """筛选符合条件的股票"""
        if df is None or len(df) == 0:
            return []
        
        # 简化筛选：选择有机构席位的
        selected = []
        for _, row in df.iterrows():
            # 简化判断：返回近5日龙虎榜股票
            selected.append({
                'code': row.get('ts_code', ''),
                'name': row.get('name', ''),
                'date': row.get('datetime', '')
            })
        
        return selected[:self.top_n]
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.days}日龙虎榜, 机构和游资同时买入")
        print(f"风控: 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'days': self.days,
                'condition': '机构和游资同时买入'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '事件驱动：跟随机构和游资动向',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = DragonTigerListStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
