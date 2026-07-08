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
        
        # 模拟超跌股票池
        rebound_stocks = [
            {'symbol': '002236', 'name': '大华股份'},
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
        ]
        
        for stock in rebound_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 15:
                    continue
                
                # 计算跌幅
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[0] - 1) * 100
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                
                current_price = kline['close'].iloc[-1]
                
                # 条件：跌幅达标 + RSI超卖 + 价格适中 + 企稳迹象
                if ret < -self.min_drop and rsi < self.max_rsi and current_price > self.min_price:
                    if current_price > kline['close'].iloc[-3]:  # 近3日企稳
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"超跌反弹：近20日跌幅{ret:.1f}%, RSI={rsi:.1f}，企稳信号"
                        })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
