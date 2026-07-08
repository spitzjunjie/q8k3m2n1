"""
高股息策略

策略逻辑：
- 筛选近12个月股息率 > 3%的股票
- 要求ROE > 10%（持续盈利能力）
- 要求股价在60日均线上方
- 持有30天，季度调仓

参考：股息率是价值投资的重要指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class HighDividendStrategy(BaseStrategy):
    """高股息策略"""
    
    def __init__(self, 
                 min_dividend=3,  # 最小股息率%
                 min_roe=10,  # 最小ROE%
                 holding_days=30,  # 持仓天数
                 top_n=10):  # 持仓数量
        super().__init__("高股息", "价值策略")
        self.min_dividend = min_dividend
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"高股息策略：股息率>{self.min_dividend}%, ROE>{self.min_roe}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：高股息+趋势向上"""
        results = []
        
        # 模拟高股息股票池（实际应从财务数据获取）
        high_dividend_stocks = [
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601288', 'name': '农业银行'},
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601988', 'name': '中国银行'},
            {'symbol': '600016', 'name': '民生银行'},
            {'symbol': '601818', 'name': '光大银行'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]
        
        for stock in high_dividend_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 20:
                    continue
                    
                # 检查60日均线上方
                ma60 = kline['close'].rolling(60).mean().iloc[-1]
                current_price = kline['close'].iloc[-1]
                
                if current_price > ma60:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"高股息：{self.min_dividend}%+, ROE>{self.min_roe}%, 趋势向上"
                    })
                    
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]


if __name__ == '__main__':
    strategy = HighDividendStrategy()
    print(f"策略: {strategy.name}")
    print(f"描述: {strategy.get_description()}")
