"""
南向资金策略

策略逻辑：
- 选取南向资金（港资）持续净买入的A股
- 要求近5日净买入
- 持有5天

参考：南向资金被认为是聪明钱
"""

from strategies.base import BaseStrategy


class SouthboundMoneyStrategy(BaseStrategy):
    """南向资金策略"""
    
    def __init__(self, 
                 consecutive_days=5,
                 holding_days=5,
                 top_n=10):
        super().__init__("南向资金", "资金流")
        self.consecutive_days = consecutive_days
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"南向资金：连续{self.consecutive_days}日净买入, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：南向资金重仓"""
        results = []
        
        # 模拟南向资金重仓股（与北向类似）
        south_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
        ]
        
        for stock in south_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if kline.empty or len(kline) < 10:
                    continue
                
                # 检查成交量趋势
                vol_ma = kline['volume'].tail(20).mean()
                recent_vol = kline['volume'].tail(self.consecutive_days).mean()
                
                # 检查价格趋势
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if recent_vol > vol_ma * 1.1 and current > ma10:  # 放量 + 趋势向上
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"南向资金：成交量较均量{round(recent_vol/vol_ma, 1)}倍，趋势向上"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
