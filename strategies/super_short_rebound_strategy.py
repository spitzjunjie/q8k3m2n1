"""
超跌反弹策略

策略逻辑：
- 选取近期跌幅超过15%的股票
- 要求RSI < 35（严重超卖）
- 股价高于5元（避免低价股风险）
- 止损5%

参考：严重超跌后反弹的概率较大
"""

from strategies.base import BaseStrategy


class SuperShortReboundStrategy(BaseStrategy):
    """超跌反弹策略"""
    
    def __init__(self, 
                 min_drop=15,
                 max_rsi=35,
                 min_price=5,
                 stop_loss=5,
                 top_n=10):
        super().__init__("超跌反弹", "逆向策略")
        self.min_drop = min_drop
        self.max_rsi = max_rsi
        self.min_price = min_price
        self.stop_loss = stop_loss
        self.top_n = top_n
        
    def get_description(self):
        return f"超跌反弹：跌幅>{self.min_drop}%, RSI<{self.max_rsi}, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：严重超跌"""
        results = []
        
        # 扩大股票池
        rebound_stocks = [
            {'symbol': '002236', 'name': '大华股份'},
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '000333', 'name': '美的集团'},
        ]
        
        for stock in rebound_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 10:
                    continue
                
                # 计算跌幅（使用近10日）
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[-10] - 1) * 100 if len(kline) >= 10 else 0
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                
                current_price = kline['close'].iloc[-1]
                
                # 优化：放宽RSI从35到45，跌幅从15%放宽到10%，移除企稳条件
                drop_ok = ret < -10  # 原来是 < -15
                rsi_ok = rsi < 45  # 原来是 < 35
                price_ok = current_price > self.min_price
                
                if drop_ok and rsi_ok and price_ok:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"超跌反弹：近10日跌幅{ret:.1f}%, RSI={rsi:.1f}"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
