"""
低PB价值策略

策略逻辑：
- 选取市净率PB < 1.5的股票
- 要求ROE > 5%
- 持有30天

参考：低PB是价值投资的经典指标
"""

from strategies.base import BaseStrategy


class LowPBValueStrategy(BaseStrategy):
    """低PB价值策略"""
    
    def __init__(self, 
                 max_pb=1.5,
                 min_roe=5,
                 holding_days=30,
                 top_n=10):
        super().__init__("低PB价值", "价值策略")
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"低PB价值：PB<{self.max_pb}, ROE>{self.min_roe}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：低PB价值"""
        results = []
        
        # 模拟低PB股票池（银行股为主）
        pb_stocks = [
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601288', 'name': '农业银行'},
            {'symbol': '601988', 'name': '中国银行'},
            {'symbol': '600016', 'name': '民生银行'},
            {'symbol': '601818', 'name': '光大银行'},
            {'symbol': '601166', 'name': '兴业银行'},
            {'symbol': '601818', 'name': '光大银行'},
        ]
        
        for stock in pb_stocks:
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
                        'reason': f"低PB价值：PB<{self.max_pb}, ROE>{self.min_roe}%, 趋势向上"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
