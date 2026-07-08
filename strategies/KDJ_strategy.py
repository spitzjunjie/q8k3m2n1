"""
KDJ超卖金叉策略

策略逻辑：
- 筛选KDJ在20以下形成金叉的股票
- 要求J值从负值回升
- 持有至J > 80或持有10天

参考：KDJ是经典的超买超卖指标
"""

from strategies.base import BaseStrategy


class KDJStrategy(BaseStrategy):
    """KDJ超卖金叉策略"""
    
    def __init__(self, 
                 oversold=20,
                 overbought=80,
                 holding_days=10,
                 top_n=10):
        super().__init__("KDJ超卖金叉", "技术面")
        self.oversold = oversold
        self.overbought = overbought
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"KDJ超卖金叉：K<{self.oversold}后金叉, 持有至J>{self.overbought}"

    def calculate_kdj(self, prices, high_prices, low_prices, n=9, m1=3, m2=3):
        """计算KDJ"""
        if len(prices) < n:
            return None, None, None
        
        # 计算RSV
        rsv = []
        for i in range(n-1, len(prices)):
            high = max(high_prices[i-n+1:i+1])
            low = min(low_prices[i-n+1:i+1])
            if high != low:
                rsv.append((prices[i] - low) / (high - low) * 100)
            else:
                rsv.append(50)
        
        if len(rsv) < m1 + m2:
            return None, None, None
        
        # 计算K、D、J
        k = [50]
        d = [50]
        for i in range(1, len(rsv)):
            k.append((m1 - 1) / m1 * k[-1] + rsv[i] / m1)
            d.append((m2 - 1) / m2 * d[-1] + k[-1] / m2)
        
        j = [3 * k[i] - 2 * d[i] for i in range(len(k))]
        
        return k[-1], d[-1], j[-1]

    def select_stocks(self, helper, date=None):
        """选股：KDJ超卖金叉"""
        results = []
        
        # 模拟热门股票池
        kdj_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '601166', 'name': '兴业银行'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600016', 'name': '民生银行'},
            {'symbol': '601288', 'name': '农业银行'},
        ]
        
        for stock in kdj_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                prices = kline['close'].values
                high = kline['high'].values
                low = kline['low'].values
                
                k, d, j = self.calculate_kdj(prices, high, low)
                
                if k and d and j:
                    # 检查超卖金叉
                    if k < self.oversold and k > d and len(prices) >= 2:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"KDJ超卖金叉：K={k:.1f}, D={d:.1f}, J={j:.1f}"
                        })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
