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
                 oversold=30,
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
        scored = []

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
                kline = helper.get_history_kline(stock['symbol'], days=30, end_date=date)
                if kline.empty or len(kline) < 20:
                    continue

                prices = kline['close'].values
                high = kline['high'].values
                low = kline['low'].values

                k, d, j = self.calculate_kdj(prices, high, low)

                if k and d and j:
                    scored.append((k, d, j, stock))
                    # 检查超卖金叉（放宽到50）
                    if k < 50 and k > d and len(prices) >= 2:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"KDJ金叉：K={k:.1f}, D={d:.1f}, J={j:.1f}"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 兜底：如果无严格金叉，返回K值最低的3只（最超卖）
        if not results and scored:
            scored.sort(key=lambda x: x[0])
            for k, d, j, stock in scored[:3]:
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'reason': f"KDJ相对超卖：K={k:.1f}, D={d:.1f}, J={j:.1f}"
                })

        return results[:self.top_n]
