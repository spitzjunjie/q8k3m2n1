"""
RSI超卖反转策略

策略逻辑：
- 选取RSI < 30超卖的股票
- 要求RSI从超卖区域回升
- 持有至RSI > 70或持有10天

参考：RSI是最经典的超买超卖指标
"""

from strategies.base import BaseStrategy


class RSIReboundStrategy(BaseStrategy):
    """RSI超卖反转策略"""
    
    def __init__(self, 
                 oversold=30,
                 overbought=70,
                 holding_days=10,
                 top_n=10):
        super().__init__("RSI超卖反转", "技术面")
        self.oversold = oversold
        self.overbought = overbought
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"RSI超卖反转：RSI<{self.oversold}后回升, 持有至RSI>{self.overbought}"

    def calculate_rsi(self, prices, period=14):
        """计算RSI"""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def select_stocks(self, helper, date=None):
        """选股：RSI超卖反转"""
        results = []
        
        # 模拟热门股票池
        rsi_stocks = [
            {'symbol': '601138', 'name': '工业富联'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '601166', 'name': '兴业银行'},
            {'symbol': '600016', 'name': '民生银行'},
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601288', 'name': '农业银行'},
            {'symbol': '601988', 'name': '中国银行'},
        ]
        
        for stock in rsi_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                prices = kline['close'].values
                rsi = self.calculate_rsi(prices)
                
                if rsi and 30 < rsi < 50:  # 从超卖区域回升
                    # 检查近3日是否企稳
                    if kline['close'].iloc[-1] > kline['close'].iloc[-3]:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"RSI超卖反转：RSI={rsi:.1f}，企稳信号"
                        })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
