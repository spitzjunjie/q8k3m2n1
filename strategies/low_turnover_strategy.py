"""
低波动策略

策略逻辑：
- 选取历史波动率最低的股票
- 要求股价在20日均线上方
- 熊市防御策略
- 持有30天

参考：学术研究表明低波动因子长期有效
"""

from strategies.base import BaseStrategy


class LowVolatilityStrategy(BaseStrategy):
    """低波动策略"""
    
    def __init__(self, 
                 vol_window=20,
                 holding_days=30,
                 top_n=10):
        super().__init__("低波动", "防御策略")
        self.vol_window = vol_window
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"低波动：{self.vol_window}日波动率最低, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：低波动"""
        results = []
        
        # 模拟低波动股票池（大盘蓝筹）
        low_vol_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '601398', 'name': '工商银行'},
            {'symbol': '601288', 'name': '农业银行'},
            {'symbol': '601328', 'name': '交通银行'},
            {'symbol': '601988', 'name': '中国银行'},
            {'symbol': '600016', 'name': '民生银行'},
        ]
        
        best_stocks = []
        
        for stock in low_vol_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 计算波动率
                returns = kline['close'].pct_change()
                volatility = returns.rolling(self.vol_window).std().iloc[-1] * 100
                
                # 检查趋势
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if current > ma20:  # 趋势向上
                    best_stocks.append({
                        'stock': stock,
                        'volatility': volatility,
                        'ma20': ma20,
                        'current': current
                    })
            except:
                continue
        
        # 按波动率排序，取最低的
        best_stocks.sort(key=lambda x: x['volatility'])
        
        for item in best_stocks[:self.top_n]:
            stock = item['stock']
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'reason': f"低波动：{self.vol_window}日波动率{item['volatility']:.2f}%, 趋势向上"
            })
                
        return results[:self.top_n]
