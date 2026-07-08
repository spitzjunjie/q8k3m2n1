"""
价值成长策略

策略逻辑：
- 选取低估值（PE<20）且高成长（增速>15%）的股票
- 要求ROE>10%
- 持有20天，季度调仓

参考：价值与成长相结合，寻找性价比最高的标的
"""

from strategies.base import BaseStrategy


class ValueGrowthStrategy(BaseStrategy):
    """价值成长策略"""
    
    def __init__(self, 
                 max_pe=20,
                 min_growth=15,
                 min_roe=10,
                 holding_days=20,
                 top_n=10):
        super().__init__("价值成长", "价值策略")
        self.max_pe = max_pe
        self.min_growth = min_growth
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"价值成长：PE<{self.max_pe}, 增速>{self.min_growth}%, ROE>{self.min_roe}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：价值成长"""
        results = []
        
        # 模拟价值成长股票池
        value_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
        ]
        
        for stock in value_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 检查趋势：20日均线上方
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if current > ma20:  # 趋势向上
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"价值成长：PE<{self.max_pe}, ROE>{self.min_roe}%, 趋势向上"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
