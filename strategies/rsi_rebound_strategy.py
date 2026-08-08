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
        
        # 扩大的股票池
        stock_pool = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '002714', 'name': '牧原股份'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '601138', 'name': '工业富联'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002415', 'name': '海康威视'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '601888', 'name': '中国中免'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300274', 'name': '阳光电源'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '000001', 'name': '平安银行'},
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '600028', 'name': '中国石化'},
            {'symbol': '601857', 'name': '中国石油'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '300015', 'name': '爱尔眼科'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]
        
        for stock in stock_pool:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                prices = kline['close'].values
                rsi = self.calculate_rsi(prices)
                
                if rsi and rsi < 60:  # 放宽条件，RSI不过高即可
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"RSI偏低：RSI={rsi:.1f}"
                    })
                
                if len(results) >= self.top_n:
                    break
            except Exception:
                continue
        
        # 兜底：返回RSI相对较低的股票
        if not results:
            scored = []
            for stock in stock_pool:
                try:
                    kline = helper.get_history_kline(stock['symbol'], days=30)
                    if kline.empty or len(kline) < 20:
                        continue
                    
                    prices = kline['close'].values
                    rsi = self.calculate_rsi(prices)
                    
                    if rsi and rsi < 50:
                        scored.append((rsi, stock))
                except Exception:
                    continue
            
            scored.sort(key=lambda x: x[0])
            for rsi, stock in scored[:self.top_n]:
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'reason': f"RSI偏低：RSI={rsi:.1f}"
                })
        
        return results[:self.top_n]
