"""
行业动量策略

策略逻辑：
- 比较各行业指数的20日涨幅
- 选择涨幅前3名的行业
- 在这些行业中选龙头股
- 持有至行业轮动

参考：邢不行课程 - 行业轮动
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class IndustryMomentumStrategy:
    """行业动量策略"""
    
    def __init__(self, 
                 lookback_days=20,  # 动量周期
                 top_industries=3,  # 选择行业数量
                 holding_days=10):  # 持仓天数
        self.lookback_days = lookback_days
        self.top_industries = top_industries
        self.holding_days = holding_days
        self.name = "行业动量"
        
        # 行业ETF列表（扩展版）
        self.industry_etfs = {
            '白酒': '512690.SH',  # 酒ETF
            '医疗': '512010.SH',  # 医药ETF
            '芯片': '512760.SH',  # 芯片ETF
            '新能源': '515030.SH',  # 新能源车ETF
            '证券': '512880.SH',  # 券商ETF
            '军工': '512660.SH',  # 军工ETF
            '消费': '159928.SH',  # 消费ETF
            '科技': '515000.SH',  # 科技ETF
            '银行': '512800.SH',  # 银行ETF
            '房地产': '512200.SH',  # 房地产ETF
        }
        
    def get_etf_data(self, code, days=30):
        """获取ETF数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E')
            if df is not None and len(df) >= self.lookback_days:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def calculate_return(self, df):
        """计算区间涨幅"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        
        return (end_price / start_price - 1) * 100
    
    def rank_industries(self):
        """行业排名"""
        results = {}
        
        for name, code in self.industry_etfs.items():
            df = self.get_etf_data(code)
            ret = self.calculate_return(df)
            if ret is not None:
                results[name] = ret
                print(f"{name}: {ret:.2f}%")
        
        # 排序
        sorted_industries = sorted(results.items(), key=lambda x: x[1], reverse=True)
        return sorted_industries
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日涨幅Top{self.top_industries}")
        
        ranked = self.rank_industries()
        
        if not ranked:
            return None
        
        top = ranked[:self.top_industries]
        selected_industries = [item[0] for item in top]
        
        return {
            'strategy': self.name,
            'signal': 'BUY',
            'selected_industries': selected_industries,
            'industry_returns': dict(top),
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '追强势行业，等行业轮动后切换',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = IndustryMomentumStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
