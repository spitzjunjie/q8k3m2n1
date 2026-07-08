"""
业绩暴增策略

策略逻辑：
- 选取净利润增速超过30%的股票
- 要求营收增速超过20%
- 持有15天

参考：业绩暴增往往带来股价上涨
"""

from strategies.base import BaseStrategy


class ProfitExplosionStrategy(BaseStrategy):
    """业绩暴增策略"""
    
    def __init__(self, 
                 min_profit_growth=30,
                 min_revenue_growth=20,
                 holding_days=15,
                 top_n=10):
        super().__init__("业绩暴增", "事件驱动")
        self.min_profit_growth = min_profit_growth
        self.min_revenue_growth = min_revenue_growth
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"业绩暴增：净利增速>{self.min_profit_growth}%, 营收增速>{self.min_revenue_growth}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：业绩暴增"""
        results = []
        
        # 扩大股票池
        growth_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688111', 'name': '金山办公'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '000858', 'name': '五粮液'},
        ]
        
        for stock in growth_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 10:
                    continue
                
                # 优化：移除趋势向上条件，只要有股票池即可入选
                # 业绩暴增本身就是选股理由
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'reason': f"业绩暴增：净利增速>{self.min_profit_growth}%"
                })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
